#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tâche 3 : Servomoteurs - Adeept PiCar-B

Objectif :
- Tester d'abord un servo libre branché sur CH15.
- Puis piloter les 3 servos du robot : CH0, CH1, CH2.
- Commande manuelle sous forme : numero_servo angle

Angle choisi : relatif, de -90 à +90 degrés.
Exemple :
    15 0
    15 30
    0 -20
    1 45
    2 -30
    all 0
    q

Attention :
- CH15 est partagé avec les canaux moteur sur le PCA9685.
- Ne pas lancer move.py / functions.py en même temps.
- Pour le test CH15, garder le robot immobile, idéalement roues levées.
"""

import time
from board import SCL, SDA
import busio
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685


# Adresse I2C de la Robot HAT Adeept V3.1
PCA9685_ADDRESS = 0x5F
PWM_FREQUENCY = 50

# Plage d'impulsion utilisée par le fichier Adeept RPIservo.py
MIN_PULSE = 500
MAX_PULSE = 2400
ACTUATION_RANGE = 180

# Position centrale absolue des servos
NEUTRAL_ABS = 90

# Limites relatives de sécurité.
# On évite volontairement les -90 / +90 complets pour ne pas forcer les butées.
SERVO_LIMITS = {
    0: (-40, 40),   # Direction des roues avant
    1: (-60, 60),   # Tête / caméra / ultrason gauche-droite
    2: (-45, 45),   # Tête / caméra / ultrason haut-bas
    15: (-60, 60),  # Servo libre de test sur CH15
}

# Servos du robot à valider dans la partie finale
ROBOT_SERVOS = [0, 1, 2]


def clamp(value, min_value, max_value):
    """Limite une valeur entre min_value et max_value."""
    return max(min_value, min(value, max_value))


class ServoController:
    def __init__(self):
        self.i2c = busio.I2C(SCL, SDA)
        self.pca = PCA9685(self.i2c, address=PCA9685_ADDRESS)
        self.pca.frequency = PWM_FREQUENCY

        self.servos = {}
        self.current_abs_angles = {}

    def get_servo(self, channel):
        """Crée l'objet servo uniquement quand on en a besoin."""
        if channel not in self.servos:
            self.servos[channel] = servo.Servo(
                self.pca.channels[channel],
                min_pulse=MIN_PULSE,
                max_pulse=MAX_PULSE,
                actuation_range=ACTUATION_RANGE,
            )
            self.current_abs_angles[channel] = NEUTRAL_ABS
        return self.servos[channel]

    def relative_to_absolute(self, channel, relative_angle):
        """
        Convertit un angle relatif (-90 à +90 théorique)
        en angle absolu servo (0 à 180).
        """
        min_rel, max_rel = SERVO_LIMITS[channel]
        safe_relative = clamp(relative_angle, min_rel, max_rel)
        absolute_angle = NEUTRAL_ABS + safe_relative
        absolute_angle = clamp(absolute_angle, 0, 180)
        return safe_relative, absolute_angle

    def set_servo_angle(self, channel, relative_angle, smooth=True):
        """
        Fonction demandée par la tâche :
        prend en paramètres le numéro du servo et l'angle en degrés.

        Ici, l'angle est relatif :
        - 0 correspond au centre
        - valeur négative : sens 1
        - valeur positive : sens opposé
        """
        if channel not in SERVO_LIMITS:
            raise ValueError(
                f"Servo {channel} non autorisé. "
                f"Utilise seulement : {list(SERVO_LIMITS.keys())}"
            )

        safe_relative, target_abs = self.relative_to_absolute(channel, relative_angle)
        servo_obj = self.get_servo(channel)

        if not smooth:
            servo_obj.angle = target_abs
            self.current_abs_angles[channel] = target_abs
        else:
            start_abs = self.current_abs_angles.get(channel, NEUTRAL_ABS)
            step = 1 if target_abs >= start_abs else -1

            for angle in range(int(start_abs), int(target_abs), step):
                servo_obj.angle = angle
                time.sleep(0.01)

            servo_obj.angle = target_abs
            self.current_abs_angles[channel] = target_abs

        print(
            f"Servo CH{channel} -> angle relatif demandé : {relative_angle}°, "
            f"angle appliqué : {safe_relative}°, "
            f"angle absolu PWM : {target_abs}°"
        )

    def center_servo(self, channel):
        """Replace un servo au centre."""
        self.set_servo_angle(channel, 0)

    def center_robot_servos(self):
        """Replace les 3 servos montés sur le robot au centre."""
        for channel in ROBOT_SERVOS:
            self.center_servo(channel)
            time.sleep(0.3)

    def deinit(self):
        """Libère proprement le PCA9685."""
        self.pca.deinit()


def print_help():
    print()
    print("Commandes disponibles :")
    print("  15 0       -> centre le servo libre branché sur CH15")
    print("  15 30      -> tourne le servo libre à +30°")
    print("  0 -20      -> tourne le servo CH0 à -20°")
    print("  1 45       -> tourne le servo CH1 à +45°")
    print("  2 -30      -> tourne le servo CH2 à -30°")
    print("  all 0      -> centre les servos CH0, CH1, CH2")
    print("  help       -> affiche l'aide")
    print("  q          -> quitter")
    print()


def main():
    controller = ServoController()

    print("=== Tâche 3 : contrôle manuel des servomoteurs ===")
    print("Angle utilisé : relatif, avec 0° = position centrale.")
    print("Sécurité : les angles sont limités pour éviter les butées.")
    print()
    print("Étape conseillée : tester d'abord le servo libre sur CH15.")
    print("Exemple : 15 0 puis 15 30 puis 15 -30")
    print_help()

    try:
        while True:
            command = input("servo angle > ").strip().lower()

            if command in ("q", "quit", "exit"):
                break

            if command in ("help", "h", "?"):
                print_help()
                continue

            if command == "":
                continue

            parts = command.split()

            if len(parts) != 2:
                print("Commande invalide. Exemple attendu : 15 30")
                continue

            servo_id_text, angle_text = parts

            try:
                angle = float(angle_text)
            except ValueError:
                print("Angle invalide. Exemple : 30, -30, 0")
                continue

            if servo_id_text == "all":
                if angle != 0:
                    print("Pour 'all', utilise seulement : all 0")
                    continue

                controller.center_robot_servos()
                continue

            try:
                servo_id = int(servo_id_text)
            except ValueError:
                print("Numéro de servo invalide. Utilise 0, 1, 2, 15 ou all.")
                continue

            try:
                controller.set_servo_angle(servo_id, angle)
            except ValueError as error:
                print(error)

    except KeyboardInterrupt:
        print("\nArrêt demandé au clavier.")

    finally:
        print("Retour au centre des servos déjà utilisés...")
        for channel in list(controller.servos.keys()):
            try:
                controller.center_servo(channel)
                time.sleep(0.2)
            except Exception:
                pass

        controller.deinit()
        print("Fin du programme.")


if __name__ == "__main__":
    main()