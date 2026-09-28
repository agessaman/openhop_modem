"""Host tests for explicit, non-release firmware builds."""
import unittest
import json
import struct
import tempfile
import subprocess
import sys
from unittest.mock import patch
from pathlib import Path
import build_firmware_assets as assets


class PackagingTests(unittest.TestCase):
    def test_packages_pio_outputs_with_verified_idf_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fw = root / 'firmware'
            out = fw / '.pio/build/heltec_v42_usb_eth'
            out.mkdir(parents=True)
            fw.joinpath('platformio.ini').write_text('[env:heltec_v42_usb_eth]\n')
            table = b''.join(struct.pack('<HBBII16sI', 0x50AA, typ, sub, off, size, name, 0)
                             for typ, sub, off, size, name in [
                                 (1, 0, 0xe000, 0x2000, b'otadata'),
                                 (0, 0x10, 0x10000, 0x330000, b'app0'),
                                 (0, 0x11, 0x340000, 0x330000, b'app1')])
            images = {'bootloader.bin': b'boot', 'partitions.bin': table,
                      'firmware.bin': b'app-ota', 'ota_data_initial.bin': b'\xff' * 0x2000}
            for name, data in images.items():
                if name != 'ota_data_initial.bin':
                    out.joinpath(name).write_bytes(data)
            out.joinpath('firmware.elf').write_bytes(b'elf')
            fw.joinpath('sdkconfig.heltec_v42_usb_eth').write_text('CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y\n')
            out.joinpath('flasher_args.json').write_text(json.dumps({
                'flash_settings': {'flash_size': '8MB'},
                'flash_files': {'0x0': 'bootloader/bootloader.bin', '0x8000': 'partition_table/partition-table.bin',
                                '0xe000': 'ota_data_initial.bin', '0x10000': 'openhop_modem.bin'}}))
            dest = root / 'result'
            assets.collect_experimental('heltec_v42_usb_eth', fw, dest)
            factory = dest.joinpath('firmware.factory.bin').read_bytes()
            for name, offset in [('bootloader.bin', 0), ('partitions.bin', 0x8000),
                                 ('ota_data_initial.bin', 0xe000), ('firmware.bin', 0x10000)]:
                self.assertEqual(factory[offset:offset+len(images[name])], images[name])
            manifest = json.loads(dest.joinpath('manifest.json').read_text())
            self.assertEqual([x['offset'] for x in manifest['builds'][0]['parts']], [0, 0x8000, 0xe000, 0x10000])
            info = json.loads(dest.joinpath('build-info.json').read_text())
            self.assertEqual(info['build_id'], assets.sha256_file(dest / 'firmware.bin'))
            self.assertFalse(info['release_eligible'])
            for line in dest.joinpath('SHA256SUMS.txt').read_text().splitlines():
                digest, name = line.split('  ')
                self.assertEqual(digest, assets.sha256_file(dest / name))
            # Never overwrite an operator's earlier package.
            with self.assertRaises(FileExistsError):
                assets.collect_experimental('heltec_v42_usb_eth', fw, dest)
            out.joinpath('firmware.bin').write_bytes(b'x' * (0x330000 + 1))
            with self.assertRaises(ValueError):
                assets.collect_experimental('heltec_v42_usb_eth', fw, root / 'oversize')
            out.joinpath('firmware.bin').write_bytes(images['firmware.bin'])
            original_args = out.joinpath('flasher_args.json').read_text()
            wrong = json.loads(original_args)
            wrong['flash_files']['0x1000'] = wrong['flash_files'].pop('0x0')
            out.joinpath('flasher_args.json').write_text(json.dumps(wrong))
            with self.assertRaises(ValueError):
                assets.collect_experimental('heltec_v42_usb_eth', fw, root / 'wrong-offset')
            out.joinpath('flasher_args.json').write_text(original_args)
            out.joinpath('partitions.bin').write_bytes(b'bad table')
            with self.assertRaises(ValueError):
                assets.collect_experimental('heltec_v42_usb_eth', fw, root / 'bad-partitions')
            out.joinpath('firmware.bin').unlink()
            with self.assertRaises(FileNotFoundError):
                assets.collect_experimental('heltec_v42_usb_eth', fw, root / 'missing')



class SelectionTests(unittest.TestCase):
    def test_pio_and_idf_use_same_explicit_partition_csv(self):
        import configparser
        config = configparser.ConfigParser(interpolation=None)
        config.read(assets.PLATFORMIO_INI)
        self.assertEqual(config['env:heltec_v42_usb_eth'].get('board_build.partitions'),
                         'boards/heltec_v42_usb_eth_8mb.csv')

    def test_failed_build_cannot_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / 'project'
            project.mkdir()
            argv = ['build_firmware_assets.py', '--variant', 'heltec_v42_usb_eth',
                    '--allow-experimental', '--pio', '/bin/false', '--output-dir', str(root / 'assets')]
            with patch.object(sys, 'argv', argv), patch.object(assets, 'FIRMWARE', project), \
                 patch.object(assets, 'SELECTED_ENVS_FILE', project / 'selected'), \
                 patch.object(assets, 'collect_experimental') as collect:
                with self.assertRaises(subprocess.CalledProcessError):
                    assets.main()
                collect.assert_not_called()
            self.assertFalse((root / 'assets').exists())

    def test_cli_requires_opt_in_and_external_destination(self):
        tool = Path(assets.__file__)
        cases = [([], False), (['--allow-experimental'], False),
                 (['--allow-experimental', '--output-dir', str(assets.ROOT / 'unsafe')], False)]
        with tempfile.TemporaryDirectory() as tmp:
            cases.append((['--allow-experimental', '--output-dir', tmp], True))
            for extra, success in cases:
                result = subprocess.run([sys.executable, str(tool), '--variant',
                                         'heltec_v42_usb_eth', '--plan', *extra],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stderr)

    def test_explicit_opt_in_only(self):
        target = "heltec_v42_usb_eth"
        self.assertEqual(assets.select_build_envs(target, True, None, None), [target])
        with self.assertRaises(SystemExit):
            assets.select_build_envs(target, False, None, None)
        for mode in ("auto", "all"):
            self.assertNotIn(target, assets.select_build_envs(mode, True, None, None))


if __name__ == "__main__":
    unittest.main()
