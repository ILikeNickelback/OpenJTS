#include "hardware.h"
#include "config.h"
#include <Arduino.h>

void detection_trigger(SystemContext &c)
{
    GPIO_SET(TriggPin);
    delayMicroseconds(1);
    GPIO_CLR(TriggPin);

    ledcWrite(detectorPwmChannel, c.leds.detectorIntensity);
    delayMicroseconds(18);

    GPIO_SET(TriggPin);
    delayMicroseconds(1);
    GPIO_CLR(TriggPin);


    ledcWrite(detectorPwmChannel, 0);
}

void laser_trigger(SystemContext &c)
{
    GPIO_SET(laserChannel_open);
    delayMicroseconds(10);
    GPIO_CLR(laserChannel_open);

    delayMicroseconds(160);

    GPIO_SET(laserChannel_start);
    delayMicroseconds(10);
    GPIO_CLR(laserChannel_start);
}
