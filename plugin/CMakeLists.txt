cmake_minimum_required(VERSION 3.22)
project(ValhallaClonePack VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(MSVC)
    # static runtime: the .vst3 does not need the VC++ redistributable
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

# Use a local JUCE checkout with -DJUCE_DIR=..., otherwise download it.
if(JUCE_DIR)
    add_subdirectory(${JUCE_DIR} juce EXCLUDE_FROM_ALL)
else()
    include(FetchContent)
    FetchContent_Declare(JUCE GIT_REPOSITORY https://github.com/juce-framework/JUCE.git GIT_TAG 8.0.4 GIT_SHALLOW TRUE)
    FetchContent_MakeAvailable(JUCE)
endif()

option(VC_COPY_PLUGINS "Install plug-ins into the system VST3 folder after building" OFF)

function(vc_add_effect target effect product code)
    juce_add_plugin(${target}
        COMPANY_NAME "VC Audio"
        PLUGIN_MANUFACTURER_CODE Vcau
        PLUGIN_CODE ${code}
        PRODUCT_NAME "${product}"
        FORMATS VST3
        IS_SYNTH FALSE
        NEEDS_MIDI_INPUT FALSE
        NEEDS_MIDI_OUTPUT FALSE
        VST3_CATEGORIES Fx Reverb
        COPY_PLUGIN_AFTER_BUILD ${VC_COPY_PLUGINS})
    target_sources(${target} PRIVATE src/PluginProcessor.cpp)
    target_include_directories(${target} PRIVATE src)
    target_compile_definitions(${target} PRIVATE
        VC_EFFECT=${effect}
        JUCE_WEB_BROWSER=0 JUCE_USE_CURL=0 JUCE_VST3_CAN_REPLACE_VST2=0
        JUCE_DISPLAY_SPLASH_SCREEN=0)
    target_link_libraries(${target} PRIVATE
        juce::juce_audio_utils juce::juce_dsp
        juce::juce_recommended_config_flags juce::juce_recommended_lto_flags juce::juce_recommended_warning_flags)
endfunction()

vc_add_effect(VCVintageVerb  VintageVerbFx  "VC VintageVerb"  Vcvv)
vc_add_effect(VCRoom         RoomFx         "VC Room"         Vcrm)
vc_add_effect(VCPlate        PlateFx        "VC Plate"        Vcpl)
vc_add_effect(VCShimmer      ShimmerFx      "VC Shimmer"      Vcsh)
vc_add_effect(VCSupermassive SupermassiveFx "VC Supermassive" Vcsm)
vc_add_effect(VCDelay        DelayFx        "VC Delay"        Vcdl)
vc_add_effect(VCFreqEcho     FreqEchoFx     "VC Freq Echo"    Vcfe)
vc_add_effect(VCSpaceMod     SpaceModFx     "VC Space Mod"    Vcsp)
vc_add_effect(VCUberMod      UberModFx      "VC UberMod"      Vcub)

# Offline self-test of every engine (no JUCE needed).
add_executable(vc_selftest tests/selftest.cpp)
target_include_directories(vc_selftest PRIVATE src)
