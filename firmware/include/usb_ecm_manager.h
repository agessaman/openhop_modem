#pragma once
#include <Arduino.h>
#include <IPAddress.h>

namespace UsbEcmManager {
// USB host uses the OTG pins; UART0, not native USB CDC, is the debug path.
// Initializes the shared IP stack and default event loop without starting Wi-Fi.
bool begin(const char* hostname, bool useStaticIP, const IPAddress& ip,
           const IPAddress& gateway, const IPAddress& subnet,
           const IPAddress& dns1, const IPAddress& dns2);
void loop();
// Main-loop-only consumer: drop a TCP session bound to the prior ECM address.
uint32_t consumeInvalidation();
bool isLinkUp();
bool hasIP();
const char* getIPString();
const char* getMACString();
IPAddress localIP();
IPAddress subnetMask();
IPAddress gatewayIP();
IPAddress dnsIP(int index);
}
