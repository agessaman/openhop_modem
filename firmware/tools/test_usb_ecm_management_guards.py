#!/usr/bin/env python3
"""Source contracts for Ethernet-only management; existing render tests cover UI."""
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / 'src/main.cpp').read_text()
ota = (ROOT / 'src/ota_manager.cpp').read_text()
wifi = (ROOT / 'src/wifi_manager.cpp').read_text()
ui = (ROOT / 'src/webui_shared.cpp').read_text()
def preprocess(text):
    return subprocess.run(['cpp', '-P', '-DOPENHOP_USB_ECM', '-DARDUINO_ARCH_ESP32'], input=text, text=True, capture_output=True, check=True).stdout
boot_reset = main[main.index('    // PRG held'):main.index('    // Drive the E22')]
assert 'WifiManager::checkResetButton();' not in preprocess(boot_reset), 'boot button must not erase management NVS on USB ECM'
for cmd, end in [('CMD_SET_WIFI', 'CMD_GET_VERSION'), ('CMD_WIFI_RESET', 'default:')]:
    start = main.index('    case '+cmd+':')
    stop = main.index('    case '+end+':', start) if end != 'default:' else main.index('    default:', start)
    active = preprocess(main[start:stop])
    assert 'sendError(ERR_INVALID_CMD, src)' in active
    assert 'WifiManager::saveConfig' not in active and 'WifiManager::factoryReset' not in active
assert 'if (BOARD.has_wifi) {\n        httpServer->on("/wifi-reset"' in ota
assert 'model.capabilities.wifi = BOARD.has_wifi;' in ota
assert 'model.capabilities.wifiReset = BOARD.has_wifi;' in ota
assert 'model.capabilities.ethernet = true;' in preprocess(ota[ota.index('    model.capabilities.wifi ='):ota.index('    model.capabilities.mdns')])
assert 'if (m.capabilities.wifi)' in ui and 'if (m.capabilities.wifiReset)' in ui
assert 'if (BOARD.has_wifi) cfg.wifiPowerSave = httpServer->hasArg("wifi_ps");' in ota
load = wifi[wifi.index('void loadConfigOnly()'):wifi.index('void begin()')]
assert 'loadConfig();' in load and 'WiFi.begin' not in load and 'factoryReset' not in load
assert 'if (!useEthernet && BOARD.has_wifi)' in main
assert 'if (BOARD.has_wifi) WifiManager::loop();' in main
upload = ota[ota.index('static void handleUpdateUpload()'):ota.index('// ─── ArduinoOTA plumbing')]
assert upload.index('if (!checkAuth()) return;') < upload.index('Update.begin(')
assert 'loadHttpPassword();' in ota[ota.index('void begin(const String& hn'):]
print('Ethernet-only reset/provisioning rejection, retained NVS, UI capabilities, authenticated upload: PASS')
