import time

from drive import drive_full, drive, destroy
from tache5_ultrason import distance_mm, buzzer
from etalonnage_servo_direction import set_servo_angle
from task6_line_tracking import LineTrackingSensor
from task3_servo import ServoController


VITESSE_MARCHE = 20
VITESSE_EVITEMENT = 18
VITESSE_RECUL = 18

SEUIL_OBSTACLE = 500
SEUIL_PASSAGE_LIBRE = 650
DISTANCE_MAX_FAUSSE = 2000

ANGLE_DIRECTION_MAX = 45
ANGLE_CENTRE = 0

PERIODE_BOUCLE = 0.05

ANGLES_SCAN = list(range(-60, 61, 10))

DUREE_AVANCE_GAP = 0.9
DUREE_CONTRE_BRAQUAGE = 0.8
DUREE_RECENTRAGE = 0.4
DUREE_RECUL_BORDURE = 0.35

capteur_ligne = LineTrackingSensor()
servo = ServoController()

def stop_robot():
    drive(0)
    set_servo_angle(ANGLE_CENTRE)


def set_head_angle(angle):
    servo.set_servo_angle(1, angle, smooth=True)


def avancer_tout_droit():
    set_servo_angle(ANGLE_CENTRE)
    drive_full(VITESSE_MARCHE, 1, ramp_time=0.05)

def obstacle_detecte(distance):
    return distance is not None and distance < SEUIL_OBSTACLE
def bordure_detectee(pattern):
    return pattern != "000"
def eviter_bordure(pattern):
    print(f"[BORDURE] Détectée : {pattern}")

    stop_robot()
    time.sleep(0.1)

    drive_full(VITESSE_RECUL, -1, ramp_time=0.05)
    time.sleep(DUREE_RECUL_BORDURE)
    drive(0)

    if pattern in ("100", "110"):

        angle = ANGLE_DIRECTION_MAX
        print("[BORDURE] Bordure gauche -> correction droite")

    elif pattern in ("001", "011"):

        angle = -ANGLE_DIRECTION_MAX
        print("[BORDURE] Bordure droite -> correction gauche")

    else:
        angle = ANGLE_DIRECTION_MAX
        print("[BORDURE] Danger devant -> demi-correction droite")

    set_servo_angle(angle)
    drive_full(VITESSE_EVITEMENT, 1, ramp_time=0.05)
    time.sleep(0.45)

    stop_robot()
def scanner_environnement():
    mesures = []

    print(" Début du scan ultrason")

    for angle in ANGLES_SCAN:
        set_head_angle(angle)
        time.sleep(0.15)

        distance = distance_mm()

        if distance is None:
            distance = DISTANCE_MAX_FAUSSE

        libre = distance >= SEUIL_PASSAGE_LIBRE

        mesures.append({
            "angle": angle,
            "distance": distance,
            "libre": libre
        })

        print(
            f"[SCAN] angle={angle:>4}° | "
            f"distance={distance:>5.0f} mm | libre={libre}"
        )

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

    penalite_virage = abs(angle_centre) * 5

    score = largeur * 10 + distance_moyenne - penalite_virage
    return score
def choisir_meilleur_gap(gaps):
    if not gaps:
        return None

    meilleur_gap = max(gaps, key=score_gap)
    point_centre = meilleur_gap[len(meilleur_gap) // 2]

    angle_choisi = point_centre["angle"]

    print("[CHOIX] Passage choisi :")
    print(f"        début  = {meilleur_gap[0]['angle']}°")
    print(f"        fin    = {meilleur_gap[-1]['angle']}°")
    print(f"        centre = {angle_choisi}°")
    print(f"        score  = {score_gap(meilleur_gap):.1f}")

    return angle_choisi
def choisir_direction_par_radar():
    mesures = scanner_environnement()
    gaps = detecter_gaps(mesures)

    print(f"[SCAN] Nombre de passages libres : {len(gaps)}")

    angle = choisir_meilleur_gap(gaps)

    if angle is None:
        print("[SCAN] Aucun passage libre.")
        return None

    return angle
def convertir_scan_vers_direction(angle_scan):

    if angle_scan < 0:
        return -ANGLE_DIRECTION_MAX
    elif angle_scan > 0:
        return ANGLE_DIRECTION_MAX
    else:
        return 0
def avancer_surveille(duree, vitesse, angle_direction):
    debut = time.time()

    set_servo_angle(angle_direction)
    drive_full(vitesse, 1, ramp_time=0.05)

    while time.time() - debut < duree:
        pattern = capteur_ligne.read_pattern()

        if bordure_detectee(pattern):
            print("[SECURITE] Bordure pendant déplacement")
            stop_robot()
            eviter_bordure(pattern)
            return False

        time.sleep(PERIODE_BOUCLE)

    return True
def avancer_surveille(duree, vitesse, angle_direction):
    debut = time.time()

    set_servo_angle(angle_direction)
    drive_full(vitesse, 1, ramp_time=0.05)

    while time.time() - debut < duree:
        pattern = capteur_ligne.read_pattern()

        if bordure_detectee(pattern):
            print("[SECURITE] Bordure pendant déplacement")
            stop_robot()
            eviter_bordure(pattern)
            return False

        time.sleep(PERIODE_BOUCLE)

    return True
def reculer_surveille(duree):
    debut = time.time()

    set_servo_angle(0)
    drive_full(VITESSE_RECUL, -1, ramp_time=0.05)

    while time.time() - debut < duree:
        time.sleep(PERIODE_BOUCLE)

    stop_robot()
def contourner_obstacle_gap():
    print("\n[OBSTACLE] Détection obstacle")

    stop_robot()
    time.sleep(0.15)

    angle_scan = choisir_direction_par_radar()

    if angle_scan is None:
        print("[ACTION] Aucun passage clair -> recul")
        reculer_surveille(0.5)
        return

    angle_direction = convertir_scan_vers_direction(angle_scan)

    print(f"[ACTION] Angle scan choisi : {angle_scan}°")
    print(f"[ACTION] Angle roues appliqué : {angle_direction}°")

    ok = avancer_surveille(DUREE_AVANCE_GAP, VITESSE_EVITEMENT, angle_direction)
    if not ok:
        return

    ok = avancer_surveille(DUREE_CONTRE_BRAQUAGE, VITESSE_EVITEMENT, -angle_direction)
    if not ok:
        return

    ok = avancer_surveille(DUREE_RECENTRAGE, VITESSE_MARCHE, 0)
    if not ok:
        return

    print("[OBSTACLE] Contournement terminé")
def main():
    print("============================================")
    print("MISSION OBSTACLES - GAP FOLLOWING")
    print("Ctrl+C pour arrêter")
    print("============================================")

    try:
        set_head_angle(0)
        set_servo_angle(0)

        while True:
            distance = distance_mm()
            pattern = capteur_ligne.read_pattern()

            if distance is not None:
                print(f"[INFO] distance={distance:.0f} mm | pattern={pattern}")

            if bordure_detectee(pattern):
                eviter_bordure(pattern)

            elif obstacle_detecte(distance):
                contourner_obstacle_gap()

            else:
                avancer_tout_droit()

            time.sleep(PERIODE_BOUCLE)

    except KeyboardInterrupt:
        print("\n[FIN] Arrêt utilisateur")

    finally:
        stop_robot()
        set_head_angle(0)
        buzzer.stop()
        servo.deinit()
        destroy()
        print("[INFO] Système sécurisé")

if __name__ == "__main__":
    main()