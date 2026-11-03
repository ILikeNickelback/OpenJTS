#include "states.h"
#include "hardware.h"
#include "serial_comm.h"
#include "config.h"
#include <Arduino.h>
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include "esp_timer.h"

// ---------- Utilitaires locaux ----------
static int extractInt(const char *seq)
{
    return atoi(seq);
}

static float extractFloat(const char *seq)
{
    return atof(seq);
}

// Waits up to `total_us` microseconds, polling serial every millisecond so a
// stop command can interrupt a long sequence delay instead of being stuck
// behind a single uninterruptible delayMicroseconds() call.
// Returns true if a stop command arrived during the wait.
static bool waitAbortable(SystemContext &c, unsigned long total_us)
{
    const unsigned long CHUNK_US = 1000; // 1 ms
    while (total_us > CHUNK_US)
    {
        delayMicroseconds(CHUNK_US);
        total_us -= CHUNK_US;
        readSerial(c.serial);
        if (c.serial.messageReady && c.serial.buffer[0] == stopMarker)
            return true;
    }
    delayMicroseconds(total_us);
    return false;
}

void writeActinicLevel(int value)
{
    writeDacLevel(actinicDacPin, DAC_CHANNEL_2, value);
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
    else if (cmd == frequencyMarker)
        c.state = SystemState::FREQUENCY_ACQUISITION;
    else if (isdigit(cmd))
        c.state = SystemState::SEQUENCE_ACQUISITION;

    c.serial.messageReady = false;
}

void handleContinuesFlash(SystemContext &c)
{
    detection_trigger(c);
    delay(1000);

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
            else if (waitAbortable(c, (unsigned long)(val * 1000)))
            {
                c.serial.messageReady = false; // consume the stop command
                break;
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

// ---------- Frequency acquisition ----------
// Command: F<freq_hz>,<pre_periods>,<periods>,<post_periods>,<amplitude_pct>,
//           <offset_pct>,<background_pct>,<first_pulse_us>,<spacing_us>,
//           <pulse_count>,<points_before_flash>
// The host computes the pulse grid (and the matching time axis); the ESP32
// plays it back while modulating the actinic DAC with
//   amplitude * sin(2*pi*f*t + phase) + offset
// during the active periods and holding `background` during pre/post periods.
// `phase` makes the sine start at the background level, as in ADC mode.
struct FrequencyParams
{
    double freqHz;
    int prePeriods;
    int periods;
    int postPeriods;
    double amplitude;
    double offset;
    double background;
    double firstPulseUs;
    double spacingUs;
    int pulseCount;
    int pointsBeforeFlash;
};

static bool parseFrequencyParams(const char *s, FrequencyParams &p)
{
    double v[11];
    char *end;
    for (int i = 0; i < 11; i++)
    {
        v[i] = strtod(s, &end);
        if (end == s)
            return false;
        s = end;
        if (i < 10)
        {
            if (*s != ',')
                return false;
            s++;
        }
    }
    p.freqHz = v[0];
    p.prePeriods = (int)v[1];
    p.periods = (int)v[2];
    p.postPeriods = (int)v[3];
    p.amplitude = v[4];
    p.offset = v[5];
    p.background = v[6];
    p.firstPulseUs = v[7];
    p.spacingUs = v[8];
    p.pulseCount = (int)v[9];
    p.pointsBeforeFlash = (int)v[10];
    return p.freqHz > 0 && p.periods >= 0 && p.prePeriods >= 0 &&
           p.postPeriods >= 0 && p.pulseCount >= 0 && p.pointsBeforeFlash >= 0 &&
           p.spacingUs > 0;
}

static int pctToActinicLevel(double pct)
{
    if (pct < 0)
        pct = 0;
    if (pct > 100)
        pct = 100;
    return (int)lround(max_amp_actinic * pct / 100.0);
}

void handleFrequency(SystemContext &c)
{
    FrequencyParams p;
    if (!parseFrequencyParams(c.serial.buffer + 1, p))
    {
        Serial.println("Invalid frequency command");
        c.state = SystemState::IDLE;
        return;
    }

    const double periodUs = 1e6 / p.freqHz;
    const double sineStartUs = p.prePeriods * periodUs;
    const double sineEndUs = (p.prePeriods + p.periods) * periodUs;
    const double totalUs = (p.prePeriods + p.periods + p.postPeriods) * periodUs;
    const int backgroundLevel = pctToActinicLevel(p.background);

    float phase = 0.0f;
    if (p.amplitude != 0)
    {
        double bgNorm = (p.background - p.offset) / p.amplitude;
        bgNorm = bgNorm < -1.0 ? -1.0 : (bgNorm > 1.0 ? 1.0 : bgNorm);
        phase = (float)asin(bgNorm);
    }

    // Time from the first pre-flash trigger to the flash start.
    const int64_t leadUs = p.pointsBeforeFlash > 0
                               ? preTriggerLeadUs + (int64_t)(p.pointsBeforeFlash - 1) * preTriggerSpacingUs
                               : 0;

    int lastLevel = -1;
    int pulse = 0;
    int64_t lastPollUs = 0;
    const int64_t t0 = esp_timer_get_time();

    while (true)
    {
        const int64_t t = esp_timer_get_time() - t0;
        if (t >= (int64_t)totalUs && pulse >= p.pulseCount)
            break;

        // Next detection flash: hand over to the blocking, tightly timed routine.
        if (pulse < p.pulseCount)
        {
            const int64_t flashUs = (int64_t)llround(p.firstPulseUs + pulse * p.spacingUs);
            if (t >= flashUs - leadUs)
            {
                frequency_flash(t0 + flashUs, p.pointsBeforeFlash);
                pulse++;
                continue;
            }
        }

        // Actinic modulation (only touch the DAC when the 8-bit level changes).
        int level = backgroundLevel;
        if (t >= sineStartUs && t < sineEndUs)
        {
            // Fractional position in the period, kept in double so long runs
            // don't lose precision, then sinf() on the single-precision FPU.
            const double frac = fmod((double)t / periodUs, 1.0);
            const float s = sinf(2.0f * (float)M_PI * (float)frac + phase);
            level = pctToActinicLevel(p.amplitude * s + p.offset);
        }
        if (level != lastLevel)
        {
            writeActinicLevel(level);
            lastLevel = level;
        }

        // Poll serial once per ms so a stop command can abort the run.
        if (t - lastPollUs >= 1000)
        {
            lastPollUs = t;
            readSerial(c.serial);
            if (c.serial.messageReady && c.serial.buffer[0] == stopMarker)
            {
                c.serial.messageReady = false; // consume the stop command
                break;
            }
        }
    }

    writeActinicLevel(c.leds.currentActinicPWM);
    c.state = SystemState::IDLE;
}
