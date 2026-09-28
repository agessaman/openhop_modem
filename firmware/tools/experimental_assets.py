"""Strict packaging for the experimental mixed-framework USB ECM target.

Only successful PlatformIO outputs are accepted: no CMake fallback, no reuse
of a pre-existing factory image, and no promotion into public release assets.
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess

ENV = 'heltec_v42_usb_eth'
OFFSETS = {'bootloader.bin': 0, 'partitions.bin': 0x8000,
           'ota_data_initial.bin': 0xe000, 'firmware.bin': 0x10000}
IDF_FILES = {0: 'bootloader/bootloader.bin', 0x8000: 'partition_table/partition-table.bin',
             0xe000: 'ota_data_initial.bin', 0x10000: 'openhop_modem.bin'}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_experimental(env: str, firmware: Path, dest: Path) -> None:
    if env != ENV:
        raise ValueError(f'No experimental packager for {env}')
    if dest.exists():
        raise FileExistsError(f'Refusing to replace existing package: {dest}')
    out = firmware / '.pio/build' / env
    args = json.loads((out / 'flasher_args.json').read_text())
    if (args['flash_settings']['flash_size'] != '8MB' or
            {int(k, 0): v for k, v in args['flash_files'].items()} != IDF_FILES):
        raise ValueError('Unexpected USB ECM flash layout; review before packaging')
    # SCons does not run IDF's blank_ota_data target. Its generator writes
    # exactly 0xff for the OTA partition length (validated below). Always
    # recreate it; never reuse OTA selection from an earlier build.
    images = {name: (b'\xff' * 0x2000 if name == 'ota_data_initial.bin'
                     else (out / name).read_bytes()) for name in OFFSETS}
    if any(not data for data in images.values()):
        raise ValueError('Empty build component')
    table = images['partitions.bin']
    partitions = []
    for offset in range(0, len(table) - 31, 32):
        magic, typ, sub, start, size, label, flags = struct.unpack_from('<HBBII16sI', table, offset)
        if magic == 0xffff:
            break
        if magic == 0xebeb:
            if table[offset+16:offset+32] != hashlib.md5(table[:offset]).digest():
                raise ValueError('Partition table MD5 mismatch')
            break
        if magic != 0x50aa:
            raise ValueError('Invalid partition table entry')
        partitions.append({'type': typ, 'subtype': sub, 'offset': start, 'size': size,
                           'name': label.rstrip(b'\0').decode('ascii'), 'flags': flags})
    apps = [(p['subtype'], p['offset'], p['size']) for p in partitions if p['type'] == 0]
    ota = [(p['offset'], p['size']) for p in partitions if (p['type'], p['subtype']) == (1, 0)]
    if apps != [(0x10, 0x10000, 0x330000), (0x11, 0x340000, 0x330000)] or ota != [(0xe000, 0x2000)]:
        raise ValueError('Unexpected OTA partition layout')
    if len(images['firmware.bin']) > 0x330000:
        raise ValueError('Application exceeds OTA slot')
    end = 0
    for name, offset in OFFSETS.items():
        if offset < end:
            raise ValueError(f'Overlapping component: {name}')
        end = offset + len(images[name])
    # Validate required identity files before creating the destination.
    elf_hash = digest(out / 'firmware.elf')
    sdkconfig = firmware / f'sdkconfig.{env}'
    sdkconfig.read_bytes()
    sources = {}
    paths = list(firmware.glob('*.ini')) + list(firmware.glob('*.csv')) + list(firmware.glob('sdkconfig.defaults*')) + [firmware / 'CMakeLists.txt']
    for directory in ('src', 'include', 'boards', 'variants', 'tools'):
        paths.extend((firmware / directory).rglob('*'))
    for path in sorted(set(paths)):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            sources[str(path.relative_to(firmware))] = digest(path)
    source_hash = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=firmware,
                         text=True, capture_output=True)
    revision = git.stdout.strip() if git.returncode == 0 else None
    info = {'schema': 1, 'environment': env, 'release_eligible': False,
            'build_id': hashlib.sha256(images['firmware.bin']).hexdigest(),
            'identity_note': 'Build ID is app SHA256; runtime version alone does not identify this build.',
            'source_revision': revision, 'source_tree_sha256': source_hash,
            'source_files_sha256': sources, 'elf_sha256': elf_hash,
            'flash_settings': args['flash_settings'], 'partitions': partitions,
            'factory_offset': 0, 'component_offsets': OFFSETS,
            'verification_scope': 'Build/package only; no hardware, DHCP, RF or recovery claim.'}
    dest.mkdir(parents=True, exist_ok=False)
    merged = bytearray(b'\xff' * end)
    for name, offset in OFFSETS.items():
        data = images[name]
        (dest / name).write_bytes(data)
        merged[offset:offset+len(data)] = data
    (dest / 'firmware.factory.bin').write_bytes(merged)
    manifest = {'name': 'Heltec V4.2 USB ECM openHop Modem (experimental)',
                'version': info['build_id'][:16], 'new_install_prompt_erase': True,
                'builds': [{'chipFamily': 'ESP32-S3', 'parts': [
                    {'path': name, 'offset': offset} for name, offset in OFFSETS.items()]}]}
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (dest / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    shutil.copy2(sdkconfig, dest / 'sdkconfig.txt')
    shutil.copy2(out / 'flasher_args.json', dest / 'idf-flasher-args.json')
    for source in (firmware / 'dependencies.lock', out / 'project_description.json'):
        if source.exists():
            shutil.copy2(source, dest / source.name)
    (dest / 'README.txt').write_text(
        'EXPERIMENTAL HELTEC V4.2 USB ECM / ESP32-S3\n'
        'firmware.bin: app-only HTTP OTA or serial app update at 0x10000.\n'
        'Requires the compatible 8MB dual-OTA partition layout in build-info.json.\n'
        'firmware.factory.bin: full recovery image at 0x0, NOT an OTA upload.\n'
        'Factory padding overwrites NVS/configuration and resets OTA selection.\n'
        'Physical 16MB flash is intentionally configured as 8MB; do not resize.\n'
        'Native USB is HOST during runtime; recovery requires physical ROM download.\n'
        'Wi-Fi is disabled. Do not assume automatic rollback or recovery.\n'
        'No hardware validation performed by this packaging command.\n'
        'build-info.json identifies exact app/ELF/source content; source revision can\n'
        'be null in exports, and source hashes identify uncommitted edits.\n'
        'idf-flasher-args.json is CMake provenance, not a command for these staged\n'
        'filenames. Use manifest.json/component_offsets for staged components.\n')
    files = sorted(p for p in dest.iterdir() if p.is_file())
    (dest / 'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in files))
    print(f'Staged experimental assets in {dest}')
