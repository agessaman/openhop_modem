"""Release-eligible PlatformIO environments shared by build and packaging.

Use `custom_release = false` in a PlatformIO env for a prototype that
builds locally but must not enter the public asset set yet. The default
remains release-enabled to preserve the existing supported target list.
"""
from pathlib import Path


def discover_release_envs(platformio_ini: Path) -> list[str]:
    enabled = []
    current = None
    release = True
    for raw in platformio_ini.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith('[') and line.endswith(']'):
            if current is not None and release:
                enabled.append(current)
            current = line[5:-1] if line.startswith('[env:') else None
            release = True
        elif current is not None and line.startswith('custom_release'):
            key, sep, value = line.partition('=')
            if sep and key.strip() == 'custom_release':
                flag = value.split(';', 1)[0].strip().lower()
                if flag not in ('true', 'false'):
                    raise ValueError(f'{platformio_ini}: invalid custom_release={flag!r}')
                release = flag == 'true'
    if current is not None and release:
        enabled.append(current)
    if not enabled:
        raise ValueError(f'No release-enabled [env:<name>] blocks in {platformio_ini}')
    if len(enabled) != len(set(enabled)):
        raise ValueError(f'Duplicate release environment in {platformio_ini}')
    return enabled
