#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP Mastercamp - Systemes Embarques
#  Tache 1 : Controle ON/OFF des 9 LED du robot
#    - 3 LED embarquees sur la HAT  : LED1, LED2, LED3
#    - 2 feux avant RGB             : gauche (R/G/B) + droite (R/G/B)
#
#  Auteur : Maïwen
#  Date   : 2026/06
# =============================================================

import time
from gpiozero import LED

# -------------------------------------------------------------
# Cablage des LED (numerotation BCM des GPIO)
# Source : 01_LED.py (Lesson 5) et 05_RGB.py du kit adeept_picar-b2
# -------------------------------------------------------------

# --- LED embarquees de la HAT : logique NORMALE ---

PIN_LED1 = 9
PIN_LED2 = 25
PIN_LED3 = 11

# --- Feux avant RGB : logique INVERSE ---

PIN_LEFT_R  = 0
PIN_LEFT_G  = 19
PIN_LEFT_B  = 13
PIN_RIGHT_R = 1
PIN_RIGHT_G = 5
PIN_RIGHT_B = 6

# Dictionnaire : numero (1..9) -> [nom lisible, objet LED]
leds = {}


def setup():
    global leds
    leds = {
        1: ["LED1",    LED(PIN_LED1)],                       # logique normale
        2: ["LED2",    LED(PIN_LED2)],
        3: ["LED3",    LED(PIN_LED3)],
        4: ["left_R",  LED(PIN_LEFT_R,  active_high=False)], # logique inverse
        5: ["left_G",  LED(PIN_LEFT_G,  active_high=False)],
        6: ["left_B",  LED(PIN_LEFT_B,  active_high=False)],
        7: ["right_R", LED(PIN_RIGHT_R, active_high=False)],
        8: ["right_G", LED(PIN_RIGHT_G, active_high=False)],
        9: ["right_B", LED(PIN_RIGHT_B, active_high=False)],
    }


def set_led(num, status):
    """C'est la fonction modulaire demandee au point 3 : elle pilote
    individuellement n'importe laquelle des 9 LED, en ON/OFF.
    """
    if num not in leds:
        print(f"  /!\\ Numero de LED invalide : {num} (attendu 1..9)")
        return

    nom, led = leds[num]
    if status == 1:
        led.on()
        print(f"  {nom} (#{num}) -> ON")
    elif status == 0:
        led.off()
        print(f"  {nom} (#{num}) -> OFF")
    else:
        print(f"  /!\\ Statut invalide : {status} (attendu 0 ou 1)")


def all_off():
    """Eteint les 9 LED (etat connu de depart / de fin)."""
    for num in leds:
        set_led(num, 0)


def afficher_aide():
    print("=" * 52)
    print("   Controle manuel des LED - code a 2 chiffres : XY")
    print("   X = 1 -> ALLUMER   |   X = 2 -> ETEINDRE")
    print("   Y = 1..9 -> numero de la LED")
    print("   ex : 14 = allumer left_R   |   29 = eteindre right_B")
    print("   commandes : 'all' = tout eteindre  |  'q' = quitter")
    print("-" * 52)
    print("   1=LED1   2=LED2   3=LED3")
    print("   4=left_R 5=left_G 6=left_B")
    print("   7=right_R 8=right_G 9=right_B")
    print("=" * 52)


def main():
    """Point 4 : validation par commande manuelle via input()."""
    setup()
    all_off()          # on demarre avec toutes les LED eteintes
    afficher_aide()

    try:
        while True:
            cmd = input("\nCommande > ").strip().lower()

            if cmd in ("q", "quit", "exit"):
                break
            if cmd == "all":
                all_off()
                continue
            if cmd in ("?", "aide", "help"):
                afficher_aide()
                continue

            # On attend exactement 2 chiffres : ex "14" ou "29"
            if len(cmd) != 2 or not cmd.isdigit():
                print("  Format invalide. Entrez 2 chiffres (ex : 14).")
                continue

            action = int(cmd[0])   # 1 = allumer, 2 = eteindre
            num    = int(cmd[1])   # 1..9

            if action == 1:
                set_led(num, 1)
            elif action == 2:
                set_led(num, 0)
            else:
                print("  Premier chiffre invalide (1=allumer, 2=eteindre).")

    except KeyboardInterrupt:
        pass
    finally:
        all_off()
        print("\nToutes les LED eteintes. Fin du programme.")


if __name__ == "__main__":
    main()