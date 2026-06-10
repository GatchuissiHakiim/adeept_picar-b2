#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP2 Mastercamp - Systemes Embarques
#  Tache 10 : Suivi de source lumineuse avec gestion d'obstacle
#
#  Auteur : Maiwen
#  Date   : 10 juin 2026
#
#  BRIQUE 5 : suivi de lumiere (servo de direction) integre
#             aux briques 1-4 (clavier, moteur, obstacle, detresse)
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
# set_servo_angle(angle) : -100 (gauche) a +100 (droite), 0 = centre
from etalonnage_servo_direction import set_servo_angle

# --- Module capteur de lumiere (Tache 8) ---
# LightTrackingSensor : calibrate(), read_value(), classify_value()
from task8_light_tracking import LightTrackingSensor

# -------------------------------------------------------------
#  Parametres
# -------------------------------------------------------------
VITESSE_MARCHE = 25      # % du max : vitesse reduite (consigne)
VITESSE_RECUL  = 25      # % du max pour le recul
RAMPE          = 1.0     # rampe d'acceleration en marche avant (s)
PERIODE_BOUCLE = 0.2     # pause entre deux tours de boucle (s)

SEUIL_OBSTACLE = 200     # mm (20 cm) : distance d'arret sur obstacle

PAUSE_AVANT_RECUL = 1.0  # 1 s entre l'arret et le recul (consigne)
DUREE_RECUL       = 1.5  # s de recul -> A CALIBRER pour obtenir ~30 cm
PAUSE_APRES       = 2.0  # 2 s d'arret avant reprise (consigne)

ANGLE_VIRAGE   = 40      # degres de braquage pour suivre la lumiere (a ajuster)

# Phares avant rouges (canaux R), logique inverse -> active_high=False
phare_gauche = LED(control_leds.PIN_LEFT_R,  active_high=False)   # GPIO0
phare_droite = LED(control_leds.PIN_RIGHT_R, active_high=False)   # GPIO1

# Capteur de lumiere (sera calibre au premier M)
capteur_lumiere = LightTrackingSensor()


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
#  Recul avec Bip Bip
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
    set_servo_angle(0)                # roues droites pendant la manoeuvre
    print(">> Feux de detresse")
    clignoter_feux(PAUSE_AVANT_RECUL)

    print(">> Recul + Bip Bip")
    feux_on()
    reculer_avec_bip(DUREE_RECUL)

    print(">> Pause 2 s")
    clignoter_feux(PAUSE_APRES)
    feux_off()


# -------------------------------------------------------------
#  Suivi de lumiere : oriente le servo selon l'etat du capteur
# -------------------------------------------------------------
def suivre_lumiere():
    valeur = capteur_lumiere.read_value()
    etat, ecart, _ = capteur_lumiere.classify_value(valeur)

    if etat == "balanced":
        set_servo_angle(0)                   # source en face -> tout droit
    elif etat == "low":
        set_servo_angle(-ANGLE_VIRAGE)       # A VERIFIER : tourner a gauche
    elif etat == "high":
        set_servo_angle(ANGLE_VIRAGE)        # A VERIFIER : tourner a droite


# -------------------------------------------------------------
#  Programme principal
# -------------------------------------------------------------
def main():
    print("=== Tache 10 - Brique 5 (suivi lumiere + obstacle) ===")
    print("Commandes : 'M' = marche / 'A' = arret / Ctrl+C = quitter")

    feux_off()
    set_servo_angle(0)                # roues droites au depart
    en_marche = False
    deja_calibre = False              # le capteur sera calibre au 1er M

    try:
        while True:
            # --- 1. Lecture clavier ---
            touche = lire_touche()
            if touche is not None:
                if touche in ('M', 'm'):
                    # Calibration du capteur lumiere au tout premier M
                    if not deja_calibre:
                        print(">> Calibration lumiere : ne touchez pas au capteur...")
                        capteur_lumiere.calibrate()
                        deja_calibre = True
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

            # --- 2. Si en marche : obstacle prioritaire, sinon suivi lumiere ---
            if en_marche:
                distance = distance_mm()
                if distance is not None and distance < SEUIL_OBSTACLE:
                    print(f">> OBSTACLE a {distance:.0f} mm")
                    reaction_obstacle()
                    print(">> Reprise de la marche")
                    drive_full(VITESSE_MARCHE, 1, ramp_time=RAMPE)
                else:
                    suivre_lumiere()          # pas d'obstacle -> on suit la lumiere

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