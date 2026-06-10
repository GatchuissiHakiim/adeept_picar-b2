import time
from control_leds import setup, set_led, all_off

def feux_detresse_on():
    """Fait clignoter les phares avant en rouge — à appeler en boucle."""
    set_led(4, 1)   # left_R ON
    set_led(7, 0)   # right_R OFF
    time.sleep(0.3)
    set_led(4, 0)   # left_R OFF
    set_led(7, 1)   # right_R ON
    time.sleep(0.3)

def feux_off():
    """Éteint tous les feux."""
    all_off()
