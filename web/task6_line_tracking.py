"""
Tâche 6 : Capteur de suivi de ligne - Adeept PiCar-B

Objectif :
- Mesurer l'état des 3 capteurs IR réflectifs du module de suivi de ligne.
- Afficher les valeurs gauche / milieu / droite.
- Afficher un pattern binaire LMR.
- Donner une interprétation adaptée au comportement observé sur notre robot.

Comportement observé sur notre PiCar-B :
- 0 = réflexion détectée : surface claire/proche/réfléchissante
- 1 = faible réflexion : ligne noire, vide, trop loin, ou surface peu réfléchissante

Attention :
Mettre un doigt sous un capteur ne simule pas forcément une ligne noire.
La peau peut réfléchir l'infrarouge si elle est très proche du capteur.
Donc un doigt proche peut produire 0, pas 1.

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

        Convention :
        - 0 = réflexion détectée : surface claire/proche/réfléchissante
        - 1 = faible réflexion : ligne noire, vide, trop loin, ou surface sombre

        Pour une vraie piste de suivi :
        - une ligne noire sous un capteur tend à faire passer ce capteur à 1.
        - une feuille claire proche tend à produire 0.
        """
        interpretations = {
            "000": "surface claire/proche sous les 3 capteurs",
            "010": "ligne noire probablement centrée",
            "100": "ligne noire détectée côté gauche",
            "001": "ligne noire détectée côté droit",
            "110": "ligne noire entre gauche et centre",
            "011": "ligne noire entre centre et droit",
            "101": "centre réfléchissant/proche, côtés sombres/vides/trop loin",
            "111": "noir partout, vide, trop loin, ou absence de réflexion",
        }

        return interpretations.get(pattern, "état inconnu")

    def visual_bar(self, pattern):
        """
        Représentation visuelle rapide des trois capteurs.

        R = réflexion détectée, surface claire/proche/réfléchissante
        F = faible réflexion, ligne noire/vide/trop loin
        """
        symbols = []

        for bit in pattern:
            if bit == "0":
                symbols.append("R")
            else:
                symbols.append("F")

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
    print("  0 = réflexion détectée : surface claire/proche/réfléchissante")
    print("  1 = faible réflexion : ligne noire, vide, trop loin, ou surface sombre")
    print()
    print("Visualisation :")
    print("  R = réflexion détectée")
    print("  F = faible réflexion")
    print()
    print("Exemples attendus :")
    print("  L:0 M:0 R:0 | pattern: 000 | R R R | surface claire/proche sous les 3 capteurs")
    print("  L:0 M:1 R:0 | pattern: 010 | R F R | ligne noire probablement centrée")
    print("  L:1 M:0 R:0 | pattern: 100 | F R R | ligne noire détectée côté gauche")
    print("  L:0 M:0 R:1 | pattern: 001 | R R F | ligne noire détectée côté droit")
    print("  L:1 M:0 R:1 | pattern: 101 | F R F | centre réfléchissant/proche, côtés sans reflet")
    print()
    print("Important :")
    print("  Un doigt proche peut réfléchir l'infrarouge et donc produire 0.")
    print("  Pour simuler une vraie ligne noire, utiliser plutôt du ruban noir ou un marqueur noir mat.")
    print()
    print("Test conseillé :")
    print("  1. Robot surélevé : on observe souvent 111 si les capteurs ne voient rien.")
    print("  2. Feuille claire proche : on attend plutôt 000.")
    print("  3. Ligne noire centrée : on attend plutôt 010.")
    print("  4. Vérifier séparément gauche, centre, droite avec une bande noire.")
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