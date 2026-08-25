#include "hardware.h"
#include "config.h"
#include <Arduino.h>

void detection_trigger(SystemContext &c)
{
    GPIO_SET(TriggPin);
    delayMicroseconds(2);
    GPIO_CLR(TriggPin);

    GPIO_SET(detectorDacPin);
    delayMicroseconds(18);

    GPIO_SET(TriggPin);
    delayMicroseconds(2);
    GPIO_CLR(TriggPin);


    GPIO_CLR(detectorDacPin);
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
