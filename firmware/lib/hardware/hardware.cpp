#include "hardware.h"
#include "config.h"
#include <Arduino.h>
#include "esp_timer.h"

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

static void trigger_pulse()
{
    GPIO_SET(TriggPin);
    delayMicroseconds(triggerPulseUs);
    GPIO_CLR(TriggPin);
}

static void wait_until(int64_t t_us)
{
    while (esp_timer_get_time() < t_us)
    {
    }
}

// Detection flash (20 us) with its during-flash trigger 18 us in.
static void flash_with_trigger()
{
    // Detection flash: 20 us total
    GPIO_SET(detectorPin);
    delayMicroseconds(18);

    // During-flash trigger at t = 18 us, held until the flash ends
    GPIO_SET(TriggPin);
    delayMicroseconds(2);

    GPIO_CLR(detectorPin);
    GPIO_CLR(TriggPin);
}

void detection_trigger(SystemContext &c)
{
    // Pre-flash trigger pulse, then the flash itself
    trigger_pulse();
    flash_with_trigger();
}

// Fires `pointsBeforeFlash` pre-flash triggers followed by the detection
// flash, which starts at `flashStartUs` (esp_timer_get_time() clock). Blocks
// until the flash is done (~150 us with 3 pre-flash points).
void frequency_flash(int64_t flashStartUs, int pointsBeforeFlash)
{
    for (int i = 0; i < pointsBeforeFlash; i++)
    {
        wait_until(flashStartUs - preTriggerLeadUs -
                   (int64_t)(pointsBeforeFlash - 1 - i) * preTriggerSpacingUs);
        trigger_pulse();
    }
    wait_until(flashStartUs);
    flash_with_trigger();
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
