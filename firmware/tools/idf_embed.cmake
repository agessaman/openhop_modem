# pioarduino 53.03.13-1 imports IDF source lists but not this custom source
# generation edge into SCons. Generate the exact IDF assembly at configure
# time. This is not a fallback build: any missing input/generator is fatal.
execute_process(
    COMMAND "${CMAKE_COMMAND}" "-DDATA_FILE=${DATA_FILE}"
        "-DSOURCE_FILE=${SOURCE_FILE}" "-DFILE_TYPE=${FILE_TYPE}"
        -P "${IDF_PATH}/tools/cmake/scripts/data_file_embed_asm.cmake"
    COMMAND_ERROR_IS_FATAL ANY)
