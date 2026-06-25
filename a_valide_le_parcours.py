#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
#  CTP2 Mastercamp - Systèmes Embarqués
#  Code Phase 1 Final - Version Unifiée Intégrale (Élan & Couple Maximisés)
# ==============================================================================

import sys
import select
import time
from gpiozero import LED

# --- Modules matériels PiCar-B ---
from drive import drive_full, drive, destroy
from tache5_ultrason import distance_mm, buzzer
from LEDWS2812_Controller import piloter_led, led
import control_leds
from etalonnage_servo_direction import set_servo_angle
from task6_line_tracking import LineTrackingSensor

# ------------------------------------------------------------------------------
#  CONSTANTES DE CONFIGURATION (Valeurs physiques idéales)
# ------------------------------------------------------------------------------
VITESSE_MARCHE      = 28      # Puissance constante (36%) pour un élan optimal
VITESSE_RECUL       = 28      # Vitesse de marche arrière pour la sécurité (%)
PERIODE_BOUCLE      = 0.04    # Échantillonnage stable à 25 Hz (40 ms)

# Paramètres de direction (Rappel châssis : positif = Gauche / négatif = Droite)
ANGLE_DOUX          = 8       # Micro-ajustement pour la ligne droite
ANGLE_FORT          = 50      # Braquage idéal pour enrouler le S sans caler

# Gestion du blanc (Filtre anti-pointillés)
SEUIL_TEMPS_POINTILLES = 0.95 # 600 ms d'immunité pour franchir le blanc des pointillés
TIMEOUT_RECUPERATION   = 2.5  # Sécurité maximale de la marche arrière

# Gestion des obstacles (bouteilles)
SEUIL_OBSTACLE      = 220     # Distance de détection (mm)
PAUSE_FEUX          = 1.0     
DUREE_RECUL_OBSTACLE= 1.3     
PAUSE_APRES_OBSTACLE= 1.5     

# Configuration Phares (GPIO)
phare_gauche = LED(control_leds.PIN_LEFT_R,  active_high=False)
phare_droite = LED(control_leds.PIN_RIGHT_R, active_high=False)

# Initialisation du capteur de ligne
capteur_ligne = LineTrackingSensor()


# ------------------------------------------------------------------------------
#  SIGNALISATION VISUELLE
# ------------------------------------------------------------------------------
def set_feux_detresse(state: bool):
    if state:
        phare_gauche.on()
        phare_droite.on()
        for i in range(14):
            piloter_led(i, 'R')
    else:
        phare_gauche.off()
        phare_droite.off()
        led.set_all_led_color(0, 0, 0)

def clignoter_feux_bloquant(duree_totale: float, periode: float = 0.2):
    fin = time.time() + duree_totale
    etat = True
    while time.time() < fin:
        set_feux_detresse(etat)
        etat = not etat
        time.sleep(periode)
    set_feux_detresse(False)


# ------------------------------------------------------------------------------
#  MANŒUVRE DE REPOSITIONNEMENT AUTONOME
# ------------------------------------------------------------------------------
def executer_manoeuvre_repositionnement():
    """Recule en ligne droite et réaligne parfaitement le cap dès que la ligne est interceptée."""
    global dernier_angle
    print("\n[AUTONOMIE] Ligne perdue hors-pointillés. Repositionnement...")
    drive(0)
    set_servo_angle(0) 
    time.sleep(0.15)
    
    set_feux_detresse(True)
    drive_full(VITESSE_RECUL, -1, ramp_time=0.05)
    
    timeout = time.time() + TIMEOUT_RECUPERATION
    ligne_trouvee = False
    pattern_recup = "000"
    
    while time.time() < timeout:
        pattern_recup = capteur_ligne.read_pattern()
        if pattern_recup != "000":
            print(f"[AUTONOMIE] Ligne interceptée avec le motif : {pattern_recup}")
            ligne_trouvee = True
            break
        time.sleep(0.01)
        
    drive(0)
    set_feux_detresse(False)
    time.sleep(0.1) # Courte pause pour stabiliser le châssis avant de repartir
    
    if ligne_trouvee:
        # REPOSITIONNEMENT PARFAIT : On oriente les roues du bon côté selon le capteur qui a vu le noir
        if pattern_recup in ("100", "110"):
            dernier_angle = ANGLE_DOUX      # La ligne est à gauche, on braque à gauche
        elif pattern_recup in ("001", "011"):
            dernier_angle = -ANGLE_DOUX     # La ligne est à droite, on braque à droite
        else:
            dernier_angle = 0               # On est pile au centre
            
        set_servo_angle(dernier_angle)      # On applique l'angle de correction immédiatement
        drive_full(VITESSE_MARCHE, 1, ramp_time=0.1)
        return True
    else:
        print("[SÉCURITÉ] Échec du repositionnement. Arrêt permanent.")
        return False


# ------------------------------------------------------------------------------
#  SÉCURITÉ OBSTACLE (BOUTEILLES)
# ------------------------------------------------------------------------------
def gerer_obstacle():
    drive(0)
    set_servo_angle(0)
    print("\n[OBSTACLE] Bouteille détectée ! Phase de sécurisation...")
    clignoter_feux_bloquant(PAUSE_FEUX, 0.15)
    
    print("[ACTION] Recul de dégagement")
    set_feux_detresse(True)
    drive_full(VITESSE_RECUL, -1, ramp_time=0.1)
    
    fin_recul = time.time() + DUREE_RECUL_OBSTACLE
    while time.time() < fin_recul:
        buzzer.play("C5")
        time.sleep(0.1)
        buzzer.stop()
        time.sleep(0.1)
        
    drive(0)
    print("[INFO] Voie libérée, poursuite du circuit...")
    clignoter_feux_bloquant(PAUSE_APRES_OBSTACLE, 0.25)


# ------------------------------------------------------------------------------
#  INTERFACE CLAVIER NON BLOQUANTE
# ------------------------------------------------------------------------------
def verifier_clavier():
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:
        return sys.stdin.readline().strip().upper()
    return None


# ------------------------------------------------------------------------------
#  BOUCLE PRINCIPALE EXÉCUTIVE
# ------------------------------------------------------------------------------
def main():
    print("==================================================================")
    print(" PI CAR-B : CONFIGURATION PHASE 1 HOMOLOGUÉE                     ")
    print(" Commandes : 'M' = Démarrer | 'A' = Arrêter | 'Ctrl+C' = Quitter ")
    print("==================================================================")

    set_feux_detresse(False)
    set_servo_angle(0)
    
    en_marche = False
    dernier_angle = 0   
    t_perte_ligne = None

    try:
        while True:
            # 1. Gestion des ordres utilisateurs
            commande = verifier_clavier()
            if commande:
                if commande == 'M':
                    en_marche = True
                    print(">> STATUT : PILOTAGE AUTOMATIQUE ACTIF")
                    drive_full(VITESSE_MARCHE, 1, ramp_time=0.1)
                elif commande == 'A':
                    en_marche = False
                    print(">> STATUT : ARRÊT VOLONTAIRE")
                    drive(0)
                    set_servo_angle(0)

            # 2. Traitement du suivi de ligne autonome
            if en_marche:
                # Vérification prioritaire du capteur à ultrasons
                distance = distance_mm()
                if distance is not None and distance < SEUIL_OBSTACLE:
                    gerer_obstacle()
                    drive_full(VITESSE_MARCHE, 1, ramp_time=0.1)
                    t_perte_ligne = None
                    continue

                # Lecture instantanée des cellules infrarouges
                pattern = capteur_ligne.read_pattern()

                if pattern == "010":  # Parfaitement centré
                    dernier_angle = 0
                    set_servo_angle(dernier_angle)
                    t_perte_ligne = None

                # ---- Courbures à Gauche (Angles Positifs) ----
                elif pattern == "110":  # Déviation légère
                    dernier_angle = ANGLE_DOUX
                    set_servo_angle(dernier_angle)
                    t_perte_ligne = None

                elif pattern == "100":  # Virage prononcé
                    dernier_angle = ANGLE_FORT
                    set_servo_angle(dernier_angle)
                    t_perte_ligne = None

                # ---- Courbures à Droite (Angles Négatifs) ----
                elif pattern == "011":  # Déviation légère
                    dernier_angle = -ANGLE_DOUX
                    set_servo_angle(dernier_angle)
                    t_perte_ligne = None

                elif pattern == "001":  # Virage prononcé
                    dernier_angle = -ANGLE_FORT
                    set_servo_angle(dernier_angle)
                    t_perte_ligne = None

                # ---- GESTION DES INTERSECTIONS / FOURCHES ----
                elif pattern in ("111", "101"):  
                    # Contournement automatique par la branche de droite
                    dernier_angle = -ANGLE_FORT
                    set_servo_angle(dernier_angle)
                    t_perte_ligne = None

                # ---- Gestion des Trous (Pointillés) et Sorties ("000") ----
                elif pattern == "000":
                    # Maintien du cap précédent pour survoler les pointillés sur l'élan rectiligne
                    set_servo_angle(dernier_angle)
                    
                    if t_perte_ligne is None:
                        t_perte_ligne = time.time()
                    else:
                        # Déclenchement de la sécurité uniquement si le blanc dure trop longtemps
                        if (time.time() - t_perte_ligne) > SEUIL_TEMPS_POINTILLES:
                            succes = executer_manoeuvre_repositionnement()
                            t_perte_ligne = None # CRITIQUE : Réinitialisation du temps pour casser la boucle de marches arrière
                            if not succes:
                                en_marche = False

            # 3. Cadencement de la boucle
            time.sleep(PERIODE_BOUCLE)

    except KeyboardInterrupt:
        print("\n[FIN] Interruption utilisateur.")

    finally:
        # Extinction propre de tous les actionneurs en cas de coupure
        drive(0)
        set_servo_angle(0)
        set_feux_detresse(False)
        buzzer.stop()
        destroy()
        print("[INFO] Fin de session. Système sécurisé.")


if __name__ == "__main__":
    main()