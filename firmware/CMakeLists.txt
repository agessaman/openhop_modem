cmake_minimum_required(VERSION 3.16)
# Mixed Arduino/IDF target: explicitly retain only app + Arduino + PIO glue.
# Normal Arduino-only PlatformIO environments do not use this file.
add_compile_definitions(BOARD_HELTEC_V42_USB_ETH OPENHOP_USB_ECM=1
    ARDUINO_USB_MODE=1 ARDUINO_USB_CDC_ON_BOOT=0
    DEFAULT_FREQ=869618000 DEFAULT_BW=62500 DEFAULT_SF=8 DEFAULT_CR=8
    DEFAULT_POWER=22 DEFAULT_SYNCWORD=0x12 DEFAULT_PREAMBLE=16)
set(COMPONENTS src framework-arduinoespressif32 __pio_env)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(openhop_modem)

# Scoped to this mixed-framework project, not normal Arduino-only envs.
# Keep the upstream custom command too (native CMake/Ninja still uses it).
function(openhop_embed_certificate component certificate)
    idf_component_get_property(component_dir ${component} COMPONENT_DIR)
    set(DATA_FILE "${component_dir}/server_certs/${certificate}")
    set(SOURCE_FILE "${CMAKE_BINARY_DIR}/${certificate}.S")
    set(FILE_TYPE TEXT)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${DATA_FILE}")
    include("${CMAKE_CURRENT_SOURCE_DIR}/tools/idf_embed.cmake")
endfunction()
if(CONFIG_ESP_INSIGHTS_TRANSPORT_MQTT)
    openhop_embed_certificate(espressif__esp_insights mqtt_server.crt)
else()
    openhop_embed_certificate(espressif__esp_insights https_server.crt)
endif()
foreach(certificate rmaker_mqtt_server.crt rmaker_claim_service_server.crt rmaker_ota_server.crt)
    openhop_embed_certificate(espressif__esp_rainmaker ${certificate})
endforeach()
