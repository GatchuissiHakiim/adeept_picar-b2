import time
from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685

i2c = busio.I2C(SCL, SDA)
pwm = PCA9685(i2c, address=0x5f)
pwm.frequency = 50

SERVO_CHANNEL = 0   

# Valeurs à calibrer en duty cycle (0-65535)
SERVO_MIN    = 2977   # butée gauche  
SERVO_CENTER = 5215   # centre       
SERVO_MAX    = 7153   # butée droite  


def set_servo_raw(value):
    pwm.channels[SERVO_CHANNEL].duty_cycle = int(value)


def set_servo_angle(angle):
    """angle : -100 (gauche) à +100 (droite), 0 = centre"""
    angle = max(-100, min(100, angle))
    if angle >= 0:
        raw = SERVO_CENTER + (angle / 100.0) * (SERVO_MAX - SERVO_CENTER)
    else:
        raw = SERVO_CENTER + (angle / 100.0) * (SERVO_CENTER - SERVO_MIN)
    set_servo_raw(raw)


def calibrate_servo():
    global SERVO_MIN, SERVO_CENTER, SERVO_MAX
    print("\n=== CALIBRATION SERVO ===")
    print("+ pour augmenter, - pour diminuer, Entrée pour valider\n")

    def ajuster(label, start):
        val = start
        while True:
            set_servo_raw(val)
            cmd = input(f"{label} (valeur={val}) +/-/Entrée : ").strip()
            if cmd == "+":
                val = min(65535, val + 100)
            elif cmd == "-":
                val = max(0, val - 100)
            elif cmd == "":
                print(f"✓ {label} = {val}\n")
                return val

    print("1) Roues à fond à GAUCHe")
    SERVO_MIN = ajuster("Butée gauche", SERVO_MIN)
    print("2) Roues DROITES (centre)")
    SERVO_CENTER = ajuster("Centre", SERVO_CENTER)
    print("3) Roues à fond à DROITE")
    SERVO_MAX = ajuster("Butée droite", SERVO_MAX)

    print("=== Résultats à recopier dans le code ===")
    print(f"SERVO_MIN    = {SERVO_MIN}")
    print(f"SERVO_CENTER = {SERVO_CENTER}")
    print(f"SERVO_MAX    = {SERVO_MAX}")

    set_servo_angle(0)


#if __name__ == '__main__':
#    calibrate_servo()       # Pour appeler la fonction permettant de calibrer le servo de direction

if __name__ == '__main__':   # Pour configurer le servo de direction sur les paramètre initiaux récupérés via la calibration
    print("Test centre")
    set_servo_angle(0)
    time.sleep(1)
    print("Test gauche")
    set_servo_angle(-100)
    time.sleep(1)
    print("Test droite")
    set_servo_angle(100)
    time.sleep(1)
    print("Retour centre")
    set_servo_angle(0)
    pwm.deinit()
