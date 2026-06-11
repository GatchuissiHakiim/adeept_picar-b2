#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from time import sleep
import sys
import time

from board import SCL, SDA
import busio
from adafruit_pca9685 import PCA9685

# ===== TACHE 1 : LED =====
from task1_leds.control_leds import setup as led_setup, set_led, all_off

# ===== TACHE 4 : MOTEUR =====
sys.path.append("./tache4_moteur")
from drive import drive_full, drive, destroy

# ===== TACHE 5 : ULTRASON + BUZZER =====
from tache5_ultrason import distance_mm, alerte_sonore

# ===== TACHE 6 : SUIVI DE LIGNE =====
from task6_line_tracking import LineTrackingSensor


# =========================
# CONFIGURATION
# =========================

DISTANCE_DANGER = 200
DISTANCE_ATTENTION = 500

VITESSE_NORMALE = 40
VITESSE_LENTE = 30
VITESSE_RECHERCHE = 20
VITESSE_RECUL = 25

ANGLE_GAUCHE = -70
ANGLE_DROITE = 70
ANGLE_CENTRE = 0

# Mettre True si tu veux recalibrer manuellement au démarrage
CALIBRATE_AT_START = False


# =========================
# SERVO DIRECTION CALIBRÉ
# =========================

i2c = busio.I2C(SCL, SDA)
pwm = PCA9685(i2c, address=0x5f)
pwm.frequency = 50

SERVO_CHANNEL = 0

SERVO_MIN = 2977
SERVO_CENTER = 5215
SERVO_MAX = 7153


def set_servo_raw(value):
    pwm.channels[SERVO_CHANNEL].duty_cycle = int(value)


def set_servo_angle(angle):
    """angle : -100 gauche, +100 droite, 0 centre"""
    angle = max(-100, min(100, angle))

    if angle >= 0:
        raw = SERVO_CENTER + (angle / 100.0) * (SERVO_MAX - SERVO_CENTER)
    else:
        raw = SERVO_CENTER + (angle / 100.0) * (SERVO_CENTER - SERVO_MIN)

    set_servo_raw(raw)


def calibrate_servo():
    global SERVO_MIN, SERVO_CENTER, SERVO_MAX

    print("\n=== CALIBRATION SERVO DIRECTION ===")

    def ajuster(label, start):
        val = start

        while True:
            set_servo_raw(val)
            cmd = input(f"{label} valeur={val} | + / - / Entrée : ").strip()

            if cmd == "+":
                val = min(65535, val + 100)
            elif cmd == "-":
                val = max(0, val - 100)
            elif cmd == "":
                print(f"{label} = {val}")
                return val

    SERVO_MIN = ajuster("Butée gauche", SERVO_MIN)
    SERVO_CENTER = ajuster("Centre", SERVO_CENTER)
    SERVO_MAX = ajuster("Butée droite", SERVO_MAX)

    print("\nValeurs finales :")
    print(f"SERVO_MIN = {SERVO_MIN}")
    print(f"SERVO_CENTER = {SERVO_CENTER}")
    print(f"SERVO_MAX = {SERVO_MAX}")

    set_servo_angle(0)


# =========================
# LED
# =========================

def afficher_led_distance(distance):
    all_off()

    if distance is None:
        set_led(3, 1)
        return

    if distance < DISTANCE_DANGER:
        set_led(4, 1)
        set_led(7, 1)

    elif distance < DISTANCE_ATTENTION:
        set_led(5, 1)
        set_led(8, 1)

    else:
        set_led(6, 1)
        set_led(9, 1)


# =========================
# MOTEUR SANS À-COUPS
# =========================

last_motor_command = None


def commander_moteur(speed, direction):
    global last_motor_command

    command = (speed, direction)

    if command == last_motor_command:
        return

    drive_full(speed, direction, 0.0)
    last_motor_command = command


def stop_robot():
    global last_motor_command

    drive(0)
    last_motor_command = (0, 0)
    sleep(0.1)


def reculer_robot():
    print("Obstacle devant -> recul")
    drive_full(VITESSE_RECUL, -1, 0.3)
    sleep(0.7)
    stop_robot()


# =========================
# SUIVI DE LIGNE
# =========================

last_direction = "center"


last_direction = "center"

last_direction = "center"

def suivre_ligne(pattern):
    global last_direction

    if pattern == "111":
        print("Ligne large centrée -> avancer droit")
        last_direction = "center"
        set_servo_angle(0)
        commander_moteur(12, 1)

    elif pattern == "110":
        print("Ligne un peu à gauche -> correction gauche légère")
        last_direction = "left"
        set_servo_angle(25)
        commander_moteur(9, 1)

    elif pattern == "100":
        print("Ligne très à gauche -> correction gauche forte")
        last_direction = "left"
        set_servo_angle(-55)
        commander_moteur(7, 1)

    elif pattern == "011":
        print("Ligne un peu à droite -> correction droite légère")
        last_direction = "right"
        set_servo_angle(-25)
        commander_moteur(9, 1)

    elif pattern == "001":
        print("Ligne très à droite -> correction droite forte")
        last_direction = "right"
        set_servo_angle(55)
        commander_moteur(7, 1)

    elif pattern == "010":
        print("Centre seul noir -> avancer droit lentement")
        last_direction = "center"
        set_servo_angle(0)
        commander_moteur(8, 1)

    elif pattern == "000":
        print(f"Ligne perdue -> recherche {last_direction}")

        if last_direction == "left":
            set_servo_angle(60)
            commander_moteur(6, 1)

        elif last_direction == "right":
            set_servo_angle(-60)
            commander_moteur(6, 1)

        else:
            set_servo_angle(0)
            commander_moteur(5, 1)

    else:
        print(f"Pattern {pattern} inconnu -> avance lente")
        set_servo_angle(0)
        commander_moteur(6, 1)
# =========================
# MAIN
# =========================

def main():
    print("=== TACHE 7 : INTEGRATION COMPLETE ===")
    print("Tâches : LED + moteur + ultrason + buzzer + suivi ligne + servo calibré")

    led_setup()
    all_off()

    line_sensor = LineTrackingSensor()

    if CALIBRATE_AT_START:
        calibrate_servo()
    else:
        print("Centrage servo direction")
        set_servo_angle(0)
        sleep(0.5)

    try:
        while True:
            distance = distance_mm()
            pattern = line_sensor.read_pattern()

            afficher_led_distance(distance)

            if distance is None:
                print(f"Distance invalide | Ligne : {pattern} -> STOP")
                stop_robot()

            elif distance < DISTANCE_DANGER:
                print(f"DANGER {distance:.0f} mm | Ligne : {pattern} -> STOP + RECUL")
                alerte_sonore(distance)
                set_servo_angle(ANGLE_CENTRE)
                stop_robot()
                reculer_robot()

            elif distance < DISTANCE_ATTENTION:
                print(f"ATTENTION {distance:.0f} mm | Ligne : {pattern} -> avance lente")
                alerte_sonore(distance)
                set_servo_angle(ANGLE_CENTRE)
                commander_moteur(VITESSE_LENTE, 1)

            else:
                print(f"OK {distance:.0f} mm | Ligne : {pattern}")
                alerte_sonore(distance)
                suivre_ligne(pattern)

            sleep(0.05)

    except KeyboardInterrupt:
        print("\nArrêt clavier demandé")

    finally:
        print("Arrêt sécurisé du robot")

        try:
            stop_robot()
            destroy()
        except Exception:
            pass

        try:
            all_off()
        except Exception:
            pass

        try:
            set_servo_angle(0)
            sleep(0.3)
            pwm.deinit()
        except Exception:
            pass

        print("Fin du programme")


if __name__ == "__main__":
    main()
