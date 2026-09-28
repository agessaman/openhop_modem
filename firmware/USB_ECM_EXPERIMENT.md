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

## Supported clean build and packaging

From the repository root, use this **single canonical command** (choose a new,
absolute output directory outside the checkout):

```sh
python3 firmware/tools/build_firmware_assets.py \
  --variant heltec_v42_usb_eth --allow-experimental --clean \
  --pio "$HOME/.local/bin/pio" \
  --output-dir "$HOME/openhop-dev/firmware-test-artifacts/heltec-v42-usb-ecm-supported-build"
```

The package is written under `<output-dir>/heltec_v42_usb_eth/`. Existing
packages are refused rather than replaced. `--allow-experimental` applies only
to explicitly named targets: `all`, `auto`, and the public release ZIP packager
still exclude this `custom_release=false` environment. Normal `heltec_v42`
build and release behavior is unchanged.

Outputs:
- `firmware.bin`: **app-only OTA**, or serial app image at `0x10000`.
- `firmware.factory.bin`: **factory/recovery image at `0x0`, never HTTP OTA**.
- `bootloader.bin`, `partitions.bin`, `ota_data_initial.bin`: components at
  `0x0`, `0x8000`, `0xe000`; manifest includes all four components.
- `manifest.json`, `SHA256SUMS.txt`, `build-info.json`, SDK config, dependency
  lock, CMake project description, build command and full PlatformIO log.

**Factory recovery resets OTA selection and can erase NVS/configuration** through
its `0xff` padding. The runtime's non-erasing behavior does not make a factory
flash configuration-preserving. App-only OTA requires an already compatible
bootloader and partition table. Physical flash may be 16 MB, but this target
intentionally retains its **8 MB configured layout**: `app0=0x10000`,
`app1=0x340000`, both `0x330000` bytes. Packaging validates the generated table,
fit, component offsets and flash settings. It constructs a fresh factory image
from the successful PIO outputs; it never trusts an old merged image.

`build-info.json` uses the app SHA256 as the unique build ID and records the ELF
hash and a file-by-file source digest. Git revision is null for source exports;
a revision alone cannot identify dirty worktree content. Runtime version text
is not a unique build identifier. `idf-flasher-args.json` preserves CMake's
original names, not staged filenames; use `manifest.json` for staged offsets.
Verify the package with `sha256sum -c SHA256SUMS.txt` from inside its directory.

### Why fresh PlatformIO builds now work

The pinned pioarduino **53.03.13-1 / Arduino 3.1.3 / IDF 5.3.2** SCons importer
omits IDF custom generation edges for the Insights HTTPS and three RainMaker
certificate assembly sources. Project-local CMake now invokes IDF's exact
embedding generator at configure time, with fatal error propagation and input
change dependencies. It does not patch installed frameworks, ignore build errors,
or fall back from arbitrary failures to CMake. Plain `pio run -e
heltec_v42_usb_eth` produces `.pio/build/heltec_v42_usb_eth/firmware.bin`.
The asset tool additionally creates the IDF-equivalent blank 8 KiB OTA-data
component, since SCons does not run IDF's `blank_ota_data` target. The dedicated
environment explicitly sets `board_build.partitions` to the same custom CSV as
IDF's SDK defaults: without it SCons emits a default single 1 MB factory-app
table even though CMake configured dual OTA. Packaging rejects that mismatch.

Use an isolated PlatformIO Python installation; do not bypass PEP 668 or install
into system Python. Some existing pioarduino installations print nonfatal Python
install warnings; only a zero PIO exit status allows packaging. Local validation
uses cached toolchains/downloads, not a completely package-cold installation.
For a fresh-project check, use a source-only checkout/export with no `.pio`,
`managed_components`, or generated `sdkconfig.heltec_v42_usb_eth`; retain tracked
`sdkconfig.defaults`. `--clean` alone cleans build outputs, not all dependencies.

Focused host tests (from `firmware/`):

```sh
python3 tools/test_experimental_assets.py
python3 tools/test_idf_embed.py
python3 tools/test_usb_ecm_network_init.py
python3 tools/test_usb_ecm_button_init.py
python3 tools/test_usb_ecm_ethernet_only.py
python3 tools/test_usb_ecm_management_guards.py
python3 tools/test_usb_ecm_ota_sanity.py
python3 tools/test_heltec_v42_usb_ecm.py
python3 tools/test_usb_ecm_release_scope.py
```

These are build/packaging and host control-flow checks, not evidence of the
installed device's partition layout, RF operation, or physical recovery.

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
