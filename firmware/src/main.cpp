#include <Arduino.h>
#include "config.h"
#include "system_context.h"
#include "serial_comm.h"
#include "states.h"
#include "hardware.h"

// ---------- Contexte global ----------
SystemContext ctx;

void setup()
{
    Serial.begin(115200);

    pinMode(TriggPin, OUTPUT);
    pinMode(laserChannel_start, OUTPUT);
    pinMode(laserChannel_open, OUTPUT);
    pinMode(detectorPin, OUTPUT);

    // Max out pad drive strength on the pulse pins so their edges stay sharp
    // even when rail voltage sags under the actinic LED's current draw.
    gpio_set_drive_capability((gpio_num_t)TriggPin, GPIO_DRIVE_CAP_3);
    gpio_set_drive_capability((gpio_num_t)laserChannel_start, GPIO_DRIVE_CAP_3);
    gpio_set_drive_capability((gpio_num_t)laserChannel_open, GPIO_DRIVE_CAP_3);
    gpio_set_drive_capability((gpio_num_t)detectorPin, GPIO_DRIVE_CAP_3);

    // Force both LED pins to a true 0V immediately on every boot/reset
    // (including the reset triggered by the host opening/closing the serial
    // port), instead of leaving them floating until the first command arrives.
    writeActinicLevel(0);
    GPIO_CLR(detectorPin);
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

    case SystemState::FREQUENCY_ACQUISITION:
        handleFrequency(ctx);
        break;
    }
}
