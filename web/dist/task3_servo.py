#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tâche 3 : Servomoteurs - Adeept PiCar-B

Version sécurisée pour robot assemblé :
- Test du servo libre sur CH3, pas CH15.
- Pilotage des 3 servos montés sur le robot : CH0, CH1, CH2.
- Les canaux CH8 à CH15 sont interdits car ils sont liés aux moteurs.
- Ajout d'une démo signature coordonnée des 3 servos.
"""

import time
from board import SCL, SDA
import busio
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685


PCA9685_ADDRESS = 0x5F
PWM_FREQUENCY = 50

MIN_PULSE = 500
MAX_PULSE = 2400
ACTUATION_RANGE = 180
NEUTRAL_ABS = 90

# Canaux moteurs du PiCar-B : à ne pas utiliser pour les servos.
MOTOR_CHANNELS = set(range(8, 16))

# Canaux autorisés pour les servos.
# CH3 remplace CH15 pour tester le servo libre.
SERVO_LIMITS = {
    0: (-40, 40),   # Direction roues avant
    1: (-60, 60),   # Tête gauche-droite
    2: (-45, 45),   # Tête haut-bas
    3: (-60, 60),   # Servo libre de test
}

ROBOT_SERVOS = [0, 1, 2]


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


class ServoController:
    def __init__(self):
        self.i2c = busio.I2C(SCL, SDA)
        self.pca = PCA9685(self.i2c, address=PCA9685_ADDRESS)
        self.pca.frequency = PWM_FREQUENCY

        self.servos = {}
        self.current_abs_angles = {}

        # Sécurité : on coupe les PWM des canaux moteurs au démarrage.
        self.stop_motor_channels()

    def stop_motor_channels(self):
        for channel in MOTOR_CHANNELS:
            self.pca.channels[channel].duty_cycle = 0

    def get_servo(self, channel):
        if channel in MOTOR_CHANNELS:
            raise ValueError(
                f"CH{channel} est réservé aux moteurs sur ce robot. "
                "Utilise CH0, CH1, CH2 ou CH3."
            )

        if channel not in SERVO_LIMITS:
            raise ValueError(
                f"CH{channel} non autorisé. "
                f"Canaux autorisés : {list(SERVO_LIMITS.keys())}"
            )

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
        min_rel, max_rel = SERVO_LIMITS[channel]
        safe_relative = clamp(relative_angle, min_rel, max_rel)
        absolute_angle = clamp(NEUTRAL_ABS + safe_relative, 0, 180)
        return safe_relative, absolute_angle

    def set_servo_angle(self, channel, relative_angle, smooth=True):
        """
        Fonction demandée :
        set_servo_angle(numero_servo, angle_en_degres)

        Angle relatif :
        - 0 = centre
        - négatif = sens 1
        - positif = sens opposé
        """
        servo_obj = self.get_servo(channel)
        safe_relative, target_abs = self.relative_to_absolute(channel, relative_angle)

        if smooth:
            start_abs = self.current_abs_angles.get(channel, NEUTRAL_ABS)
            step = 1 if target_abs >= start_abs else -1

            for angle in range(int(start_abs), int(target_abs), step):
                servo_obj.angle = angle
                time.sleep(0.01)

        servo_obj.angle = target_abs
        self.current_abs_angles[channel] = target_abs

        print(
            f"CH{channel} | demandé : {relative_angle}° | "
            f"appliqué : {safe_relative}° | PWM absolu : {target_abs}°"
        )

    def set_many_angles(self, targets, duration=0.6, steps=30):
        """
        Déplace plusieurs servos de manière coordonnée et progressive.

        targets est un dictionnaire :
            {numero_servo: angle_relatif}

        Exemple :
            self.set_many_angles({0: 10, 1: -30, 2: 15})
        """
        if steps <= 0:
            steps = 1

        target_abs = {}
        start_abs = {}

        # Préparation des servos et calcul des angles sécurisés.
        for channel, relative_angle in targets.items():
            self.get_servo(channel)
            _, abs_angle = self.relative_to_absolute(channel, relative_angle)

            target_abs[channel] = abs_angle
            start_abs[channel] = self.current_abs_angles.get(channel, NEUTRAL_ABS)

        # Mouvement progressif avec interpolation douce.
        for step_index in range(1, steps + 1):
            t = step_index / steps

            # Interpolation smoothstep : mouvement plus naturel.
            eased_t = 3 * t * t - 2 * t * t * t

            for channel in targets:
                angle = start_abs[channel] + (
                    target_abs[channel] - start_abs[channel]
                ) * eased_t

                self.servos[channel].angle = angle

            time.sleep(duration / steps)

        # Mise à jour des positions connues.
        for channel in targets:
            self.current_abs_angles[channel] = target_abs[channel]

    def signature_demo(self):
        """
        Démo distinctive pour la tâche 3 :
        - retour au neutre
        - mouvement "non" avec la tête
        - mouvement "oui" avec la tête
        - balayage type radar
        - petit salut final
        - retour automatique au neutre
        """
        print("Démo signature : chorégraphie coordonnée des 3 servos.")

        # Position neutre.
        self.set_many_angles({0: 0, 1: 0, 2: 0}, duration=0.6)
        time.sleep(0.3)

        # Le robot dit "non" avec la tête gauche-droite.
        for _ in range(2):
            self.set_many_angles({1: -35}, duration=0.25)
            self.set_many_angles({1: 35}, duration=0.25)
        self.set_many_angles({1: 0}, duration=0.25)

        # Le robot dit "oui" avec la tête haut-bas.
        for _ in range(2):
            self.set_many_angles({2: -20}, duration=0.25)
            self.set_many_angles({2: 20}, duration=0.25)
        self.set_many_angles({2: 0}, duration=0.25)

        # Balayage type radar : tête + légère orientation des roues.
        scan_positions = [-50, -25, 0, 25, 50, 25, 0, -25, 0]

        for pan in scan_positions:
            steering = int(-pan * 0.25)
            tilt = 10 if pan > 0 else -10 if pan < 0 else 0

            self.set_many_angles(
                {
                    0: steering,
                    1: pan,
                    2: tilt,
                },
                duration=0.30
            )

        # Petit salut final.
        for _ in range(2):
            self.set_many_angles({1: 40, 2: -20}, duration=0.25)
            self.set_many_angles({1: 40, 2: 15}, duration=0.25)

        # Retour au centre.
        self.set_many_angles({0: 0, 1: 0, 2: 0}, duration=0.8)
        print("Démo terminée : servos revenus au neutre.")

    def center_servo(self, channel):
        self.set_servo_angle(channel, 0)

    def center_robot_servos(self):
        for channel in ROBOT_SERVOS:
            self.center_servo(channel)
            time.sleep(0.3)

    def deinit(self):
        self.stop_motor_channels()
        self.pca.deinit()


def print_help():
    print()
    print("Commandes :")
    print("  3 0          -> centre le servo libre branché sur CH3")
    print("  3 20         -> servo libre à +20°")
    print("  3 -20        -> servo libre à -20°")
    print("  0 -20        -> direction roues avant")
    print("  1 30         -> tête gauche-droite")
    print("  2 -20        -> tête haut-bas")
    print("  all 0        -> centre CH0, CH1, CH2")
    print("  demo         -> lance la démo signature")
    print("  signature    -> lance la démo signature")
    print("  show         -> lance la démo signature")
    print("  help         -> affiche cette aide")
    print("  q            -> quitter")
    print()


def main():
    controller = ServoController()

    print("=== Tâche 3 : Servomoteurs PiCar-B ===")
    print("Version sécurisée : CH15 interdit, test servo libre sur CH3.")
    print("Ne pas utiliser CH8 à CH15 : canaux liés aux moteurs.")
    print("Commande distinctive disponible : demo")
    print_help()

    try:
        while True:
            command = input("servo angle > ").strip().lower()

            if command in ("q", "quit", "exit"):
                break

            if command in ("help", "h", "?"):
                print_help()
                continue

            # Important : cette commande doit être testée avant le split,
            # car elle ne contient pas deux éléments du type "servo angle".
            if command in ("demo", "signature", "show"):
                controller.signature_demo()
                continue

            if not command:
                continue

            parts = command.split()

            if len(parts) != 2:
                print("Commande invalide. Exemple : 3 20")
                print("Tape 'help' pour voir les commandes disponibles.")
                continue

            servo_id_text, angle_text = parts

            try:
                angle = float(angle_text)
            except ValueError:
                print("Angle invalide.")
                continue

            if servo_id_text == "all":
                if angle != 0:
                    print("Utilise seulement : all 0")
                    continue
                controller.center_robot_servos()
                continue

            try:
                servo_id = int(servo_id_text)
                controller.set_servo_angle(servo_id, angle)
            except ValueError as error:
                print(error)

    except KeyboardInterrupt:
        print("\nArrêt clavier.")

    finally:
        print("Retour au centre des servos utilisés...")
        for channel in list(controller.servos.keys()):
            try:
                controller.center_servo(channel)
                time.sleep(0.2)
            except Exception:
                pass

        controller.deinit()
        print("Fin.")


if __name__ == "__main__":
    main()