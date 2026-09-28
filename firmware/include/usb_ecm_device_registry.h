#pragma once

#include <stddef.h>
#include <stdint.h>

// Supported CDC-ECM *devices*, not a promise that every adapter using the
// same chipset or USB class works on a particular board. Add tested entries
// here; keep USB-host capability, power, and recovery in the board/build.
struct OpenhopUsbEcmDevice {
    uint16_t vendorId;
    uint16_t productId;
    uint8_t configurationValue; // bConfigurationValue verified from descriptors
    const char* model;
};

static constexpr OpenhopUsbEcmDevice openhopUsbEcmDevices[] = {
    {0x0bda, 0x8153, 2, "Ubiquiti UACC-Adapter-PoE-USBC (RTL8153 ECM)"},
};
static constexpr size_t openhopUsbEcmDeviceCount =
    sizeof(openhopUsbEcmDevices) / sizeof(openhopUsbEcmDevices[0]);

// The host enumeration callback sees the device descriptor (and the number
// of configurations), not every configuration's interfaces. Never guess the
// ECM configuration for an unlisted device; inspect its descriptors first.
constexpr const OpenhopUsbEcmDevice* findOpenhopUsbEcmDevice(
        uint16_t vendorId, uint16_t productId, uint8_t configurationCount) {
    for (size_t i = 0; i < openhopUsbEcmDeviceCount; ++i) {
        const auto& device = openhopUsbEcmDevices[i];
        if (device.vendorId == vendorId && device.productId == productId &&
            device.configurationValue >= 1 &&
            device.configurationValue <= configurationCount) return &device;
    }
    return nullptr;
}
