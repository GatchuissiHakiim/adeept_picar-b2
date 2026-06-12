#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP2 Mastercamp - Systemes Embarques
#  Tache 11 : Suivi de ligne noire avec gestion d'obstacle
#
#  Auteur : Maiwen
#  Date   : 11 juin 2026
#
#  Gestion des virages serres : quand la ligne est perdue dans
#  un virage, le robot recule en CONTRE-BRAQUANT (facon creneau)
#  pour compenser son angle de braquage limite, puis repart.
# =============================================================

import sys
import select
import time

from gpiozero import LED

# --- Module moteur (Tache 4) ---
from drive import drive_full, drive, destroy

# --- Module ultrason + buzzer (Tache 5) ---
from tache5_ultrason import distance_mm, buzzer

# --- Module WS2812 (Tache 2) ---
from LEDWS2812_Controller import piloter_led, led

# --- Module LED Tache 1 : on reutilise SES numeros de broches ---
import control_leds

# --- Module servo de direction (Tache 3) ---
# set_servo_angle(angle) : negatif = gauche, positif = droite, 0 = centre
from etalonnage_servo_direction import set_servo_angle

# --- Module capteur de ligne (Tache 6) ---
# read_pattern() -> chaine "LMR" (0 = blanc, 1 = ligne noire)
from task6_line_tracking import LineTrackingSensor

# -------------------------------------------------------------
#  Parametres
# -------------------------------------------------------------
VITESSE_MARCHE = 30      # % du max : vitesse reduite (consigne)
VITESSE_RECUL  = 25      # % du max pour le recul
RAMPE          = 1.0     # rampe d'acceleration en marche avant (s)
PERIODE_BOUCLE = 0.2     # pause entre deux tours de boucle (s)

SEUIL_OBSTACLE = 200     # mm (20 cm) : distance d'arret, PARAMETRABLE (consigne)

PAUSE_AVANT_RECUL = 1.0  # 1 s entre l'arret et le recul (obstacle)
DUREE_RECUL       = 1.5  # s de recul obstacle -> A CALIBRER (~30 cm)
PAUSE_APRES       = 2.0  # 2 s d'arret avant reprise (obstacle)

ANGLE_VIRAGE    = 40     # degres de braquage pour suivre la ligne (a ajuster)
DUREE_MANOEUVRE = 0.6    # s de recul en contre-braquage (virage) -> A CALIBRER

# Phares avant rouges (canaux R), logique inverse -> active_high=False
phare_gauche = LED(control_leds.PIN_LEFT_R,  active_high=False)   # GPIO0
phare_droite = LED(control_leds.PIN_RIGHT_R, active_high=False)   # GPIO1

# Capteur de ligne (3 capteurs IR : gauche / milieu / droite)
capteur_ligne = LineTrackingSensor()

# Memoire du dernier cote ou la ligne a ete vue
#   -1 = ligne a gauche, +1 = ligne a droite, 0 = centre / inconnu
dernier_cote = 0


# -------------------------------------------------------------
#  Lecture clavier non bloquante
# -------------------------------------------------------------
def lire_touche():
    """Lit une touche au clavier SANS bloquer la boucle. None si rien."""
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:
        return sys.stdin.readline().strip()
    return None


# -------------------------------------------------------------
#  Feux de detresse (phares rouges + WS2812 rouges)
# -------------------------------------------------------------
def feux_on():
    phare_gauche.on()
    phare_droite.on()
    for i in range(14):
        piloter_led(i, 'R')


def feux_off():
    phare_gauche.off()
    phare_droite.off()
    led.set_all_led_color(0, 0, 0)


def clignoter_feux(duree, periode=0.4):
    fin = time.time() + duree
    etat = True
    while time.time() < fin:
        feux_on() if etat else feux_off()
        etat = not etat
        time.sleep(periode)
    feux_off()


# -------------------------------------------------------------
#  Recul avec Bip Bip (reaction obstacle)
# -------------------------------------------------------------
def reculer_avec_bip(duree):
    drive_full(VITESSE_RECUL, -1, ramp_time=0.5)
    fin = time.time() + duree
    while time.time() < fin:
        buzzer.play("C5")
        time.sleep(0.15)
        buzzer.stop()
        time.sleep(0.15)
    drive(0)


# -------------------------------------------------------------
#  Sequence complete de reaction a l'obstacle
# -------------------------------------------------------------
def reaction_obstacle():
    drive(0)
    set_servo_angle(0)
    print(">> Feux de detresse")
    clignoter_feux(PAUSE_AVANT_RECUL)

    print(">> Recul + Bip Bip")
    feux_on()
    reculer_avec_bip(DUREE_RECUL)

    print(">> Pause 2 s")
    clignoter_feux(PAUSE_APRES)
    feux_off()


# -------------------------------------------------------------
#  Manoeuvre de virage serre (ligne perdue, pattern 000)
#  Le robot recule en CONTRE-BRAQUANT pour se repositionner,
#  puis repart en avant. Compense l'angle de braquage limite.
# -------------------------------------------------------------
def manoeuvre_virage():
    print(">> Virage serre : manoeuvre de repositionnement")
    drive(0)

    # On recule en braquant a l'OPPOSE du cote ou etait la ligne
    if dernier_cote == +1:               # ligne a droite -> recul roues a GAUCHE
        set_servo_angle(ANGLE_VIRAGE)
    elif dernier_cote == -1:             # ligne a gauche -> recul roues a DROITE
        set_servo_angle(-ANGLE_VIRAGE)
    else:                                # cote inconnu -> recul tout droit
        set_servo_angle(0)

    # Recul de repositionnement
    drive_full(VITESSE_RECUL, -1, ramp_time=0.3)
    time.sleep(DUREE_MANOEUVRE)
    drive(0)

    # On remet droit et on repart en avant
    set_servo_angle(0)
    drive_full(VITESSE_MARCHE, 1, ramp_time=RAMPE)


# -------------------------------------------------------------
#  Suivi de ligne : corrige la direction selon les 3 capteurs
#  Convention : 0 = blanc, 1 = ligne noire
# -------------------------------------------------------------
def suivre_ligne():
    global dernier_cote
    pattern = capteur_ligne.read_pattern()      # ex : "010"

    if pattern == "010":                        # ligne centree
        set_servo_angle(0)
        dernier_cote = 0
    elif pattern in ("100", "110"):             # ligne a gauche
        set_servo_angle(ANGLE_VIRAGE)
        dernier_cote = -1
    elif pattern in ("001", "011"):             # ligne a droite
        set_servo_angle(-ANGLE_VIRAGE)
        dernier_cote = +1
    elif pattern == "111":                      # noir partout -> tout droit
        set_servo_angle(0)
    elif pattern == "000":                      # ligne perdue -> manoeuvre
        manoeuvre_virage()


# -------------------------------------------------------------
#  Programme principal
# -------------------------------------------------------------
def main():
    print("=== Tache 11 - Suivi de ligne + detection obstacle ===")
    print("Commandes : 'M' = marche / 'A' = arret / Ctrl+C = quitter")

    feux_off()
    set_servo_angle(0)                # roues droites au depart
    en_marche = False

    try:
        while True:
            # --- 1. Lecture clavier ---
            touche = lire_touche()
            if touche is not None:
                if touche in ('M', 'm'):
                    en_marche = True
                    print(">> Commande M : MARCHE")
                    drive_full(VITESSE_MARCHE, 1, ramp_time=RAMPE)
                elif touche in ('A', 'a'):
                    en_marche = False
                    print(">> Commande A : ARRET")
                    drive(0)
                    set_servo_angle(0)
                else:
                    print(f">> Touche ignoree : '{touche}'")

            # --- 2. Si en marche : obstacle prioritaire, sinon suivi ligne ---
            if en_marche:
                distance = distance_mm()
                if distance is not None and distance < SEUIL_OBSTACLE:
                    print(f">> OBSTACLE a {distance:.0f} mm")
                    reaction_obstacle()
                    print(">> Reprise de la marche")
                    drive_full(VITESSE_MARCHE, 1, ramp_time=RAMPE)
                else:
                    suivre_ligne()            # pas d'obstacle -> on suit la ligne

            # --- 3. Pause ---
            time.sleep(PERIODE_BOUCLE)

    except KeyboardInterrupt:
        print("\nFin de programme par Ctrl-C")

    finally:
        drive(0)
        set_servo_angle(0)
        feux_off()
        buzzer.stop()
        destroy()
        print("Nettoyage final realise")


if __name__ == "__main__":
    main()
