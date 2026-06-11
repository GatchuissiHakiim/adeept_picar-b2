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

# ===== TACHE 6 : SUIVI DE LIGNE =====
from task6_line_tracking import LineTrackingSensor


DISTANCE_DANGER = 200
DISTANCE_ATTENTION = 500

VITESSE_NORMALE = 50
VITESSE_LENTE = 25
VITESSE_RECUL = 25

ANGLE_GAUCHE = -25
ANGLE_DROITE = 25
ANGLE_CENTRE = 0


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


def stop_robot():
    drive(0)
    sleep(0.1)


def reculer_robot():
    print("Obstacle devant -> recul")
    drive_full(VITESSE_RECUL, -1, 0.5)
    sleep(0.8)
    stop_robot()


last_direction = "center"


def suivre_ligne(pattern, servo_controller):
    global last_direction

    if pattern == "010":
        print("Ligne centre -> avancer")
        last_direction = "center"
        servo_controller.set_servo_angle(0, 0)
        drive_full(18, 1, 0.0)

    elif pattern in ("100", "110"):
        print("Ligne gauche -> tourner gauche")
        last_direction = "right"
        servo_controller.set_servo_angle(0, -40)
        drive_full(12, 1, 0.0)

    elif pattern in ("001", "011"):
        print("Ligne droite -> tourner droite")
        last_direction = "left"
        servo_controller.set_servo_angle(0, 40)
        drive_full(12, 1, 0.0)

    elif pattern == "000":
        print("Surface claire -> avance lente")
        servo_controller.set_servo_angle(0, 0)
        drive_full(10, 1, 0.0)

    elif pattern == "111":
        print(f"Ligne perdue -> recherche {last_direction}")

        if last_direction == "left":

            servo_controller.set_servo_angle(0, -40)
            drive_full(8, 1, 0.0)

        elif last_direction == "right":
            servo_controller.set_servo_angle(0, 40)
            drive_full(8, 1, 0.0)

        else:
            servo_controller.set_servo_angle(0, 0)
            drive_full(6, 1, 0.0)

    else:
        print(f"Pattern {pattern} inconnu -> avance lente")
        drive_full(8, 1, 0.0)
def main():
    print("=== TACHE 7 : INTEGRATION COMPLETE ===")
    print("Tâches intégrées : 1 LED, 3 servos, 4 moteur, 5 ultrason, 6 suivi de ligne")

    led_setup()
    all_off()

    servo_controller = ServoController()
    line_sensor = LineTrackingSensor()

    servo_controller.center_robot_servos()

    try:
        while True:
            distance = distance_mm()
            pattern = line_sensor.read_pattern()

            afficher_led_distance(distance)

            print(f"Distance : {distance if distance is not None else 'invalide'} mm | Ligne : {pattern}")

            if distance is None:
                print("Mesure ultrason invalide -> STOP")
                stop_robot()

            elif distance < DISTANCE_DANGER:
                print(f"DANGER : obstacle à {distance:.0f} mm -> STOP + RECUL")
                alerte_sonore(distance)
                servo_controller.set_servo_angle(0, ANGLE_CENTRE)
                stop_robot()
                reculer_robot()

            elif distance < DISTANCE_ATTENTION:
                print(f"ATTENTION : obstacle à {distance:.0f} mm -> avance lente")
                alerte_sonore(distance)
                servo_controller.set_servo_angle(0, ANGLE_CENTRE)
                drive_full(VITESSE_LENTE, 1, 0.3)

            else:
                print("Pas d'obstacle proche -> suivi de ligne")
                alerte_sonore(distance)
                suivre_ligne(pattern, servo_controller)

            

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
            servo_controller.center_robot_servos()
            servo_controller.deinit()
        except Exception:
            pass

        print("Fin du programme")


if __name__ == "__main__":
    main()

