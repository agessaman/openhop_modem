#!/usr/bin/env python3
"""Exercise the real USB-ECM OTA sanity policy on the host and its wiring."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "include" / "ota_sanity_policy.h"
MAIN = (ROOT / "src" / "main.cpp").read_text()
OTA = (ROOT / "src" / "ota_manager.cpp").read_text()

HARNESS = r'''
#include "ota_sanity_policy.h"
#include <cassert>
#include <cstdint>
int main() {
    OtaSanityPolicy policy;
    constexpr uint32_t timeout = 120000;
    policy.observe(1000, true);
    assert(!policy.healthyFor(120999, timeout));
    assert(policy.healthyFor(121000, timeout));
    policy.observe(121001, false);
    assert(!policy.healthyFor(241002, timeout));
    policy.observe(250000, true);
    assert(!policy.healthyFor(369999, timeout));
    assert(policy.healthyFor(370000, timeout));
    policy.reset();
    assert(!policy.healthyFor(500000, timeout));
    policy.observe(0xfffffff0U, true);
    assert(!policy.healthyFor(0x10U, timeout));
    assert(policy.healthyFor(0xfffffff0U + timeout, timeout));
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / "policy.cpp"
    exe = Path(tmp) / "policy"
    src.write_text(HARNESS)
    subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", "-Werror", "-I", str(HEADER.parent), str(src), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

assert "OTAManager::notifyNetworkHealth(radioReady && EthernetManager::hasIP())" in MAIN, "OTA sanity must use Ethernet and radio, not disabled STA"
assert "networkHealth.healthyFor(millis(), SANITY_TIMEOUT_MS)" in OTA
assert "networkHealth.reset()" in OTA
assert 'if (err != ESP_OK) return;' in OTA, "failed validity writes must retry"
print("USB ECM OTA stable-Ethernet sanity policy and wiring: PASS")
