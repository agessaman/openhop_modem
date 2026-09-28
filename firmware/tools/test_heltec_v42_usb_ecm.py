#!/usr/bin/env python3
"""Host-side contract checks for the experimental V4.2 ECM target (no USB hardware)."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src/usb_ecm_manager.cpp").read_text()
main = (ROOT / "src/main.cpp").read_text()
eth = (ROOT / "src/ethernet_manager.cpp").read_text()
ota = (ROOT / "src/ota_manager.cpp").read_text()
board = (ROOT / "include/boards/heltec_v42_usb_eth.h").read_text()
base = (ROOT / "include/boards/heltec_v42.h").read_text()

# Compile and exercise the real device policy and USB host callback. Only the
# UniFi adapter is admitted at this stage; a new device requires a reviewed
# registry entry with descriptor and hardware evidence.
callback = re.search(r"static bool selectConfiguration\([^}]+\}", source, re.S)
assert callback, "configuration selector not found"
with tempfile.TemporaryDirectory(prefix="openhop-ecm-test-") as td:
    cpp = Path(td) / "test.cpp"
    cpp.write_text('''#include <cstdint>
#include "usb_ecm_device_registry.h"
struct usb_device_desc_t { uint16_t idVendor, idProduct; uint8_t bNumConfigurations; };
''' + callback.group() + '''
int main() {
    uint8_t config = 0;
    usb_device_desc_t real{0x0bda, 0x8153, 2};
    if (!selectConfiguration(&real, &config) || config != 2) return 1;
    usb_device_desc_t wrongVendor{0x1234, 0x8153, 2};
    config = 0;
    if (selectConfiguration(&wrongVendor, &config) || config != 0) return 2;
    usb_device_desc_t wrongProduct{0x0bda, 0x8152, 2};
    if (selectConfiguration(&wrongProduct, &config)) return 3;
    usb_device_desc_t single{0x0bda, 0x8153, 1};
    if (selectConfiguration(&single, &config)) return 4;
    if (openhopUsbEcmDeviceCount < 1) return 5;
    const auto* device = findOpenhopUsbEcmDevice(0x0bda, 0x8153, 2);
    if (!device || device->configurationValue != 2) return 6;
    if (findOpenhopUsbEcmDevice(0x0bda, 0x8153, 1)) return 7;
    for (size_t i = 0; i < openhopUsbEcmDeviceCount; ++i) {
        const auto& d = openhopUsbEcmDevices[i];
        if (!d.model || !d.model[0] || !d.configurationValue) return 8;
        usb_device_desc_t candidate{d.vendorId, d.productId, d.configurationValue};
        config = 0;
        if (!selectConfiguration(&candidate, &config) || config != d.configurationValue) return 9;
        for (size_t j = 0; j < i; ++j)
            if (openhopUsbEcmDevices[j].vendorId == d.vendorId &&
                openhopUsbEcmDevices[j].productId == d.productId) return 10;
    }
}
''')
    exe = Path(td) / "test"
    subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "include"), str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
assert 'for (size_t i = 0; i < openhopUsbEcmDeviceCount; ++i)' in source
assert 'matchIds[i].idVendor = openhopUsbEcmDevices[i].vendorId;' in source
assert 'matchIds[i].idProduct = openhopUsbEcmDevices[i].productId;' in source

assert board.replace('boards/heltec_v42_usb_eth.h — experimental V4.2 USB ECM',
                     'boards/heltec_v42.h — Heltec WiFi LoRa 32 V4.2').replace(
    '"Heltec V4.2 USB ECM"', '"Heltec V4.2"').replace(
    '"heltec-v42-usb-eth"', '"heltec-v42"').replace(
    '.has_wifi       = false,', '.has_wifi       = true,') == base, "RF/GPIO policy drift"
assert 'WifiManager::begin();' in main and 'EthernetManager::begin(deviceHostname.c_str());' in main
assert main.index('WifiManager::begin();', main.index('// ─── Network bring-up:')) < main.index('EthernetManager::begin(deviceHostname.c_str());')
assert 'WifiManager::isSTAConnected() || EthernetManager::hasIP()' in main
assert 'String token = BOARD.has_wifi ? wcfg.tcpToken : String();' in main
assert 'UsbEcmManager::hasIP()' in eth and 'void end() {}' in eth
assert 'snap.ip = UsbEcmManager::localIP();' in ota
assert 'if (!checkAuth()) return;' in ota[ota.index('static void handleUpdateUpload()'):]
assert 'httpServer->on("/update", HTTP_POST, handleUpdateResult, handleUpdateUpload);' in ota
assert 'CONFIG_PARTITION_TABLE_CUSTOM=y' in (ROOT / 'sdkconfig.defaults').read_text()
assert 'uint32_t consumeInvalidation()' in source
assert 'TCPServer::invalidateInterface(IPAddress(invalidECM))' in main
assert main.index('TCPServer::invalidateInterface(IPAddress(invalidECM))') < main.index('if (tcpStarted) TCPServer::loop();')
assert 'if (!otaStarted && WifiManager::isSTAConnected())' not in main
assert 'if (!otaStarted && netUp)' in main
assert '.has_wifi       = false,' in board
print('ECM selector; GC1109 policy; Ethernet-only; link invalidation; Ethernet HTTP; token/HTTP OTA; netif snapshot; OTA partitions: PASS')
