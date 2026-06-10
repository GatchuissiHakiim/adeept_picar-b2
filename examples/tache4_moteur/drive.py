import time
from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import motor

i2c = busio.I2C(SCL, SDA)
pwm_motor = PCA9685(i2c, address=0x5f)
pwm_motor.frequency = 50

MOTOR_M1_IN1 = 15
MOTOR_M1_IN2 = 14
motor1 = motor.DCMotor(pwm_motor.channels[MOTOR_M1_IN1], pwm_motor.channels[MOTOR_M1_IN2])
motor1.decay_mode = motor.SLOW_DECAY

def destroy(): # Arrêt immédiat
    motor1.throttle = 0
    pwm_motor.deinit()

def drive(direction):
    low_speed = 25 # Vitesse de base définie à 25% de la puissance max
    if direction == 0:
        motor1.throttle = 0
        return
    throttle = low_speed / 100.0 # Conversion du pourcentage (25) en un float entre -1 et 1
    if direction == -1:
        throttle = -throttle
    motor1.throttle = throttle

def drive_ramp(direction, target_speed=100, ramp_time=1.0):
    if direction == 0:
        motor1.throttle = 0
        return
    steps = 50
    delay = ramp_time / steps
    for step in range(1, steps + 1):
        throttle = (step / steps) * (target_speed / 100.0)
        if direction == -1:
            throttle = -throttle
        motor1.throttle = throttle
        time.sleep(delay) 

def drive_full(speed, direction, ramp_time=0.0):
    if direction == 0 or speed == 0:
        motor1.throttle = 0
        return
    speed = max(0, min(100, speed))
    if ramp_time > 0:
        drive_ramp(direction, target_speed=speed, ramp_time=ramp_time)
    else:
        throttle = speed / 100.0
        if direction == -1:
            throttle = -throttle
        motor1.throttle = throttle

def manual_test():
    print("\n=== MODE MANUEL ===")
    print("z = avant  |  s = arrière  |  w = stop  |  x = quitter")
    while True:
        cmd = input("Commande : ").strip().lower()
        if cmd == "z":
            print("→ Avant 25%")
            drive_full(25, 1, ramp_time=1)
        elif cmd == "s":
            print("→ Arrière 25%")
            drive_full(25, -1, ramp_time=1)
        elif cmd == "w" or cmd == "stop":
            print("→ Stop")
            drive(0)
        elif cmd == "x":
            print("→ Quitter")
            drive(0)
            destroy()
            break
        else:
            print("  touche non reconnue")

if __name__ == "__main__":
        manual_test()
