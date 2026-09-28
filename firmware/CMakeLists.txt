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
