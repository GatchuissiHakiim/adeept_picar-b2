#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP2 Mastercamp - Systemes Embarques
#  Tache 11 : Suivi de ligne noire avec gestion d'obstacle
#
#  Auteur : Maiwen
#  Date   : 11 juin 2026
#
#  Reutilise les modules : moteur (drive), ultrason (tache5),
#  WS2812, phares (control_leds), servo (etalonnage_servo),
#  capteur de ligne (task6_line_tracking).
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
# read_pattern() -> chaine "LMR", ex "010"
#   convention : 0 = surface claire (blanc) / 1 = ligne noire (ou vide)
from task6_line_tracking import LineTrackingSensor

# -------------------------------------------------------------
#  Parametres
# -------------------------------------------------------------
VITESSE_MARCHE = 20     # % du max : vitesse reduite (consigne)
VITESSE_RECUL  = 25      # % du max pour le recul
RAMPE          = 1.0     # rampe d'acceleration en marche avant (s)
PERIODE_BOUCLE = 0.2     # pause entre deux tours de boucle (s)

SEUIL_OBSTACLE = 200     # mm (20 cm) : distance d'arret, PARAMETRABLE (consigne)

PAUSE_AVANT_RECUL = 1.0  # 1 s entre l'arret et le recul
DUREE_RECUL       = 1.5  # s de recul obstacle -> A CALIBRER (~30 cm)
PAUSE_APRES       = 2.0  # 2 s d'arret avant reprise

ANGLE_VIRAGE     = 40    # degres de braquage pour suivre la ligne (a ajuster)
MAX_ESSAIS_RECUL = 5     # nb de petits reculs avant d'abandonner la recherche

# Phares avant rouges (canaux R), logique inverse -> active_high=False
phare_gauche = LED(control_leds.PIN_LEFT_R,  active_high=False)   # GPIO0
phare_droite = LED(control_leds.PIN_RIGHT_R, active_high=False)   # GPIO1

# Capteur de ligne (3 capteurs IR : gauche / milieu / droite)
capteur_ligne = LineTrackingSensor()


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
#  Recherche de la ligne quand elle est perdue (pattern 000)
# -------------------------------------------------------------
def retrouver_ligne():
    """Recule par petits coups jusqu'a revoir la ligne, avec une limite."""
    print(">> Ligne perdue : recul pour la retrouver")
    drive(0)
    essais = 0
    while essais < MAX_ESSAIS_RECUL:
        drive_full(VITESSE_RECUL, -1, ramp_time=0.3)   # petit recul
        time.sleep(0.3)
        drive(0)
        if capteur_ligne.read_pattern() != "000":      # ligne revue ?
            print(">> Ligne retrouvee")
            return
        essais += 1
    print(">> Ligne introuvable : arret")


# -------------------------------------------------------------
#  Suivi de ligne : corrige la direction selon les 3 capteurs
#  Convention : 0 = blanc, 1 = ligne noire
# -------------------------------------------------------------
def suivre_ligne():
    pattern = capteur_ligne.read_pattern()

    if pattern == "010":
        print("capteur milieu active :",pattern)
        set_servo_angle(0)
    elif pattern in ("100", "110"):
        print("capteur droit  pas active :", pattern)
        set_servo_angle(ANGLE_VIRAGE)
    elif pattern in ("001", "011"):
        print("in 001,011", pattern)
        set_servo_angle(-ANGLE_VIRAGE)
    elif pattern == "111":
        print("full:", pattern)
        set_servo_angle(0)
    elif pattern == "000":
        retrouver_ligne()
        set_servo_angle(0)                          # roues droites
        drive_full(VITESSE_MARCHE, 1, ramp_time=RAMPE)   # ON REPART


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