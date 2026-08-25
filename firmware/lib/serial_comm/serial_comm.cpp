#include "serial_comm.h"
#include "config.h"
#include <Arduino.h>

void readSerial(SerialState &s)
{
    while (Serial.available())
    {
        char c = Serial.read();

        if (c == startMarker)
        {
            s.index = 0;
            s.inProgress = true;
        }
        else if (c == endMarker && s.inProgress)
        {
            s.buffer[s.index] = '\0';
            s.inProgress = false;
            s.messageReady = true;
        }
        else if (s.inProgress && s.index < 15000)
        {
            s.buffer[s.index++] = c;
        }
    }
}
