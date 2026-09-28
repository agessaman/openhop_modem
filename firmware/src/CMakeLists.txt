set(LIBDEPS "${CMAKE_CURRENT_LIST_DIR}/../.pio/libdeps/heltec_v42_usb_eth")
file(GLOB_RECURSE RADIO_SOURCES "${LIBDEPS}/RadioLib/src/*.cpp")
file(GLOB GFX_SOURCES "${LIBDEPS}/Adafruit GFX Library/*.cpp")
file(GLOB OLED_SOURCES "${LIBDEPS}/Adafruit SSD1306/*.cpp")
file(GLOB BUSIO_SOURCES "${LIBDEPS}/Adafruit BusIO/*.cpp")
file(GLOB APP_SOURCES "*.cpp")
idf_component_register(SRCS ${APP_SOURCES} ${RADIO_SOURCES} ${GFX_SOURCES}
    ${OLED_SOURCES} ${BUSIO_SOURCES}
    INCLUDE_DIRS "../include" "${LIBDEPS}/RadioLib/src"
    "${LIBDEPS}/ArduinoJson/src" "${LIBDEPS}/Adafruit GFX Library"
    "${LIBDEPS}/Adafruit SSD1306" "${LIBDEPS}/Adafruit BusIO"
    "../variants/heltec_wifi_lora_32_V4"
    REQUIRES framework-arduinoespressif32 usb esp_netif esp_event app_update
    espressif__iot_usbh_ecm espressif__iot_usbh_cdc espressif__iot_eth)
