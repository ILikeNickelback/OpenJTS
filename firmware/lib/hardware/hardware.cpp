#include "hardware.h"
#include "config.h"
#include <Arduino.h>

// The ESP32 DAC has a non-zero floor voltage at code 0 (tens-to-hundreds of
// mV), which is enough to keep a sensitive LED driver visibly lit. Disabling
// the DAC channel and driving the pin as a plain digital output forces a
// true 0V for the 0% case.
void writeDacLevel(uint8_t pin, dac_channel_t channel, int value)
{
    if (value <= 0)
    {
        dac_output_disable(channel);
        pinMode(pin, OUTPUT);
        digitalWrite(pin, LOW);
    }
    else
    {
        dacWrite(pin, value);
    }
}

void detection_trigger(SystemContext &c)
{
    GPIO_SET(TriggPin);
    delayMicroseconds(2);
    GPIO_CLR(TriggPin);

    writeDacLevel(detectorDacPin, DAC_CHANNEL_1, c.leds.detectorIntensity);
    delayMicroseconds(18);

    GPIO_SET(TriggPin);
    delayMicroseconds(2);
    GPIO_CLR(TriggPin);

    writeDacLevel(detectorDacPin, DAC_CHANNEL_1, 0);
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
