# Contributing USB Ethernet device support

This is the contribution contract for [USB Ethernet modem-tcp issue #75](https://github.com/openhop-dev/openhop_modem/issues/75). The initial implementation deliberately supports **one board build and one adapter**: `heltec_v42_usb_eth` on Heltec WiFi LoRa 32 V4.2, using the Ubiquiti UACC-Adapter-PoE-USBC with USB ID `0bda:8153` and CDC-ECM configuration value 2. The ordinary `heltec_v42` Wi-Fi build remains separate. A Linux laptop accepting a device is **not** proof the ESP32-S3 can host it.

## Boundaries

- `include/usb_ecm_device_registry.h` is the reviewed adapter admission list. Each row contains an exact VID:PID, a descriptor-confirmed `bConfigurationValue`, and a human-readable model. `src/usb_ecm_manager.cpp` uses this **same list** to build the ECM driver's match IDs and to select the USB configuration. Unknown devices remain unsupported; don't add a wildcard entry based only on the chip family.
- The registry is for devices presenting a compliant **CDC-ECM** function at the selected configuration. A vendor-specific USB Ethernet protocol or CDC-NCM needs a **separate driver/backend** and tests. A USB-C power/data splitter or PoE injector doesn't automatically provide a usable host connection.
- A device-list addition is not a board addition. Host role, power budget, USB pins/PHY, boot/debug access, RF pin policy, Wi-Fi fallback, OTA/partition layout, and TCP/HTTP exposure must be assessed per board. For the first build, the V4.2 native USB connector is occupied by host mode, while UART0 and ESP ROM download mode remain separate recovery considerations.
- ESP32-S3's native USB host is full-speed, regardless of a dongle's advertised gigabit speed. Throughput isn't the LoRa bottleneck; enumeration, power, and reliability are.
- There is no generic ECM auto-admission yet. The ESP-IDF enumeration filter used here sees only the **device descriptor** and cannot discover another adapter's ECM configuration by scanning all configurations. A PR must provide descriptors and an exact selection before adding a row. Do not apply the UniFi configuration-2 rule to unknown devices.

## Adapter PR evidence

1. State the exact board revision, adapter vendor/model/hardware revision, USB VID:PID, how each side is powered, and whether a hub or USB-C role/PD hardware is involved. Attach or quote the USB device/configuration/interface/endpoint descriptors (for example `lsusb -v -d VID:PID` from Linux), including the selected `bConfigurationValue`, ECM control/data interfaces, and any non-ECM configurations. Do not include serial numbers or credentials.
2. Show the board's actual host-mode and power arrangement; verify native USB bootloader/serial recovery **before** OTA. This Ethernet-only experiment has no Wi-Fi recovery; require physical board access and a verified ROM-bootloader/serial recovery path while trying a new device. Do not change the known-good Wi-Fi build's USB behavior.
3. Add the exact registry row and a targeted selector/negative test. Run `python3 tools/test_heltec_v42_usb_ecm.py` and `python3 tools/test_usb_ecm_ota_sanity.py`. A row alone is a *candidate*, not a compatibility claim.
4. Build the exact board environment, check the app fits and the OTA partition table matches the installed device. The pinned mixed-framework build currently needs the CMake workaround in `USB_ECM_EXPERIMENT.md`; never mistake an SCons failure for a successful firmware image. Test an adjacent Wi-Fi-only build for regression.
5. On the physical board, record USB enumeration at its actual speed, selected configuration, link and DHCP address, authenticated modem TCP on port 5055, HTTP management/OTA without Wi-Fi, adapter unplug/replug with a connected TCP client, absence of Wi-Fi STA/AP even with saved credentials, and a controlled reboot **after OTA sanity**. Report what did not work as clearly as what worked. No password, token, MAC/serial tied to a person, or private network diagram in a public PR.
6. For a new board, add a separate PlatformIO environment, board revision/RF pin policy, verified partition/recovery path, and board-specific tests. Do not infer USB host support merely because the chip is ESP32-S3 or the connector supplies power.

## Promotion out of experiment

`platformio.ini` marks `heltec_v42_usb_eth` with `custom_release = false`.
Both the asset builder and release packager use that flag, so this prototype
cannot silently enter a public ZIP or browser flasher. Remove it only when
the ordinary or explicitly supported mixed-framework builder produces complete
checksummed bootloader/partition/app/factory assets, release packaging and
flasher selection include the exact target, and a controlled post-OTA reboot
and recovery have been verified on hardware. Adding another device row does
not by itself satisfy those gates.

The first UniFi trial reached a network address and HTTP/TCP services over the adapter while Wi-Fi remained available, but a persistent post-power-cycle result must be verified separately. Nothing here promises all RTL8153 products, ECM devices, or NCM adapters.
