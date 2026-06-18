#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
VITESSE_NORMALE = 40     # % du max : ligne droite
VITESSE_RECUL   = 15     # % du max : recul (obstacle / manoeuvre)
RAMPE           = 1.0    # rampe d'acceleration au demarrage (s)
PERIODE_BOUCLE  = 0.01   # pause entre deux tours de boucle (s)

SEUIL_OBSTACLE = 200     # mm (20 cm) : distance d'arret, PARAMETRABLE (consigne)

PAUSE_AVANT_RECUL = 1.0  # 1 s entre l'arret et le recul (obstacle)
DUREE_RECUL       = 1.5  # s de recul obstacle -> A CALIBRER (~30 cm)
PAUSE_APRES       = 2.0  # 2 s d'arret avant reprise (obstacle)

ANGLE_VIRAGE    = 40     # degres de braquage (a ajuster)
DUREE_MANOEUVRE = 0.6    # s de recul en contre-braquage -> A CALIBRER

SEUIL_PERDU = 1          # nb de lectures consecutives "ligne perdue" avant manoeuvre

# Phares avant rouges (canaux R), logique inverse -> active_high=False
phare_gauche = LED(control_leds.PIN_LEFT_R,  active_high=False)   # GPIO0
phare_droite = LED(control_leds.PIN_RIGHT_R, active_high=False)   # GPIO1

# Capteur de ligne (3 capteurs IR : gauche / milieu / droite)
capteur_ligne = LineTrackingSensor()

# Etat du suivi
dernier_cote     = 0     # -1 = ligne a gauche, +1 = a droite, 0 = inconnu
vitesse_actuelle = 0     # vitesse moteur courante (relance seulement si ca change)
compteur_perdu   = 0     # nb de lectures consecutives "ligne perdue"


# -------------------------------------------------------------
#  Direction : sens de braquage centralise
# -------------------------------------------------------------
def braquer_gauche():
    set_servo_angle(ANGLE_VIRAGE)

def braquer_droite():
    set_servo_angle(-ANGLE_VIRAGE)

def roues_droites():
    set_servo_angle(0)


# -------------------------------------------------------------
#  Vitesse : ne relance le moteur que si la vitesse CHANGE
# -------------------------------------------------------------
def rouler(vitesse):
    global vitesse_actuelle
    if vitesse != vitesse_actuelle:
        drive_full(vitesse, 1, ramp_time=1.0)
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
#  Manoeuvre de virage serre (ligne perdue)
# -------------------------------------------------------------
def manoeuvre_virage():
    global vitesse_actuelle
    DUREE_MAX_RECUL = 3.0    # securite : recul max si ligne pas retrouvee (s)
    print(">> Ligne perdue : manoeuvre de repositionnement")

    # 1. Arret complet
    drive(0)
    vitesse_actuelle = 0
    time.sleep(0.3)

    # 2. Choix de l'angle de contre-braquage
    if dernier_cote == +1:
        angle = +ANGLE_VIRAGE       # ligne perdue a droite -> braquer gauche
    elif dernier_cote == -1:
        angle = -ANGLE_VIRAGE      # ligne perdue a gauche -> braquer droite
    else:
        angle = ANGLE_VIRAGE       # par defaut

    # 3. Recul avec maintien actif du braquage
    set_servo_angle(angle)
    time.sleep(0.4)                # laisse le servo tourner
    drive_full(VITESSE_RECUL, -1, ramp_time=0.2)
    
    debut = time.time()
    while True:
      set_servo_angle(angle)
      pattern = capteur_ligne.read_pattern()
      print(f"  recul... pattern = {pattern}")
    
      if pattern != "000":
        print(">> Ligne retrouvee !")
        time.sleep(0.3)
        break
        
      if time.time() - debut > DUREE_MAX_RECUL:
        print(">> Securite : duree max atteinte")
        break
        
      time.sleep(0.05)

    # 4. Arret
    drive(0)
    vitesse_actuelle = 0
    time.sleep(0.2)
    
    if dernier_cote == +1:           # ligne perdue a droite -> repart a droite
        set_servo_angle(+ANGLE_VIRAGE)
    elif dernier_cote == -1:         # ligne perdue a gauche -> repart a gauche
        set_servo_angle(-ANGLE_VIRAGE)
    else:
        set_servo_angle(0)

    time.sleep(0.3)  

    # 5. Reprise progressive : avance lente pour gerer la courbe
    compteur_perdu = 0
    drive_full(25, 1, ramp_time=0.5)
    vitesse_actuelle = 25

# -------------------------------------------------------------
#  Suivi de ligne (coeur de la tache)
#  Le compteur_perdu sert d'anti-rebond : il faut SEUIL_PERDU
#  lectures consecutives de "ligne perdue" pour declencher la
#  manoeuvre. Sinon le robot suit normalement.
# -------------------------------------------------------------
def suivre_ligne():
    global dernier_cote, compteur_perdu
    pattern = capteur_ligne.read_pattern()
    print(f"pattern = {pattern}")

    if pattern == "111":                        # ligne droite
        compteur_perdu = 0
        roues_droites()
        rouler(VITESSE_NORMALE)

    elif pattern == "001":                      # leger decalage a gauche
        compteur_perdu = 0
        braquer_droite()
        rouler(VITESSE_NORMALE // 2)
        dernier_cote = -1

    elif pattern == "100":                      # leger decalage a droite
        compteur_perdu = 0
        braquer_gauche()
        rouler(VITESSE_NORMALE // 2)
        dernier_cote = +1

    elif pattern == "011":                      # virage serre a gauche
        compteur_perdu = 0
        braquer_droite()
        rouler(VITESSE_NORMALE // 3)
        dernier_cote = -1

    elif pattern == "110":                      # virage serre a droite
        compteur_perdu = 0
        braquer_gauche()
        rouler(VITESSE_NORMALE // 3)
        dernier_cote = +1

    elif pattern == "010":                      # centre seul -> tout droit
        compteur_perdu = 0
        roues_droites()
        rouler(VITESSE_NORMALE)

    elif pattern == "000":                      # ligne perdue ?
        compteur_perdu += 1
        if compteur_perdu >= SEUIL_PERDU:
            compteur_perdu = 0
            manoeuvre_virage()
        # sinon : on continue tout droit, on attend de confirmer


# -------------------------------------------------------------
#  Programme principal
# -------------------------------------------------------------
def main():
    global vitesse_actuelle, compteur_perdu
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
                    compteur_perdu = 0
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
                    compteur_perdu = 0
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
