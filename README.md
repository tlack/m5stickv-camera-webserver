# m5stickv-camera-webserver

This software allows M5StickV / Kendryte K210 / Sipeed Maix MicroPython users
to publish images from their device to their local network.

The K210 features an onboard neural network and computer vision accelerator
chip, but often is packaged without wifi.

## Status

Only the low level connection code works (and is useful to transfer images).
Webserver part missing (but easier).

## How it works

The software connects at 115200, switches to 1.5mbps, and then begins
downloading images.

It shoves raw Python commands into the remote MicroPython REPL. That way you
don't have to load any firmware or transfer any files into the bootloader /
flash / etc.

The data is encoded using `(u)binascii.hexlify()`.

