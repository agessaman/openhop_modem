#!/usr/bin/env python3
"""Execute production boot-button setup with recording GPIO boundaries."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
main = (root / 'src/main.cpp').read_text()
block = main[main.index('    // PRG held'):main.index('    // Drive the E22')]
harness = r'''
#include <cassert>
constexpr int INPUT_PULLUP = 2;
constexpr int INPUT_PULLDOWN = 3;
struct { int pin_user_button; bool user_button_active_low; } BOARD;
int configuredPin = -1, configuredMode = -1, resetCalls = 0;
void pinMode(int pin, int mode) { configuredPin = pin; configuredMode = mode; }
namespace WifiManager { void checkResetButton() { ++resetCalls; } }
void setupButton() {
''' + block + r'''
}
int main() {
    BOARD = {0, true}; setupButton();
#ifdef OPENHOP_USB_ECM
    assert(configuredPin == 0 && configuredMode == INPUT_PULLUP);
    assert(resetCalls == 0);
    configuredPin = -1; BOARD = {-1, true}; setupButton();
    assert(configuredPin == -1 && resetCalls == 0);
    BOARD = {4, false}; setupButton();
    assert(configuredPin == 4 && configuredMode == INPUT_PULLDOWN);
#else
    assert(resetCalls == 1);
#endif
}
'''
with tempfile.TemporaryDirectory(prefix='ecm-button-', dir=os.environ.get('TMPDIR')) as d:
    source = Path(d) / 'test.cpp'
    source.write_text(harness)
    for flags in (['-DOPENHOP_USB_ECM'], []):
        exe = Path(d) / 'test'
        subprocess.run(['g++', '-std=c++17', *flags, str(source), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
print('USB ECM button GPIO initialization, disabled pin, polarity, normal reset path: PASS')
