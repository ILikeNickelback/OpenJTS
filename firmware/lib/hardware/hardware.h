#ifndef HARDWARE_H
#define HARDWARE_H

#include "system_context.h"
#include "driver/dac.h"

void writeDacLevel(uint8_t pin, dac_channel_t channel, int value);

void detection_trigger(SystemContext &c);
void laser_trigger(SystemContext &c);

#endif
