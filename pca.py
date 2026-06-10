#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Instance unique du PCA9685 partagee par le moteur et le servo
# (evite le conflit I2C : 2 modules pilotant la meme puce 0x5f)

from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685

i2c = busio.I2C(SCL, SDA)
pwm = PCA9685(i2c, address=0x5f)
pwm.frequency = 50