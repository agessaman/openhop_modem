#!/usr/bin/env python3
"""Compile the complete production USB ECM translation unit against recording IDF stubs.
No extracted/reimplemented begin(), Wi-Fi, hardware, or scheduler emulation.
"""
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
STUB = r'''
#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <cassert>
#include <iostream>
using std::string;
inline std::vector<string> calls;
inline int netResult=0, eventResult=0;
inline bool ready=false, events=false;
inline void record(const char* s){calls.emplace_back(s);}
using esp_err_t=int;
constexpr int ESP_OK=0, ESP_FAIL=-1, ESP_ERR_INVALID_STATE=259;
inline esp_err_t esp_netif_init(){record("netinit"); if(netResult==0) ready=true; return netResult;}
inline esp_err_t esp_event_loop_create_default(){record("eventinit"); assert(ready); if(eventResult==0 || eventResult==ESP_ERR_INVALID_STATE) events=true; return eventResult;}
struct IPAddress { uint32_t v; IPAddress(uint32_t n=0):v(n){} operator uint32_t()const{return v;} string toString()const{return "192.0.2.2";} };
struct {void println(const char*){} template<class... A> void printf(const char*,A...){} } Serial;
using esp_event_base_t=int;
constexpr int ESP_INTR_FLAG_LEVEL1=1, IOT_ETH_EVENT_CONNECTED=1,IOT_ETH_EVENT_DISCONNECTED=2,IOT_ETH_EVENT_STOP=3,IOT_ETH_EVENT=4,ESP_EVENT_ANY_ID=-1;
struct usb_device_desc_t{uint16_t idVendor,idProduct; uint8_t bNumConfigurations;};
struct usb_device_match_id_t{int match_flags; uint16_t idVendor,idProduct;};
constexpr int USB_DEVICE_ID_MATCH_VID_PID=1;
struct usb_host_config_t{bool skip_phy_setup; int intr_flags; bool(*enum_filter_cb)(const usb_device_desc_t*,uint8_t*);};
inline int usb_host_install(const usb_host_config_t*){record("usb_install"); assert(ready && events);return 0;}
inline int usb_host_lib_handle_events(int,uint32_t*){return -1;}
using TaskHandle_t=void*;
constexpr int pdPASS=1,pdTRUE=1,portMAX_DELAY=-1,configMAX_PRIORITIES=25;
#define pdMS_TO_TICKS(x) (x)
inline TaskHandle_t xTaskGetCurrentTaskHandle(){return nullptr;}
inline void xTaskNotifyGive(TaskHandle_t){} inline void vTaskDelete(TaskHandle_t){}
inline int xTaskCreatePinnedToCore(void(*fn)(void*),const char*,int,void* arg,int,TaskHandle_t*,int){record("host_task"); assert(ready && events);fn(arg);return pdPASS;}
inline int ulTaskNotifyTake(int,int){return 1;}
struct usbh_cdc_driver_config_t{int task_stack_size,task_priority,task_coreid;bool skip_init_usb_host_driver;};
inline int usbh_cdc_driver_install(const usbh_cdc_driver_config_t*){record("cdc");return 0;}
struct iot_eth_driver_t{}; using iot_eth_handle_t=void*;using iot_eth_netif_glue_handle_t=void*;
struct iot_usbh_ecm_config_t{usb_device_match_id_t* match_id_list;};
inline int iot_eth_new_usb_ecm(const iot_usbh_ecm_config_t*,iot_eth_driver_t** d){static iot_eth_driver_t driver;*d=&driver;record("ecm");return 0;}
struct iot_eth_config_t{iot_eth_driver_t* driver;void* stack_input;};
inline int iot_eth_install(const iot_eth_config_t*,iot_eth_handle_t* e){*e=(void*)1;record("eth_install");return 0;}
struct esp_netif_t{};
struct esp_netif_inherent_config_t{const char* if_key;const char* if_desc;};
#define ESP_NETIF_INHERENT_DEFAULT_ETH() esp_netif_inherent_config_t{}
#define ESP_NETIF_NETSTACK_DEFAULT_ETH nullptr
struct esp_netif_config_t{esp_netif_inherent_config_t* base;void* driver;void* stack;};
inline esp_netif_t* esp_netif_new(const esp_netif_config_t*){assert(ready && events);static esp_netif_t n;record("netif");return &n;}
inline int esp_netif_set_hostname(esp_netif_t*,const char*){return 0;}
inline iot_eth_netif_glue_handle_t iot_eth_new_netif_glue(iot_eth_handle_t){record("glue");assert(events);return (void*)1;}
inline int esp_netif_attach(esp_netif_t*,void*){record("attach");return 0;}
struct ip4{uint32_t addr;}; struct esp_netif_ip_info_t{ip4 ip,gw,netmask;};
struct esp_netif_dns_info_t{struct {int type;struct {struct ip4 ip4;}u_addr;}ip;};
constexpr int ESP_IPADDR_TYPE_V4=0,ESP_NETIF_DNS_MAIN=0,ESP_NETIF_DNS_BACKUP=1;
inline int esp_netif_dhcpc_stop(esp_netif_t*){return 0;}
inline int esp_netif_set_ip_info(esp_netif_t*,const esp_netif_ip_info_t*){return 0;}
inline int esp_netif_set_dns_info(esp_netif_t*,int,const esp_netif_dns_info_t*){return 0;}
inline int esp_netif_get_ip_info(esp_netif_t*,esp_netif_ip_info_t*){return 0;}
inline int esp_netif_get_dns_info(esp_netif_t*,int,esp_netif_dns_info_t*){return 0;}
inline int esp_netif_get_mac(esp_netif_t*,uint8_t*){return -1;}
inline int esp_event_handler_register(int,int,void(*)(void*,int,int32_t,void*),void*){record("handler");assert(events);return 0;}
inline int iot_eth_start(iot_eth_handle_t){record("start");return 0;}
'''
MAIN = r'''
#include "usb_ecm_manager.cpp"
int main(int argc,char** argv){
 string mode=argc>1?argv[1]:"cold";
 if(mode=="existing") {ready=events=true;eventResult=ESP_ERR_INVALID_STATE;}
 if(mode=="netfail") netResult=ESP_FAIL;
 if(mode=="netinvalid") netResult=ESP_ERR_INVALID_STATE;
 if(mode=="eventfail") eventResult=ESP_FAIL;
 bool ok=UsbEcmManager::begin("test",false,{},{},{},{},{});
 if(mode=="netfail" || mode=="netinvalid") {assert(!ok);assert((calls==std::vector<string>{"netinit"}));}
 else if(mode=="eventfail") {assert(!ok);assert((calls==std::vector<string>{"netinit","eventinit"}));}
 else {
  assert(ok);
  assert((calls==std::vector<string>{"netinit","eventinit","host_task","usb_install","cdc","ecm","eth_install","netif","glue","attach","handler","start"}));
  auto before=calls;assert(UsbEcmManager::begin("test",false,{},{},{},{},{}));assert(calls==before);
 }
 if(!ok) {
  calls.clear();netResult=eventResult=ESP_OK;
  assert(UsbEcmManager::begin("retry",false,{},{},{},{},{}));
  assert(calls.front()=="netinit" && calls.back()=="start");
 }
 for(auto& call:calls) std::cout<<call<<" "; std::cout<<"PASS "<<mode<<"\n";
}
'''
with tempfile.TemporaryDirectory(prefix='ecm-network-init-') as tmp:
    tmp = Path(tmp)
    (tmp/'stubs.h').write_text(STUB)
    for name in ['Arduino.h','IPAddress.h','usb/usb_host.h','iot_usbh_cdc.h','iot_usbh_ecm.h','iot_eth.h','iot_eth_netif_glue.h','esp_netif.h','esp_event.h','esp_mac.h','freertos/FreeRTOS.h','freertos/task.h']:
        p = tmp/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('#include "stubs.h"\n')
    (tmp/'sdkconfig.h').write_text('#define CONFIG_USB_HOST_ENABLE_ENUM_FILTER_CALLBACK 1\n')
    (tmp/'main.cpp').write_text(MAIN)
    exe=tmp/'test'
    subprocess.run(['c++','-std=c++17','-DOPENHOP_USB_ECM','-I'+str(tmp),'-I'+str(ROOT/'include'),'-I'+str(ROOT/'src'),str(tmp/'main.cpp'),'-o',str(exe)],check=True)
    for mode in sys.argv[1:] or ['cold', 'existing', 'netfail', 'netinvalid', 'eventfail']:
        subprocess.run([str(exe),mode],check=True)
