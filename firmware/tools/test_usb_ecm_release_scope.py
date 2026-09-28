#!/usr/bin/env python3
"""Experimental ECM target stays out of asset/release automation until ready."""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import build_firmware_assets as builder
import package_release_assets as packager

for discover in (builder.discover_envs, packager.discover_platformio_envs):
    envs = discover()
    assert 'heltec_v42' in envs
    assert 'heltec_v42_usb_eth' not in envs, discover.__name__
    assert len(envs) == len(set(envs))
assert 'heltec_v42_usb_eth' in (TOOLS.parent / 'platformio.ini').read_text()
print('Experimental ECM env excluded from production asset/release lists: PASS')
