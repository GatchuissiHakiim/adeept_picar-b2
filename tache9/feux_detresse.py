import time
import sys
sys.path.append('/home/vigiris/adeept_picar-b2/task1_leds')
sys.path.append('/home/vigiris/adeept_picar-b2/examples')

from control_leds import setup, set_led, all_off
from importlib import import_module
ws2812 = import_module('06_Spi_WS2812')
Adeept_SPI_LedPixel = ws2812.Adeept_SPI_LedPixel

NB_LEDS = 14
led = Adeept_SPI_LedPixel(count=NB_LEDS, bright=255)
led.setDaemon(True)
led.start()

def feux_detresse_on():
    set_led(6, 1)   
    set_led(7, 1)   
    for i in range(NB_LEDS):
        led.set_led_color(i, 255, 0, 0) 
    time.sleep(0.5)
    set_led(6, 0)
    set_led(7, 0)
    for i in range(NB_LEDS):
        led.set_led_color(i, 0, 0, 0)
    time.sleep(0.5)

def feux_off():
    all_off()
    for i in range(NB_LEDS):
        led.set_led_color(i, 0, 0, 0)

if __name__ == '__main__':
    try:
        setup()
        print("Feux de détresse ON — Ctrl+C pour arrêter")
        while True:
            feux_detresse_on()
    except KeyboardInterrupt:
        feux_off()
        print("Feux éteints.")

