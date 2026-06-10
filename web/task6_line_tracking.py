#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tâche 6 : Capteur de suivi de ligne - Adeept PiCar-B

Objectif :
- Mesurer l'état des 3 capteurs IR réflectifs du module de suivi de ligne.
- Afficher les valeurs gauche / milieu / droite.
- Afficher un pattern binaire LMR.
- Donner une interprétation adaptée au comportement observé sur notre robot.

Comportement observé sur notre PiCar-B :
- 0 = réflexion détectée, surface claire proche
- 1 = faible réflexion, ligne noire, vide ou surface trop éloignée

Module connecté sur X8 Line Tracking :
- Gauche : GPIO22
- Milieu : GPIO27
- Droite : GPIO17

Arrêt du programme :
Ctrl + C
"""

import time
from gpiozero import InputDevice


# Broches utilisées par le module Line Tracking Adeept.
LINE_PIN_LEFT = 22
LINE_PIN_MIDDLE = 27
LINE_PIN_RIGHT = 17

# Fréquence d'affichage.
DEFAULT_INTERVAL = 0.20

# Si True, affiche uniquement quand l'état change.
# C'est beaucoup plus lisible pour la démonstration.
ONLY_ON_CHANGE = True


class LineTrackingSensor:
    def __init__(self):
        self.left = InputDevice(pin=LINE_PIN_LEFT)
        self.middle = InputDevice(pin=LINE_PIN_MIDDLE)
        self.right = InputDevice(pin=LINE_PIN_RIGHT)

        self.last_pattern = None
        self.state_counter = {}

    def read_raw(self):
        """
        Lit directement les trois capteurs.

        Retour :
            tuple (left, middle, right)
            Chaque valeur vaut 0 ou 1.
        """
        left_value = self.left.value
        middle_value = self.middle.value
        right_value = self.right.value

        return left_value, middle_value, right_value

    def read_pattern(self):
        """
        Retourne l'état sous forme texte LMR, par exemple :
            "000"
            "010"
            "111"
        """
        left_value, middle_value, right_value = self.read_raw()
        return f"{left_value}{middle_value}{right_value}"

    def interpret_pattern(self, pattern):
        """
        Interprétation adaptée au comportement observé sur notre PiCar-B.

        Dans notre montage :
        - 0 = réflexion détectée, surface claire proche
        - 1 = faible réflexion, ligne noire, vide ou surface trop éloignée
        """
        interpretations = {
            "000": "surface claire sous les 3 capteurs",
            "010": "ligne noire probablement centrée",
            "100": "ligne noire détectée côté gauche",
            "001": "ligne noire détectée côté droit",
            "110": "ligne noire entre gauche et centre",
            "011": "ligne noire entre centre et droit",
            "101": "cas ambigu : gauche et droit sombres, centre clair",
            "111": "noir partout, vide, ou surface trop éloignée",
        }

        return interpretations.get(pattern, "état inconnu")

    def visual_bar(self, pattern):
        """
        Représentation visuelle rapide des trois capteurs.

        B = Blanc / réflexion détectée / surface claire proche
        N = Noir / faible réflexion / ligne noire / vide / trop loin
        """
        symbols = []

        for bit in pattern:
            if bit == "1":
                symbols.append("N")
            else:
                symbols.append("B")

        return " ".join(symbols)

    def update_counter(self, pattern):
        if pattern not in self.state_counter:
            self.state_counter[pattern] = 0

        self.state_counter[pattern] += 1

    def print_state(self, force=False):
        pattern = self.read_pattern()
        self.update_counter(pattern)

        if ONLY_ON_CHANGE and not force and pattern == self.last_pattern:
            return

        left_value = pattern[0]
        middle_value = pattern[1]
        right_value = pattern[2]

        interpretation = self.interpret_pattern(pattern)
        visual = self.visual_bar(pattern)

        print(
            f"L:{left_value} M:{middle_value} R:{right_value} | "
            f"pattern: {pattern} | "
            f"{visual} | "
            f"{interpretation}"
        )

        self.last_pattern = pattern

    def print_summary(self):
        print()
        print("Résumé des états observés :")

        if not self.state_counter:
            print("Aucune mesure enregistrée.")
            return

        total = sum(self.state_counter.values())

        for pattern, count in sorted(self.state_counter.items()):
            percent = (count / total) * 100
            interpretation = self.interpret_pattern(pattern)

            print(
                f"  {pattern} : {count:4d} mesures "
                f"({percent:5.1f} %) -> {interpretation}"
            )


def print_start_message():
    print("=== Tâche 6 : Capteur de suivi de ligne ===")
    print("Lecture des 3 capteurs IR réflectifs du module X8.")
    print()
    print("Format :")
    print("  L = capteur gauche")
    print("  M = capteur central")
    print("  R = capteur droit")
    print()
    print("Convention observée sur notre PiCar-B :")
    print("  0 = surface claire proche / réflexion détectée")
    print("  1 = ligne noire, vide, trop loin, ou faible réflexion")
    print()
    print("Visualisation :")
    print("  B = Blanc / réflexion détectée")
    print("  N = Noir / faible réflexion")
    print()
    print("Exemples attendus :")
    print("  L:0 M:0 R:0 | pattern: 000 | B B B | surface claire sous les 3 capteurs")
    print("  L:0 M:1 R:0 | pattern: 010 | B N B | ligne noire probablement centrée")
    print("  L:1 M:0 R:0 | pattern: 100 | N B B | ligne noire détectée côté gauche")
    print("  L:0 M:0 R:1 | pattern: 001 | B B N | ligne noire détectée côté droit")
    print()
    print("Test conseillé :")
    print("  1. Placer une feuille claire sous le module.")
    print("  2. Observer l'état 000 si les trois capteurs voient le clair.")
    print("  3. Déplacer une ligne noire sous le capteur gauche, central, puis droit.")
    print("  4. Vérifier que les bits L, M, R changent dans le bon ordre.")
    print()
    print("Arrêt : Ctrl + C")
    print()


def main():
    sensor = LineTrackingSensor()
    print_start_message()

    try:
        # Affiche forcément la première mesure.
        sensor.print_state(force=True)

        while True:
            sensor.print_state()
            time.sleep(DEFAULT_INTERVAL)

    except KeyboardInterrupt:
        print("\nArrêt du programme demandé.")

    finally:
        sensor.print_summary()
        print("Fin.")


if __name__ == "__main__":
    main()
