#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP2 Mastercamp - Systemes Embarques
#  Tache 10 : Suivi de source lumineuse avec gestion d'obstacle
#
#  Auteur : Maiwen
#  Date   : 10 juin 2026
#
#  BRIQUE 4 : reaction complete a l'obstacle
#             (feux de detresse + recul ~30 cm + Bip Bip + pause)
# =============================================================

import sys
import select
import time

from gpiozero import LED

# --- Module moteur (Tache 4) ---
from drive import drive_full, drive, destroy

# --- Module ultrason + buzzer (Tache 5) ---
# distance_mm() : distance en mm (moyenne de 5 mesures) ou None
# buzzer        : TonalBuzzer sur GPIO18 (.play("C5") / .stop())
from tache5_ultrason import distance_mm, buzzer

# --- Module WS2812 (Tache 2) ---
# piloter_led(numero, couleur) : couleur 'R','G','B','N'
# led.set_all_led_color(r,g,b) : eteint tout avec (0,0,0)
from LEDWS2812_Controller import piloter_led, led

# --- Module LED Tache 1 : on reutilise SES numeros de broches ---
# (on n'appelle PAS control_leds.setup() : il creerait LED1/LED3 sur
#  GPIO9/GPIO11, qui sont reserves par le SPI utilise par les WS2812.
#  On n'initialise donc que les phares avant, dont les broches ne sont
#  pas des broches SPI -> pas de conflit "GPIO busy".)
import control_leds

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

# Phares avant rouges (canaux R des 2 feux), logique inverse -> active_high=False
phare_gauche = LED(control_leds.PIN_LEFT_R,  active_high=False)   # GPIO0
phare_droite = LED(control_leds.PIN_RIGHT_R, active_high=False)   # GPIO1


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
    for i in range(14):          # les 14 WS2812 en rouge
        piloter_led(i, 'R')


def feux_off():
    phare_gauche.off()
    phare_droite.off()
    led.set_all_led_color(0, 0, 0)


def clignoter_feux(duree, periode=0.4):
    """Fait clignoter les feux de detresse pendant 'duree' secondes."""
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
    """Recule a vitesse reduite pendant 'duree' s en emettant des bips."""
    drive_full(VITESSE_RECUL, -1, ramp_time=0.5)   # lance le recul
    fin = time.time() + duree
    while time.time() < fin:
        buzzer.play("C5")
        time.sleep(0.15)
        buzzer.stop()
        time.sleep(0.15)
    drive(0)                                        # stop apres le recul


# -------------------------------------------------------------
#  Sequence complete de reaction a l'obstacle
# -------------------------------------------------------------
def reaction_obstacle():
    drive(0)                          # 1. arret immediat
    print(">> Feux de detresse")
    clignoter_feux(PAUSE_AVANT_RECUL) #    feux clignotants pendant 1 s

    print(">> Recul + Bip Bip")
    feux_on()                         # 2. feux fixes pendant le recul
    reculer_avec_bip(DUREE_RECUL)     #    recul ~30 cm avec Bip Bip

    print(">> Pause 2 s")
    clignoter_feux(PAUSE_APRES)       # 3. feux clignotants pendant 2 s
    feux_off()                        #    puis tout eteint -> reprise


# -------------------------------------------------------------
#  Programme principal
# -------------------------------------------------------------
def main():
    print("=== Tache 10 - Brique 4 (reaction obstacle complete) ===")
    print("Commandes : 'M' = marche / 'A' = arret / Ctrl+C = quitter")

    feux_off()                        # etat de depart : tout eteint
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
                else:
                    print(f">> Touche ignoree : '{touche}'")

            # --- 2. Surveillance obstacle si en marche ---
            if en_marche:
                distance = distance_mm()
                if distance is not None and distance < SEUIL_OBSTACLE:
                    print(f">> OBSTACLE a {distance:.0f} mm")
                    reaction_obstacle()
                    # apres la sequence : on relance la marche avant
                    print(">> Reprise de la marche")
                    drive_full(VITESSE_MARCHE, 1, ramp_time=RAMPE)

            # --- 3. Pause ---
            time.sleep(PERIODE_BOUCLE)

    except KeyboardInterrupt:
        print("\nFin de programme par Ctrl-C")

    finally:
        # Securite : moteur coupe + feux eteints + buzzer arrete
        drive(0)
        feux_off()
        buzzer.stop()
        destroy()
        print("Nettoyage final realise")


if __name__ == "__main__":
    main()