# OpenJTS

Welcome to the documentation for OpenJTS, an open hardware version of the Joliot Type Spectrophotometer (JTS). Here you'll find everything needed to build, run and contribute to the project: technical notes, construction instructions and manuals covering the hardware, software and firmware.

![My image](../../assets/img/JTS150_002.png)

## Purpose

The OpenJTS is designed for measuring light-induced transient signals in photosynthesis research: ECS, Phi PSII, and related fluorescence and spectroscopy protocols.

This version was designed as an open alternative to commercial JTS instruments (such as the JBeamBio JTS). With modest skills and budget, interested labs can build their own instrument, and anyone is welcome to contribute to its development.

Compared to previous versions, OpenJTS offers:

- A new user interface written in Python
- A greater number of actinic and detection light levels
- Two independent detection LEDs, replacing the Y fibre optic used previously
- A design optimized for flat samples

## Where to start

The full step-by-step build instructions are available in the [build manual](hardware/notes/full-build-manual.md). Note that there are several separate instruction manuals, one for each independent part of the instrument, to keep things clear.

## Licence

OpenJTS is released under the [Apache License 2.0](../LICENSE).

```{toctree}
:maxdepth: 2
:caption: Documentation

hardware/index
software/index
firmware/firmware
```
