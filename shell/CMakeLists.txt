include(FetchContent)

# SDL3. A Linux distribution ships one built against its own PipeWire and
# Wayland, so use it when it is there -- the pinned tarball's PipeWire backend
# no longer compiles with current GCC. Elsewhere SDL is fetched and linked
# static: no DLL juggling in the build tree.
if(NOT WIN32)
    find_package(SDL3 CONFIG QUIET)
endif()
if(TARGET SDL3::SDL3)
    set(OPENMAC_SDL_TARGET SDL3::SDL3)
else()
    set(SDL_SHARED OFF CACHE BOOL "" FORCE)
    set(SDL_STATIC ON CACHE BOOL "" FORCE)
    set(SDL_TEST_LIBRARY OFF CACHE BOOL "" FORCE)
    set(SDL_TESTS OFF CACHE BOOL "" FORCE)
    set(SDL_EXAMPLES OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(SDL3
        URL https://github.com/libsdl-org/SDL/archive/refs/tags/release-3.2.0.tar.gz
        SYSTEM
    )
    FetchContent_MakeAvailable(SDL3)
    set(OPENMAC_SDL_TARGET SDL3::SDL3-static)
endif()

FetchContent_Declare(imgui
    URL https://github.com/ocornut/imgui/archive/refs/tags/v1.91.8.tar.gz
)
FetchContent_MakeAvailable(imgui)

add_library(imgui_lib STATIC
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/imgui_demo.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_sdl3.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_sdlrenderer3.cpp
)
target_include_directories(imgui_lib SYSTEM PUBLIC ${imgui_SOURCE_DIR} ${imgui_SOURCE_DIR}/backends)
target_link_libraries(imgui_lib PUBLIC ${OPENMAC_SDL_TARGET})

add_executable(openmac WIN32
    src/main.cpp
)
if(WIN32)
    target_sources(openmac PRIVATE openmac.rc)   # embeds the app icon
endif()
target_link_libraries(openmac PRIVATE openmac_core imgui_lib ${OPENMAC_SDL_TARGET} openmac_warnings)
