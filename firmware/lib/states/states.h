#ifndef STATES_H
#define STATES_H

#include "system_context.h"

void handleIdle(SystemContext &c);
void handleContinuesFlash(SystemContext &c);
void handleConstantLight(SystemContext &c);
void handleSequence(SystemContext &c);

#endif
