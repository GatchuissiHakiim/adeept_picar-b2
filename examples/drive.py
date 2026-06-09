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

if __name__ == '__main__':
    print("Avant 25%")
    drive(1) # Lance le moteur en avant à 25% de sa puissance
    time.sleep(2)
    print("Stop")
    drive(0)
    time.sleep(1)
    print("Arrière 25%")
    drive(-1)
    time.sleep(2)
    print("Stop final")
    drive(0)
    destroy()
