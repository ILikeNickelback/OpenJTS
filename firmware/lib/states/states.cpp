#include "states.h"
#include "hardware.h"
#include "config.h"
#include <Arduino.h>
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include "driver/dac.h"

// ---------- Utilitaires locaux ----------
static int extractInt(const char *seq)
{
    return atoi(seq);
}

static float extractFloat(const char *seq)
{
    return atof(seq);
}

// The ESP32 DAC (actinicDacPin/GPIO26 = DAC_CHANNEL_2) has a non-zero floor
// voltage at code 0 (tens-to-hundreds of mV), which is enough to keep a
// sensitive actinic LED driver visibly lit. Disabling the DAC channel and
// driving the pin as a plain digital output forces a true 0V for the 0% case.
static void writeActinicLevel(int value)
{
    if (value <= 0)
    {
        dac_output_disable(DAC_CHANNEL_2);
        pinMode(actinicDacPin, OUTPUT);
        digitalWrite(actinicDacPin, LOW);
    }
    else
    {
        dacWrite(actinicDacPin, value);
    }
}

// ---------- États ----------
void handleIdle(SystemContext &c)
{
    if (!c.serial.messageReady)
        return;

    char cmd = c.serial.buffer[0];

    if (cmd == continuesMarker)
    {
        int interval = extractInt(c.serial.buffer + 1);
        if (interval > 0)
            c.flashIntervalMs = interval;
        c.state = SystemState::CONTINUES_FLASH;
    }
    else if (cmd == constantLightMarker_on)
        c.state = SystemState::CONSTANT_LIGHT;
    else if (isdigit(cmd))
        c.state = SystemState::SEQUENCE_ACQUISITION;

    c.serial.messageReady = false;
}

void handleContinuesFlash(SystemContext &c)
{
    detection_trigger(c);
    delay(c.flashIntervalMs);

    if (c.serial.messageReady && c.serial.buffer[0] == set_LED_intensity)
    {
        float pct = extractFloat(c.serial.buffer + 1);
        c.leds.detectorIntensity = round(max_amp_detector * pct / 100.0);
        Serial.print("Intensity = ");
        Serial.println(c.leds.detectorIntensity);
        c.serial.messageReady = false;
    }

    if (c.serial.messageReady && c.serial.buffer[0] != continuesMarker)
    {
        c.state = SystemState::IDLE;
    }
}

void handleConstantLight(SystemContext &c)
{
    float offset = extractFloat(c.serial.buffer + 1);
    c.leds.currentActinicPWM = round(max_amp_actinic * offset / 100.0);
    writeActinicLevel(c.leds.currentActinicPWM);
    c.state = SystemState::IDLE;
}

void handleSequence(SystemContext &c)
{
    const char *s = c.serial.buffer;

    while (*s)
    {
        if (*s == 'D')
        {
            detection_trigger(c);
            s++;
        }
        else if (*s == 'L')
        {
            laser_trigger(c);
            s++;
        }
        else if (isdigit(*s) || *s == '.')
        {
            float val = atof(s);
            while (isdigit(*s) || *s == '.')
                s++;

            if (*s == '!')
            {
                writeActinicLevel(round(max_amp_actinic * val / 100.0));
                s++;
            }
            else
            { 
                delayMicroseconds(val * 1000);
                
            }
        }
        else
        {
            s++;
        }
    }

    writeActinicLevel(c.leds.currentActinicPWM);
    c.state = SystemState::IDLE;
}
