#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Test : capture une image avec la camera du robot

from picamera2 import Picamera2
import time

print("Initialisation de la camera...")
picam = Picamera2()

# Configuration simple pour une photo
config = picam.create_still_configuration()
picam.configure(config)

picam.start()
time.sleep(2)            # laisse la camera s'ajuster (expo, balance des blancs)

print("Capture en cours...")
picam.capture_file("test_photo.jpg")
picam.stop()

print("Photo enregistree : test_photo.jpg")