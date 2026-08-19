#include <Arduino.h>
#include "config.h"
#include "system_context.h"
#include "serial_comm.h"
#include "states.h"

// ---------- Contexte global ----------
SystemContext ctx;

void setup()
{
    Serial.begin(115200);

    pinMode(TriggPin, OUTPUT);
    pinMode(laserChannel_start, OUTPUT);
    pinMode(laserChannel_open, OUTPUT);

    // actinicDacPin uses dacWrite() — no channel attach needed.
    ledcSetup(detectorPwmChannel, detectorPwmFreq, detectorPwmResolution);
    ledcAttachPin(detectorDacPin, detectorPwmChannel);
}

void loop()
{
    readSerial(ctx.serial);

    switch (ctx.state)
    {
    case SystemState::IDLE:
        handleIdle(ctx);
        break;

    case SystemState::CONTINUES_FLASH:
        handleContinuesFlash(ctx);
        break;

    case SystemState::CONSTANT_LIGHT:
        handleConstantLight(ctx);
        break;

    case SystemState::SEQUENCE_ACQUISITION:
        handleSequence(ctx);
        break;
    }
}
