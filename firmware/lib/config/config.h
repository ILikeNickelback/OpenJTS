#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>
#include "soc/gpio_struct.h"
#include "driver/gpio.h"

// ---------- Pins ----------
// GPIO26 is the ESP32's DAC-capable pin, reserved for the actinic analog
// output below. detectorDacPin is driven via LEDC PWM instead of the DAC —
// its GPIO matrix output stage has a strong push-pull driver, giving sharp
// edges in both directions instead of the DAC's weak, slow pull-down — so it
// no longer needs to be a true DAC pin. TriggPin is moved off GPIO25 to
// GPIO12 to free it up (GPIO12 is a boot-strapping pin (MTDI) — confirmed
// safe for this board's wiring).
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

// ---------- Analog output (DAC) ----------
// dacWrite() is 8-bit, fixed resolution — no PWM frequency/resolution config needed.
constexpr int dacResolution = 8;
constexpr int max_amp_actinic = (1 << dacResolution) - 1; // 255 — full DAC range

// ---------- Detector PWM ----------
// Frequency is set near the top of the 8-bit LEDC range so several duty
// cycles land within detection_trigger()'s 20us pulse window.
constexpr int detectorPwmChannel = 0;
constexpr int detectorPwmFreq = 312500;
constexpr int detectorPwmResolution = 8;
constexpr int max_amp_detector = (1 << detectorPwmResolution) - 1; // 255 — full PWM range

#endif
