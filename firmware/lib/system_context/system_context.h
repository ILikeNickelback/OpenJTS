#ifndef SYSTEM_CONTEXT_H
#define SYSTEM_CONTEXT_H

#include "config.h"

// ---------- Machine d’état ----------
enum class SystemState
{
    IDLE,
    CONTINUES_FLASH,
    CONSTANT_LIGHT,
    SEQUENCE_ACQUISITION
};

// ---------- Structures ----------
struct SerialState
{
    char buffer[15001];
    bool inProgress = false;
    bool messageReady = false;
    int index = 0;
};

struct LedState
{
    // Defaults to full scale so an unconfigured detector LED (before any
    // 'S' command) behaves like it did at the old 4-bit resolution's
    // default of 16/15 (clipped to max).
    int detectorIntensity = max_amp_detector;
    int actinicPWM = 0;
    int currentActinicPWM = 0;
};

struct SystemContext
{
    SystemState state = SystemState::IDLE;
    SerialState serial;
    LedState leds;
    unsigned long flashIntervalMs = 200;
};

// ---------- Contexte global ----------
extern SystemContext ctx;

#endif
