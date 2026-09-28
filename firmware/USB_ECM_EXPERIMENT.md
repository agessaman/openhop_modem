# Experimental Heltec V4.2 Ethernet-only USB ECM image

Contributor/device support criteria: [USB_ECM_CONTRIBUTING.md](USB_ECM_CONTRIBUTING.md).

Environment: `heltec_v42_usb_eth` (ESP32-S3, 8 MB flash). It retains the
`heltec_v42` GC1109 GPIO2/7/46 RF policy and separate experimental identity.
**Do not use this image for V4.3. Standard `heltec_v42` is unchanged.**

## Ethernet-only policy and recovery

**Wi-Fi STA and setup AP are disabled, even with previously saved credentials.**
There is no Wi-Fi rescue, provisioning portal, or Wi-Fi reset control. Boot-time
PRG configuration erase and protocol Wi-Fi provisioning/reset are disabled for
this experiment so they cannot erase the retained management configuration.
Short PRG presses still control the display. Native USB on GPIO19/20 is a host,
not a USB-CDC modem or serial console; `Serial` is UART0.

NVS is not erased: hostname, TCP port/token, HTTP password, GPS and other saved
settings remain available. Saved Wi-Fi credentials remain stored but cannot
activate STA/AP. The existing LAN-only TCP service uses the saved port and token;
HTTP management and `/update` retain Basic authentication as `admin` with the
saved HTTP password. If never configured, existing default credentials still
apply: do not expose this experimental image to an untrusted network.

The host accepts only RTL8153 VID:PID `0bda:8153`, requiring at least two USB
configurations, and selects `bConfigurationValue=2` (the observed ECM mode).
ECM uses DHCP, not the saved Wi-Fi static address. Saved static-network settings
are retained but do not apply to this experiment's ECM startup; use a DHCP
reservation. HTTP/TCP start when Ethernet gets an address, including late
adapter attachment/DHCP after boot, with no dependency on Wi-Fi. No setup portal
competes for port 80. Wi-Fi power-save/setup controls are hidden.

**Physical recovery is mandatory if Ethernet does not come up.** Have physical
board access, a known-good recovery image, and an independently verified ROM
bootloader/serial recovery method before installation. Disconnect the USB host
adapter before changing USB roles. An app-only OTA image cannot install or repair
bootloader/partition tables. Do not assume native application USB-CDC remains
available or that a Wi-Fi reset button can rescue this build. No hardware access,
flashing, or OTA is part of compile-only validation.

## Build from `firmware/`

```sh
python3 tools/test_usb_ecm_network_init.py
python3 tools/test_usb_ecm_button_init.py
python3 tools/test_usb_ecm_ethernet_only.py
python3 tools/test_usb_ecm_management_guards.py
python3 tools/test_usb_ecm_ota_sanity.py
python3 tools/test_heltec_v42_usb_ecm.py
python3 tools/test_usb_ecm_release_scope.py
pio run -e heltec_v42_usb_eth
# Pinned pioarduino 53.03.13-1 fails SCons on generated
# espressif__esp_insights https_server.crt.S, after configuring IDF/CMake.
IDF_PATH="$HOME/.platformio/packages/framework-espidf" \
PATH="$HOME/.platformio/packages/toolchain-xtensa-esp-elf/bin:$PATH" \
cmake --build .pio/build/heltec_v42_usb_eth -j 6
# App-only image: .pio/build/heltec_v42_usb_eth/openhop_modem.bin
```

Use PlatformIO's isolated Python environment rather than installing dependencies
into a PEP-668-managed system Python. CMake requires `esptool>=4.8,<5` in
`~/.platformio/penv/.espidf-5.3.2/bin/python`. `pio run` alone does not produce
the mixed image. This environment is excluded from production release assets.

The custom table preserves `app0=0x10000` and `app1=0x340000`, each `0x330000`
bytes. App OTA requires a compatible installed partition layout. Local image
inspection and partition-fit checks do not verify the device's installed layout.

## OTA sanity and validation limits

The USB ECM fallback sanity condition is **continuous Ethernet IP plus initialized
radio for 120 seconds** after the OTA manager starts. A link/IP or radio-health
loss resets that observation. The existing valid-host-frame alternative remains;
failed validity writes are retried. Other builds retain their host-frame policy.
The generated mixed-IDF SDK config has bootloader rollback disabled; an app-only
update does not replace the installed bootloader. Do not assume automatic rollback
or its cancellation without a controlled hardware reboot test.

On one Heltec V4.2 / UniFi UACC PoE USB-C RTL8153 pair, the Ethernet-only
image completed authenticated HTTP OTA, remained reachable with increasing uptime
for over two minutes, and returned after a controlled software reboot. The radio
reported RX/Idle and the former Wi-Fi HTTP address no longer responded. These are
bounded runtime observations, not an RF scan proving absence of a setup AP.

Ethernet initializes ESP-NETIF and the default event loop independently of Wi-Fi.
The display button retains its input/pull initialization even though boot-time
configuration erase is disabled. Host regressions exercise both initialization
paths; physical confirmation of the display fix is still pending.

Still required: Wi-Fi association/AP inspection, late link/hotplug, authenticated
modem protocol traffic, OTA-state readback, controlled power-cycle persistence,
and sustained radio/PoE operation. Other adapters, power paths, board revisions
and NCM remain unsupported/unverified. This is not guaranteed Ethernet recovery.
