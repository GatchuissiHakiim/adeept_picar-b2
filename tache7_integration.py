#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from time import sleep
import sys

# ===== TACHE 1 : LED =====
from task1_leds.control_leds import setup as led_setup, set_led, all_off

# ===== TACHE 3 : SERVOS =====
from task3_servo import ServoController

# ===== TACHE 4 : MOTEUR =====
sys.path.append("./tache4_moteur")
from drive import drive_full, drive, destroy

# ===== TACHE 5 : ULTRASON + BUZZER =====
from tache5_ultrason import distance_mm, alerte_sonore


DISTANCE_DANGER = 200       # mm
DISTANCE_ATTENTION = 500    # mm


def afficher_led_distance(distance):
    all_off()

    if distance is None:
        set_led(3, 1)       # erreur
        return

    if distance < DISTANCE_DANGER:
        set_led(4, 1)       # rouge gauche
        set_led(7, 1)       # rouge droite

    elif distance < DISTANCE_ATTENTION:
        set_led(5, 1)       # vert gauche
        set_led(8, 1)       # vert droite

    else:
        set_led(6, 1)       # bleu gauche
        set_led(9, 1)       # bleu droite


def stop_robot():
    drive(0)
    sleep(0.1)


def reculer_robot():
    print("Obstacle proche -> recul")
    drive_full(25, -1, 0.5)
    sleep(0.8)
    stop_robot()


def main():
    print("=== TACHE 7 : INTEGRATION ===")
    print("Modules : LED + Servos + Moteur + Ultrason + Buzzer")

    led_setup()
    all_off()

    servo_controller = ServoController()
    servo_controller.center_robot_servos()

    try:
        while True:
            distance = distance_mm()
            afficher_led_distance(distance)

            if distance is None:
                print("Mesure invalide -> STOP")
                stop_robot()

            elif distance < DISTANCE_DANGER:
                print(f"DANGER : {distance:.0f} mm -> STOP + RECUL")
                alerte_sonore(distance)

                servo_controller.set_servo_angle(0, 0)
                stop_robot()
                reculer_robot()

            elif distance < DISTANCE_ATTENTION:
                print(f"ATTENTION : {distance:.0f} mm -> AVANCE LENTE")
                alerte_sonore(distance)

                servo_controller.set_servo_angle(0, 0)
                drive_full(15, 1, 0.5)

            else:
                print(f"OK : {distance:.0f} mm -> AVANCE NORMALE")
                alerte_sonore(distance)

                servo_controller.set_servo_angle(0, 0)
                drive_full(25, 1, 0.5)

            sleep(0.2)

    except KeyboardInterrupt:
        print("\nArret clavier")

    finally:
        print("Arret securise du robot")

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
            servo_controller.center_robot_servos()
            servo_controller.deinit()
        except Exception:
            pass

        print("Fin du programme")


if __name__ == "__main__":
    main()
