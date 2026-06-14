#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP2 Mastercamp - Systemes Embarques
#  Tache 11 : Suivi de ligne noire (3 cm) avec gestion d'obstacle
#
#  Auteur : Maïwen CHRIST
#  Date   : 12 juin 2026
#
#  Suivi de ligne a 3 niveaux de vitesse :
#   - 111            -> ligne droite       : vitesse NORMALE
#   - 110 / 011      -> leger decalage      : vitesse / 2
#   - 100 / 001      -> virage serre        : vitesse / 3
#   - 000            -> ligne perdue        : manoeuvre (recul contre-braque)
#  La derniere direction connue (dernier_cote) n'est mise a jour que
#  sur un decalage, jamais en ligne droite : on la garde en memoire
#  pour bien contre-braquer au moment ou la ligne est perdue.
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
from etalonnage_servo_direction import set_servo_angle

# --- Module capteur de ligne (Tache 6) ---
# read_pattern() -> chaine "LMR" (0 = blanc, 1 = ligne noire)
from task6_line_tracking import LineTrackingSensor

# -------------------------------------------------------------
#  Parametres
# -------------------------------------------------------------
VITESSE_NORMALE = 30     # % du max : ligne droite
VITESSE_RECUL   = 25     # % du max : recul (obstacle / manoeuvre)
RAMPE           = 1.0    # rampe d'acceleration au demarrage (s)
PERIODE_BOUCLE  = 0.15   # pause entre deux tours de boucle (s)

SEUIL_OBSTACLE = 200     # mm (20 cm) : distance d'arret, PARAMETRABLE (consigne)

PAUSE_AVANT_RECUL = 1.0  # 1 s entre l'arret et le recul (obstacle)
DUREE_RECUL       = 1.5  # s de recul obstacle -> A CALIBRER (~30 cm)
PAUSE_APRES       = 2.0  # 2 s d'arret avant reprise (obstacle)

ANGLE_VIRAGE    = 40     # degres de braquage (a ajuster)
DUREE_MANOEUVRE = 0.6    # s de recul en contre-braquage -> A CALIBRER

# Phares avant rouges (canaux R), logique inverse -> active_high=False
phare_gauche = LED(control_leds.PIN_LEFT_R,  active_high=False)   # GPIO0
phare_droite = LED(control_leds.PIN_RIGHT_R, active_high=False)   # GPIO1

# Capteur de ligne (3 capteurs IR : gauche / milieu / droite)
capteur_ligne = LineTrackingSensor()

# Etat du suivi
dernier_cote     = 0     # -1 = ligne a gauche, +1 = a droite, 0 = inconnu
vitesse_actuelle = 0     # vitesse moteur courante (relance seulement si ca change)


# -------------------------------------------------------------
#  Direction : sens de braquage centralise
#  *** Sur CE robot : angle POSITIF = braquer a GAUCHE ***
#  (si un sens est inverse au test, echanger le contenu des
#   deux fonctions ci-dessous : c'est le SEUL endroit a changer)
# -------------------------------------------------------------
def braquer_gauche():
    set_servo_angle(ANGLE_VIRAGE)

def braquer_droite():
    set_servo_angle(-ANGLE_VIRAGE)

def roues_droites():
    set_servo_angle(0)


# -------------------------------------------------------------
#  Vitesse : ne relance le moteur que si la vitesse CHANGE
#  (evite de relancer la rampe a chaque tour de boucle)
# -------------------------------------------------------------
def rouler(vitesse):
    global vitesse_actuelle
    if vitesse != vitesse_actuelle:
        drive_full(vitesse, 1, ramp_time=0.4)
        vitesse_actuelle = vitesse


def repartir():
    """Relance la marche avant a vitesse normale (apres obstacle/manoeuvre)."""
    global vitesse_actuelle
    drive_full(VITESSE_NORMALE, 1, ramp_time=RAMPE)
    vitesse_actuelle = VITESSE_NORMALE


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
    global vitesse_actuelle
    drive_full(VITESSE_RECUL, -1, ramp_time=0.5)
    vitesse_actuelle = 0
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
    global vitesse_actuelle
    drive(0)
    vitesse_actuelle = 0
    roues_droites()
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
#  Recule en CONTRE-BRAQUANT selon la derniere direction connue,
#  puis repart en avant a vitesse normale.
# -------------------------------------------------------------
def manoeuvre_virage():
    global vitesse_actuelle
    print(">> Ligne perdue : manoeuvre de repositionnement")
    drive(0)
    vitesse_actuelle = 0

    # Contre-braquage : roues a l'OPPOSE du cote ou etait la ligne
    if dernier_cote == +1:          # ligne perdue a DROITE -> roues a GAUCHE
        braquer_gauche()
    elif dernier_cote == -1:        # ligne perdue a GAUCHE -> roues a DROITE
        braquer_droite()
    else:
        roues_droites()             # cote inconnu -> recul tout droit

    time.sleep(0.2)                 # laisse le servo tourner AVANT de reculer

    drive_full(VITESSE_RECUL, -1, ramp_time=0.3)
    time.sleep(DUREE_MANOEUVRE)
    drive(0)

    roues_droites()
    repartir()                      # on repart en avant a vitesse normale


# -------------------------------------------------------------
#  Suivi de ligne (coeur de la tache)
#  Convention capteurs : 0 = blanc, 1 = ligne noire
#  Plus le robot est decale, plus il ralentit.
# -------------------------------------------------------------
def suivre_ligne():
    global dernier_cote
    pattern = capteur_ligne.read_pattern()      # ex : "111"

    if pattern == "111":                        # ligne droite -> tout droit
        roues_droites()
        rouler(VITESSE_NORMALE)
        # on NE touche PAS a dernier_cote : on garde la derniere direction connue

    elif pattern == "110":                      # leger decalage a gauche
        braquer_gauche()
        rouler(VITESSE_NORMALE // 2)            # vitesse / 2
        dernier_cote = -1

    elif pattern == "011":                      # leger decalage a droite
        braquer_droite()
        rouler(VITESSE_NORMALE // 2)
        dernier_cote = +1

    elif pattern == "100":                      # virage serre a gauche
        braquer_gauche()
        rouler(VITESSE_NORMALE // 3)            # vitesse / 3
        dernier_cote = -1

    elif pattern == "001":                      # virage serre a droite
        braquer_droite()
        rouler(VITESSE_NORMALE // 3)
        dernier_cote = +1

    elif pattern == "010":                      # centre seul -> tout droit
        roues_droites()
        rouler(VITESSE_NORMALE)

    elif pattern == "000":                      # ligne perdue -> manoeuvre
        manoeuvre_virage()


# -------------------------------------------------------------
#  Programme principal
# -------------------------------------------------------------
def main():
    global vitesse_actuelle
    print("=== Tache 11 - Suivi de ligne + detection obstacle ===")
    print("Commandes : 'M' = marche / 'A' = arret / Ctrl+C = quitter")

    feux_off()
    roues_droites()
    en_marche = False

    try:
        while True:
            # --- 1. Lecture clavier ---
            touche = lire_touche()
            if touche is not None:
                if touche in ('M', 'm'):
                    en_marche = True
                    print(">> Commande M : MARCHE")
                    repartir()
                elif touche in ('A', 'a'):
                    en_marche = False
                    print(">> Commande A : ARRET")
                    drive(0)
                    vitesse_actuelle = 0
                    roues_droites()
                else:
                    print(f">> Touche ignoree : '{touche}'")

            # --- 2. Si en marche : obstacle prioritaire, sinon suivi ligne ---
            if en_marche:
                distance = distance_mm()
                if distance is not None and distance < SEUIL_OBSTACLE:
                    print(f">> OBSTACLE a {distance:.0f} mm")
                    reaction_obstacle()
                    print(">> Reprise de la marche")
                    repartir()
                else:
                    suivre_ligne()

            # --- 3. Pause ---
            time.sleep(PERIODE_BOUCLE)

    except KeyboardInterrupt:
        print("\nFin de programme par Ctrl-C")

    finally:
        drive(0)
        roues_droites()
        feux_off()
        buzzer.stop()
        destroy()
        print("Nettoyage final realise")


if __name__ == "__main__":
    main()