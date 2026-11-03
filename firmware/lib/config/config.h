#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>
#include "soc/gpio_struct.h"
#include "driver/gpio.h"

// ---------- Pins ----------
// GPIO26 (DAC_CHANNEL_2) drives the actinic light as an analog output.
// GPIO25 drives the detection light as a plain digital (on/off) output. TriggPin is moved off GPIO25 to GPIO12 to free it
// up (GPIO12 is a boot-strapping pin (MTDI) — confirmed safe for this
// board's wiring).
#define TriggPin 12
#define actinicDacPin 26
#define detectorPin 25
#define laserChannel_start 18
#define laserChannel_open 19

// ---------- GPIO ----------
#define GPIO_SET(pin) (GPIO.out_w1ts = (1 << pin))
#define GPIO_CLR(pin) (GPIO.out_w1tc = (1 << pin))

// ---------- Protocol markers ----------
#define startMarker '<'
#define endMarker '>'
#define continuesMarker '#'
#define constantLightMarker_on 'O'
#define constantLightMarker_off 'I'
#define set_LED_intensity 'S'
#define stopMarker 'X'
#define frequencyMarker 'F'

// ---------- Frequency-mode trigger timing ----------
// Pre-flash triggers are spaced preTriggerSpacingUs apart; the last one rises
// preTriggerLeadUs before the detection flash, whose own trigger fires 18 us
// into the flash. With 3 pre-flash points this puts the ADC scans at
// t = 0, 60, 120 and 145 us — the times assumed by the frequency-mode
// processing in software/src/workers/base_worker.py. Keep these in sync with
// software/src/hardware/adc_frequency_external.py.
constexpr int triggerPulseUs = 2;
constexpr int preTriggerSpacingUs = 60;
constexpr int preTriggerLeadUs = 7;

// ---------- Analog output (DAC) ----------
// dacWrite() is 8-bit, fixed resolution — no PWM frequency/resolution config needed.
constexpr int dacResolution = 8;
constexpr int max_amp_actinic = (1 << dacResolution) - 1;  // 255 — full DAC range
constexpr int max_amp_detector = (1 << dacResolution) - 1; // 255 — full DAC range

#endif
