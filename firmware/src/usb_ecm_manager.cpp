#include "usb_ecm_manager.h"
#if defined(OPENHOP_USB_ECM)
#include "usb_ecm_device_registry.h"
#include "sdkconfig.h"
#ifndef CONFIG_USB_HOST_ENABLE_ENUM_FILTER_CALLBACK
#error USB ECM requires IDF host enumeration filter to select RTL8153 configuration 2
#endif
#include <usb/usb_host.h>
#include <iot_usbh_cdc.h>
#include <iot_usbh_ecm.h>
#include <iot_eth.h>
#include <iot_eth_netif_glue.h>
#include <esp_netif.h>
#include <esp_event.h>
#include <esp_mac.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <cstdio>
#include <atomic>

namespace UsbEcmManager {
static esp_netif_t* netif = nullptr;
static iot_eth_driver_t* driver = nullptr;
static iot_eth_handle_t eth = nullptr;
static iot_eth_netif_glue_handle_t glue = nullptr;
static TaskHandle_t hostTask = nullptr;
static volatile bool hostInstalled = false;
static volatile bool linkUp = false;
static std::atomic<uint32_t> lastIP{0};
static std::atomic<uint32_t> invalidatedIP{0};
static char ipText[20] = "---";
static char macText[18] = "";
// One source of truth for admission and the configuration override. The last
// zeroed entry terminates the IDF driver's match list.
static usb_device_match_id_t matchIds[openhopUsbEcmDeviceCount + 1] = {};
static void populateMatchIds() {
    for (size_t i = 0; i < openhopUsbEcmDeviceCount; ++i) {
        matchIds[i].match_flags = USB_DEVICE_ID_MATCH_VID_PID;
        matchIds[i].idVendor = openhopUsbEcmDevices[i].vendorId;
        matchIds[i].idProduct = openhopUsbEcmDevices[i].productId;
    }
}

static bool selectConfiguration(const usb_device_desc_t* descriptor, uint8_t* value) {
    if (!descriptor || !value) return false;
    const auto* device = findOpenhopUsbEcmDevice(
        descriptor->idVendor, descriptor->idProduct,
        descriptor->bNumConfigurations);
    if (!device) return false;
    *value = device->configurationValue;
    return true;
}

static void hostEvents(void* arg) {
    const usb_host_config_t config = {
        .skip_phy_setup = false,
        .intr_flags = ESP_INTR_FLAG_LEVEL1,
        .enum_filter_cb = selectConfiguration,
    };
    const esp_err_t result = usb_host_install(&config);
    hostInstalled = result == ESP_OK;
    xTaskNotifyGive(static_cast<TaskHandle_t>(arg));
    if (!hostInstalled) { hostTask = nullptr; vTaskDelete(nullptr); return; }
    for (;;) {
        uint32_t flags = 0;
        if (usb_host_lib_handle_events(portMAX_DELAY, &flags) != ESP_OK) break;
    }
    hostTask = nullptr;
    vTaskDelete(nullptr);
}

static void onEth(void*, esp_event_base_t, int32_t event, void*) {
    if (event == IOT_ETH_EVENT_CONNECTED) linkUp = true;
    if (event == IOT_ETH_EVENT_DISCONNECTED || event == IOT_ETH_EVENT_STOP) {
        linkUp = false;
        const uint32_t previous = lastIP.exchange(0, std::memory_order_relaxed);
        if (previous) invalidatedIP.store(previous, std::memory_order_relaxed);
        ipText[0] = '-'; ipText[1] = '-'; ipText[2] = '-'; ipText[3] = 0;
    }
}

bool begin(const char* hostname, bool staticIP, const IPAddress& ip,
           const IPAddress& gateway, const IPAddress& subnet,
           const IPAddress& dns1, const IPAddress& dns2) {
    if (netif) return true;
    populateMatchIds();
    // Arduino initArduino() does not initialize networking. ECM must also work
    // without Wi-Fi; IDF 5.3.2 esp_netif_init() is safe after prior initialization.
    const esp_err_t netResult = esp_netif_init();
    if (netResult != ESP_OK) {
        Serial.printf("[USB ECM] esp_netif_init failed: %d\n", netResult);
        return false;
    }
    const esp_err_t eventResult = esp_event_loop_create_default();
    // INVALID_STATE means the shared default loop already exists, not a failure.
    if (eventResult != ESP_OK && eventResult != ESP_ERR_INVALID_STATE) {
        Serial.printf("[USB ECM] default event loop init failed: %d\n", eventResult);
        return false;
    }
    if (xTaskCreatePinnedToCore(hostEvents, "ecm_usb_host", 4096,
                                xTaskGetCurrentTaskHandle(), 5, &hostTask, 0) != pdPASS) return false;
    if (!ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(1500)) || !hostInstalled) {
        Serial.println("[USB ECM] host install failed");
        return false;
    }
    usbh_cdc_driver_config_t cdc = {};
    cdc.task_stack_size = 4096;
    cdc.task_priority = configMAX_PRIORITIES - 1;
    cdc.task_coreid = 0;
    cdc.skip_init_usb_host_driver = true;
    if (usbh_cdc_driver_install(&cdc) != ESP_OK) return false;
    iot_usbh_ecm_config_t config = { .match_id_list = matchIds };
    if (iot_eth_new_usb_ecm(&config, &driver) != ESP_OK || !driver) return false;
    iot_eth_config_t ethConfig = { .driver = driver, .stack_input = nullptr };
    if (iot_eth_install(&ethConfig, &eth) != ESP_OK) return false;
    esp_netif_inherent_config_t inherent = ESP_NETIF_INHERENT_DEFAULT_ETH();
    inherent.if_key = "OPENHOP_USB_ECM";
    inherent.if_desc = "RTL8153 ECM";
    esp_netif_config_t netConfig = { .base = &inherent, .driver = nullptr,
                                      .stack = ESP_NETIF_NETSTACK_DEFAULT_ETH };
    netif = esp_netif_new(&netConfig);
    if (!netif) return false;
    if (hostname && *hostname) esp_netif_set_hostname(netif, hostname);
    glue = iot_eth_new_netif_glue(eth);
    if (!glue || esp_netif_attach(netif, glue) != ESP_OK) return false;
    if (staticIP) {
        esp_netif_dhcpc_stop(netif);
        esp_netif_ip_info_t info = {};
        info.ip.addr = (uint32_t)ip;
        info.gw.addr = (uint32_t)gateway;
        info.netmask.addr = (uint32_t)subnet;
        if (esp_netif_set_ip_info(netif, &info) != ESP_OK) return false;
        esp_netif_dns_info_t dns = {};
        dns.ip.type = ESP_IPADDR_TYPE_V4;
        dns.ip.u_addr.ip4.addr = (uint32_t)dns1;
        esp_netif_set_dns_info(netif, ESP_NETIF_DNS_MAIN, &dns);
        dns.ip.u_addr.ip4.addr = (uint32_t)dns2;
        esp_netif_set_dns_info(netif, ESP_NETIF_DNS_BACKUP, &dns);
    }
    esp_event_handler_register(IOT_ETH_EVENT, ESP_EVENT_ANY_ID, onEth, nullptr);
    if (iot_eth_start(eth) != ESP_OK) return false;
    return true;
}
void loop() {
    if (!netif || !linkUp) return;
    esp_netif_ip_info_t info = {};
    if (esp_netif_get_ip_info(netif, &info) == ESP_OK) {
        const uint32_t current = info.ip.addr;
        const uint32_t previous = lastIP.exchange(current, std::memory_order_relaxed);
        if (previous && previous != current)
            invalidatedIP.store(previous, std::memory_order_relaxed);
    }
    if (info.ip.addr) {
        IPAddress ip(info.ip.addr);
        snprintf(ipText, sizeof(ipText), "%s", ip.toString().c_str());
    }
    uint8_t mac[6];
    if (esp_netif_get_mac(netif, mac) == ESP_OK)
        snprintf(macText, sizeof(macText), "%02X:%02X:%02X:%02X:%02X:%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}
uint32_t consumeInvalidation() {
    return invalidatedIP.exchange(0, std::memory_order_relaxed);
}
bool isLinkUp() { return linkUp; }
bool hasIP() { return linkUp && localIP() != IPAddress((uint32_t)0); }
const char* getIPString() { return hasIP() ? ipText : "---"; }
const char* getMACString() { return macText; }
static IPAddress fromInfo(int which) {
    if (!netif || !linkUp) return IPAddress((uint32_t)0);
    esp_netif_ip_info_t info = {};
    if (esp_netif_get_ip_info(netif, &info) != ESP_OK) return IPAddress((uint32_t)0);
    return IPAddress(which == 0 ? info.ip.addr : which == 1 ? info.netmask.addr : info.gw.addr);
}
IPAddress localIP() { return fromInfo(0); }
IPAddress subnetMask() { return fromInfo(1); }
IPAddress gatewayIP() { return fromInfo(2); }
IPAddress dnsIP(int index) {
    if (!netif) return IPAddress((uint32_t)0);
    esp_netif_dns_info_t dns = {};
    return esp_netif_get_dns_info(netif, index ? ESP_NETIF_DNS_BACKUP : ESP_NETIF_DNS_MAIN,
                                  &dns) == ESP_OK ? IPAddress(dns.ip.u_addr.ip4.addr)
                                                   : IPAddress((uint32_t)0);
}
}
#endif
