cmake_minimum_required(VERSION 3.16)
project(hub75_clock CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── rpi-rgb-led-matrix ────────────────────────────────────────────────────────
set(RGB_MATRIX_DIR "$ENV{HOME}/rpi-rgb-led-matrix" CACHE PATH "Path to rpi-rgb-led-matrix checkout")

add_library(rgb_matrix STATIC IMPORTED)
set_target_properties(rgb_matrix PROPERTIES
    IMPORTED_LOCATION ${RGB_MATRIX_DIR}/lib/librgbmatrix.a
)
target_include_directories(rgb_matrix INTERFACE
    ${RGB_MATRIX_DIR}/include
)

# ── Third-party dependencies ──────────────────────────────────────────────────
find_package(PkgConfig REQUIRED)
pkg_check_modules(MOSQUITTO REQUIRED libmosquitto)
pkg_check_modules(YAML_CPP REQUIRED yaml-cpp)

# nlohmann/json — header-only; prefer system install, fall back to FetchContent
find_package(nlohmann_json QUIET)
if(NOT nlohmann_json_FOUND)
    include(FetchContent)
    FetchContent_Declare(nlohmann_json
        URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
    )
    FetchContent_MakeAvailable(nlohmann_json)
endif()

# ── Source files ──────────────────────────────────────────────────────────────
file(GLOB ANIM_SOURCES CONFIGURE_DEPENDS src/animations/*.cpp)

add_executable(hub75_clock
    src/main.cpp
    src/Sensors.cpp
    src/Serial.cpp
    src/WeatherAnimator.cpp
    src/ThemeLoader.cpp
    src/CameoManager.cpp
    ${ANIM_SOURCES}
)

target_include_directories(hub75_clock PRIVATE
    include
    ${MOSQUITTO_INCLUDE_DIRS}
    ${YAML_CPP_INCLUDE_DIRS}
)

target_link_libraries(hub75_clock PRIVATE
    rgb_matrix
    nlohmann_json::nlohmann_json
    ${MOSQUITTO_LIBRARIES}
    ${YAML_CPP_LIBRARIES}
    pthread
    gpiod
)

target_compile_options(hub75_clock PRIVATE
    -Wall -Wextra -Wpedantic
    ${MOSQUITTO_CFLAGS_OTHER}
    ${YAML_CPP_CFLAGS_OTHER}
)

install(TARGETS hub75_clock RUNTIME DESTINATION bin)
