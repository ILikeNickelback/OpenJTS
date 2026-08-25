#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>
#include "soc/gpio_struct.h"
#include "driver/gpio.h"

// ---------- Pins ----------
// GPIO26 (DAC_CHANNEL_2) is reserved for the actinic analog output below.
// GPIO25 (detectorDacPin) drives the detector LED as a plain digital
// GPIO_SET/GPIO_CLR output — its GPIO matrix output stage has a strong
// push-pull driver, giving sharp edges in both directions for
// detection_trigger()'s pulse. TriggPin is moved off GPIO25 to GPIO12 to
// free it up (GPIO12 is a boot-strapping pin (MTDI) — confirmed safe for
// this board's wiring).
#define TriggPin 12
#define actinicDacPin 26
#define detectorDacPin 25
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

// ---------- Analog output (DAC) ----------
// dacWrite() is 8-bit, fixed resolution — no PWM frequency/resolution config needed.
constexpr int dacResolution = 8;
constexpr int max_amp_actinic = (1 << dacResolution) - 1; // 255 — full DAC range

// ---------- Detector ----------
// detectorDacPin is a plain digital GPIO (see above), so detectorIntensity
// and max_amp_detector are kept only for 'S' command protocol compatibility
// — detection_trigger() always drives the pin fully on/off and ignores them.
constexpr int max_amp_detector = 255;

#endif
