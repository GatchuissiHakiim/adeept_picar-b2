#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import threading

from drive import drive_full, drive, destroy
from tache5_ultrason import distance_mm, buzzer
from etalonnage_servo_direction import set_servo_angle
from task6_line_tracking import LineTrackingSensor
from task3_servo import ServoController


# ============================================================
# CONFIGURATION
# ============================================================

VITESSE_MARCHE = 25
VITESSE_EVITEMENT = 25
VITESSE_RECUL = 14

SEUIL_OBSTACLE = 400
SEUIL_COLLISION = 180
SEUIL_PASSAGE_LIBRE = 400
DISTANCE_MAX_FAUSSE = 2000

ANGLE_DIRECTION_MAX = 65

PERIODE_ULTRASON = 0.08
PERIODE_IR = 0.03
PERIODE_DECISION = 0.05

ANGLES_SCAN = list(range(-60, 61, 10))

DUREE_RECUL_URGENCE = 0.8
DUREE_RECUL_BORDURE = 0.5

DUREE_PAS_EVITEMENT = 1.5
MAX_PAS_EVITEMENT = 10

DUREE_RECENTRAGE = 2.25




# ============================================================
# INITIALISATION
# ============================================================

capteur_ligne = LineTrackingSensor()
servo = ServoController()
dernier_angle_direction = 0

etat_lock = threading.Lock()

etat = {
    "distance": None,
    "pattern": "000",
    "running": True,
}


# ============================================================
# THREADS CAPTEURS
# ============================================================

def thread_ultrason():
    while True:
        with etat_lock:
            running = etat["running"]

        if not running:
            break

        d = distance_mm()

        with etat_lock:
            etat["distance"] = d

        time.sleep(PERIODE_ULTRASON)


def thread_ir():
    while True:
        with etat_lock:
            running = etat["running"]

        if not running:
            break

        pattern = capteur_ligne.read_pattern()

        with etat_lock:
            etat["pattern"] = pattern

        time.sleep(PERIODE_IR)


def lire_etat():
    with etat_lock:
        return etat["distance"], etat["pattern"]


def arreter_threads():
    with etat_lock:
        etat["running"] = False


# ============================================================
# FONCTIONS DE BASE
# ============================================================

def stop_robot():
    drive(0)
    set_servo_angle(0)


def set_head_angle(angle):
    servo.set_servo_angle(1, angle, smooth=True)


def avancer_tout_droit():
    set_head_angle(0)
    set_servo_angle(0)
    drive_full(VITESSE_MARCHE, 1, ramp_time=0.05)


def obstacle_detecte(distance):
    return distance is not None and distance < SEUIL_OBSTACLE


def collision_imminente(distance):
    return distance is not None and distance < SEUIL_COLLISION


def bordure_detectee(pattern):
    return pattern != "000"


# ============================================================
# SECURITES
# ============================================================

def recul_urgence():
    print("[URGENCE] Obstacle trop proche -> recul")

    stop_robot()
    time.sleep(0.1)

    set_head_angle(0)
    set_servo_angle(0)

    drive_full(VITESSE_RECUL, -1, ramp_time=0.05)
    time.sleep(DUREE_RECUL_URGENCE)

    stop_robot()
    time.sleep(0.2)
    
    

def dernier_angle_recentrer():
    global dernier_angle_direction

    if dernier_angle_direction > 0:
        return -ANGLE_DIRECTION_MAX

    elif dernier_angle_direction < 0:
        return ANGLE_DIRECTION_MAX

    else:
        return ANGLE_DIRECTION_MAX
  


def tourner_roues(angle):
    global dernier_angle_direction

    set_servo_angle(angle)

    if angle != 0:
        dernier_angle_direction = angle
        
def eviter_bordure(pattern):
    print(f"[BORDURE] Detectee : {pattern}")

    stop_robot()
    time.sleep(0.1)

    set_head_angle(0)
    set_servo_angle(0)

    drive_full(VITESSE_RECUL, -1, ramp_time=0.05)
    time.sleep(DUREE_RECUL_BORDURE)
    stop_robot()
    time.sleep(0.4)

    if pattern in ("100", "110"):
        angle = -ANGLE_DIRECTION_MAX
        print("[BORDURE] gauche -> correction droite")

    elif pattern in ("001", "011"):
        angle = ANGLE_DIRECTION_MAX
        print("[BORDURE] droite -> correction gauche")

    else:
        angle = dernier_angle_recentrer()
        print("[BORDURE] devant/ambigu -> correction droite")
        tourner_roues(-angle)
        drive_full(25, -1, ramp_time=0.05)
        time.sleep(1.5)
        tourner_roues(angle)
        drive_full(VITESSE_EVITEMENT, 1, ramp_time=0)
        time.sleep(1.25)
        return
        

    tourner_roues(angle)
    drive_full(VITESSE_EVITEMENT, 1, ramp_time=0)
    time.sleep(0.25)

    stop_robot()
    set_servo_angle(0)


# ============================================================
# SCAN RADAR
# ============================================================

def scanner_environnement():
    mesures = []

    print("[SCAN] Debut scan")

    stop_robot()
    time.sleep(0.1)

    for angle in ANGLES_SCAN:
        _, pattern = lire_etat()

        if bordure_detectee(pattern):
            print("[SCAN] Bordure detectee pendant scan")
            break

        set_head_angle(angle)
        time.sleep(0.15)

        d = distance_mm()

        if d is None:
            d = DISTANCE_MAX_FAUSSE

        libre = d >= SEUIL_PASSAGE_LIBRE

        mesures.append({
            "angle": angle,
            "distance": d,
            "libre": libre
        })

        print(f"[SCAN] angle={angle:>4} | distance={d:>5.0f} | libre={libre}")

    set_head_angle(0)
    time.sleep(0.1)

    return mesures


def detecter_gaps(mesures):
    gaps = []
    gap_actuel = []

    for point in mesures:
        if point["libre"]:
            gap_actuel.append(point)
        else:
            if gap_actuel:
                gaps.append(gap_actuel)
                gap_actuel = []

    if gap_actuel:
        gaps.append(gap_actuel)

    return gaps


def score_gap(gap):
    largeur = abs(gap[-1]["angle"] - gap[0]["angle"]) + 10
    distance_moyenne = sum(p["distance"] for p in gap) / len(gap)
    angle_centre = gap[len(gap) // 2]["angle"]

    # Favorise largeur + distance, mais pénalise fort les bords
    penalite_angle = abs(angle_centre) * 20
    penalite_extreme = 800 if abs(angle_centre) >= 50 else 0

    return largeur * 20 + distance_moyenne - penalite_angle - penalite_extreme

def choisir_meilleur_gap(gaps):
    if not gaps:
        return None

    # Priorité : passage entre obstacles, donc pas trop excentré
    candidats_centraux = []

    for gap in gaps:
        angle_centre = gap[len(gap) // 2]["angle"]
        largeur = abs(gap[-1]["angle"] - gap[0]["angle"]) + 10

        if abs(angle_centre) <= 30 and largeur >= 20:
            candidats_centraux.append(gap)

    if candidats_centraux:
        meilleur_gap = max(candidats_centraux, key=score_gap)
        print("[CHOIX] Mode central : passage entre obstacles")
    else:
        # Si aucun passage central, seulement là on accepte un côté
        meilleur_gap = max(gaps, key=score_gap)
        print("[CHOIX] Mode secours : passage lateral")

    point_centre = meilleur_gap[len(meilleur_gap) // 2]
    angle_choisi = point_centre["angle"]

    print("[CHOIX] Passage choisi :")
    print(f"        debut  = {meilleur_gap[0]['angle']}")
    print(f"        fin    = {meilleur_gap[-1]['angle']}")
    print(f"        centre = {angle_choisi}")
    print(f"        score  = {score_gap(meilleur_gap):.1f}")

    return angle_choisi

def choisir_direction_par_radar():
    mesures = scanner_environnement()

    if not mesures:
        print("[SCAN] Aucune mesure exploitable")
        return None

    gaps = detecter_gaps(mesures)

    if not gaps:
        print("[SCAN] Aucun passage libre")
        return None

    return choisir_meilleur_gap(gaps)


def convertir_scan_vers_direction(angle_scan):
    if angle_scan < 0:
        return -ANGLE_DIRECTION_MAX
    elif angle_scan > 0:
        return ANGLE_DIRECTION_MAX
    return 0


# ============================================================
# MOUVEMENTS SURVEILLES
# ============================================================

def avancer_surveille(duree, vitesse, angle_direction):
    debut = time.time()

    set_servo_angle(angle_direction)
    drive_full(vitesse, 1, ramp_time=0.05)

    while time.time() - debut < duree:
        distance, pattern = lire_etat()

        if collision_imminente(distance):
            print("[SURVEILLANCE] Collision imminente")
            stop_robot()
            recul_urgence()
            return False

        if bordure_detectee(pattern):
            print("[SURVEILLANCE] Bordure pendant mouvement")
            stop_robot()
            eviter_bordure(pattern)
            return False

        time.sleep(PERIODE_DECISION)

    return True


def recentrer_sur_voie(angle_precedent, duree_max=1.5):
    print("[RECENTRAGE] Contre-braquage adaptatif")

    angle_recentrage = -angle_precedent
    debut = time.time()

    set_head_angle(0)
    set_servo_angle(angle_recentrage)
    drive_full(VITESSE_MARCHE, 1, ramp_time=0.05)

    while time.time() - debut < duree_max:
        distance, pattern = lire_etat()

        if collision_imminente(distance):
            recul_urgence()
            return False

        if bordure_detectee(pattern):
            eviter_bordure(pattern)
            return False

        # si l'avant est libre, on peut arrêter le contre-braquage
        if distance is None or distance > SEUIL_OBSTACLE:
            break

        time.sleep(PERIODE_DECISION)

    stop_robot()
    set_servo_angle(0)
    set_head_angle(0)
    time.sleep(0.5)

    return True


# ============================================================
# CONTOURNEMENT MULTI-OBSTACLES
# ============================================================

def contourner_obstacle_gap():
    print("[OBSTACLE] Contournement dynamique")
    dernier_angle_direction = 0
    
    

    stop_robot()
    time.sleep(0.1)

    for i in range(MAX_PAS_EVITEMENT):
        distance, pattern = lire_etat()

        if collision_imminente(distance):
            recul_urgence()
            continue

        if bordure_detectee(pattern):
            eviter_bordure(pattern)
            continue

        if not obstacle_detecte(distance):
          print("[OBSTACLE] Plus d'obstacle devant -> recentrage obligatoire")
      
          ok = avancer_surveille(1.5, VITESSE_EVITEMENT, -dernier_angle_direction)
          if not ok:
              continue
      
          ok = avancer_surveille(0.50, VITESSE_MARCHE, 0)
          if not ok:
              continue
      
          print("[OBSTACLE] Recentrage termine")
          return

        angle_scan = choisir_direction_par_radar()

        if angle_scan is None:
            print("[ACTION] Aucun gap -> recul")
            recul_urgence()
            continue

        angle_direction = convertir_scan_vers_direction(angle_scan)
        dernier_angle_direction = angle_direction

        print(f"[ACTION] pas {i + 1}/{MAX_PAS_EVITEMENT}")
        print(f"         angle scan  = {angle_scan}")
        print(f"         angle roues = {angle_direction}")

        ok = avancer_surveille(
            DUREE_PAS_EVITEMENT,
            VITESSE_EVITEMENT,
            angle_direction
        )

        if not ok:
            continue

    print("[SECURITE] Trop de tentatives -> recul long")
    recul_urgence()
    recentrer_sur_voie(angle_direction)
    



# ============================================================
# MAIN
# ============================================================

def main():
    print("============================================")
    print("MISSION OBSTACLE - VERSION THREADS")
    print("Ctrl+C pour arreter")
    print("============================================")

    t_ultrason = threading.Thread(target=thread_ultrason, daemon=True)
    t_ir = threading.Thread(target=thread_ir, daemon=True)
    angle = dernier_angle_recentrer()
    

    try:
        set_head_angle(0)
        set_servo_angle(angle)
        stop_robot()

        t_ultrason.start()
        t_ir.start()

        time.sleep(0.5)

        while True:
            distance, pattern = lire_etat()

            if distance is not None:
                print(f"[INFO] distance={distance:.0f} mm | pattern={pattern}")
            else:
                print(f"[INFO] distance=None | pattern={pattern}")

            if collision_imminente(distance):
                  recul_urgence()

            elif bordure_detectee(pattern):
                  eviter_bordure(pattern)

            elif obstacle_detecte(distance):
                  contourner_obstacle_gap()

            else:
                avancer_tout_droit()

            time.sleep(PERIODE_DECISION)

    except KeyboardInterrupt:
        print("\n[FIN] Arret utilisateur")

    finally:
        print("[SECURITE] Arret complet")

        arreter_threads()
        time.sleep(0.2)

        stop_robot()
        set_head_angle(0)
        buzzer.stop()
        servo.deinit()
        destroy()

        print("[INFO] Systeme securise")


if __name__ == "__main__":
    main()
