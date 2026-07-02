#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP2 Mastercamp - Mission B - V11 validation pré-test
#  Suivi de ligne ROUGE par CAMERA + arrêt sur carré BLEU
#
#  Cette version repart de la famille V6/V8, pas de la V9.
#
#  Pourquoi ?
#  - V9 était trop nerveuse : dérivée temps réel + gains adaptatifs + slew élevé
#    => oscillations, saturation servo, effondrement au dernier virage.
#  - V11 garde une mesure stable proche/lointaine et corrige un défaut de V10 :
#    le départ ne se fait plus toujours à VITESSE_MAX ; il est déjà plafonné
#    selon l'erreur détectée au pré-alignement.
#
#  Principe :
#  - VITESSE_MAX peut être montée à 32, 36, 40.
#  - En ligne droite, le robot va vers VITESSE_MAX.
#  - En virage serré, la vitesse est automatiquement plafonnée.
#  - Le carré bleu ne ralentit plus le robot : il sert seulement à l'arrêt final.
#
#  Commandes : M = marche / A = arrêt / Q = quitter / Ctrl+C = quitter
# =============================================================

import sys
import select
import time
import termios
import tty

import cv2
import numpy as np
from picamera2 import Picamera2

from task3_servo import ServoController
from drive import drive_full, drive, destroy

# -------------------------------------------------------------
#  Camera / détection rouge
# -------------------------------------------------------------
LARGEUR = 320
HAUTEUR = 240

# D'après tes logs : BGR est le mode qui détecte réellement la ligne rouge.
MODE_COULEUR = "BGR"    # "BGR", "RGB", ou "AUTO"

ROUGE_BAS_1 = np.array([0,   75,  45])
ROUGE_HAUT_1 = np.array([16, 255, 255])
ROUGE_BAS_2 = np.array([164, 75,  45])
ROUGE_HAUT_2 = np.array([180, 255, 255])

# Mesure proche : où est la ligne sous le châssis.
# Mesure loin : où part la ligne devant.
BANDE_PROCHE = (0.73, 0.98)
BANDE_LOIN = (0.50, 0.74)

MIN_PIXELS_BANDE = 35
MIN_AIRE_CONTOUR = 20
MIN_PIXELS_ROW = 2
MIN_ROWS_VALIDES = 2

# Calibration caméra.
# Si le robot roule constamment à droite de la ligne rouge : -3 puis -5.
# Si le robot roule constamment à gauche de la ligne rouge : +3 puis +5.
OFFSET_CAMERA_PCT = 0.0

# Protection de la mesure loin.
MIN_PIXELS_LOIN_FIABLE = 300
FAR_EXTREME_PCT = 72
MIN_PIXELS_LOIN_EXTREME = 900

# -------------------------------------------------------------
#  Détection du carré bleu d'arrêt
# -------------------------------------------------------------
BLEU_BAS = np.array([95,  60,  35])
BLEU_HAUT = np.array([140, 255, 255])

ROI_BLEU = (0.35, 0.98)

# Le bleu ne doit pas ralentir le suivi ; il ne sert qu'à l'arrêt final.
# Condition historique conservée : gros carré bleu, centre très bas dans l'image.
MIN_AIRE_BLEU_ARRET = 1700
Y_BLEU_ARRET = 0.84
BLEU_FRAMES_ARRET = 3

# V12 : condition complémentaire de fin de parcours.
# Le suivi rouge reste inchangé ; le problème d'arrêt vient du fait que la
# validation précédente dépendait uniquement du centre du contour bleu. Or, avec
# une caméra basse, le carré peut être déjà au contact du robot lorsque son centre
# n'a pas encore atteint Y_BLEU_ARRET. On ajoute donc une validation par bord bas.
MIN_AIRE_BLEU_APPROCHE_ARRET = 650
Y_BLEU_CENTRE_MIN_ARRET = 0.70
Y_BLEU_BAS_ARRET = 0.90
BLEU_CENTRAGE_APPROCHE_PCT = 55
RATIO_BLEU_ARRET_MIN = 0.45
RATIO_BLEU_ARRET_MAX = 2.20
REMPLISSAGE_BLEU_APPROCHE_MIN = 0.30
BLEU_FRAMES_APPROCHE_ARRET = 2
TEMPS_MIN_BLEU_APRES_DEPART = 0.80

# -------------------------------------------------------------
#  Servos
# -------------------------------------------------------------
CANAL_TETE = 1
CANAL_ROUES = 0

ANGLE_TETE_FIXE = 0.0
SENS_ROUES = +1

# Le contrôleur matériel semble appliquer environ 40° max.
# On demande 38° pour éviter d'être constamment dans la saturation.
ANGLE_ROUES_MAX = 38.0

# Variation max des roues par boucle.
# Pas trop haut : sinon on obtient les oscillations V9.
SLEW_ROUES_BASE = 8.0
SLEW_ROUES_RAPIDE = 12.0

ZONE_MORTE_ROUES = 0.8

# -------------------------------------------------------------
#  Gains d'asservissement
# -------------------------------------------------------------
# Priorité au point proche, anticipation lointaine plus modérée.
KP_PROCHE = 0.86
KP_LOIN = 0.18
KD_PROCHE = 0.10       # dérivée discrète par boucle, PAS / seconde

# Filtrage : réactif mais pas hystérique.
ALPHA_PROCHE = 0.68
ALPHA_LOIN = 0.52

# Réduit l'influence de la bande loin lorsqu'elle contredit fortement la bande proche.
FAR_OPPOSE_REDUCTION = 0.22

# -------------------------------------------------------------
#  Moteur / régulateur de vitesse
# -------------------------------------------------------------
# Tu peux tester 32 puis 36 puis 40.
VITESSE_MAX = 32

# Ne pas descendre sous ce seuil : évite le "calage" / manque de couple.
VITESSE_MIN_COURBE = 24

# Si la ligne est brièvement perdue, on continue assez vite pour garder du couple.
VITESSE_RECHERCHE = 24

# Mise à jour de vitesse : pas trop fréquente pour ne pas perturber le driver.
PERIODE_UPDATE_MOTEUR = 0.28
DELTA_VITESSE_MIN = 3

TEMPS_RECHERCHE_AVANT_ARRET = 2.4

PERIODE_BOUCLE = 0.05
PERIODE_LOG = 0.15
PERIODE_LOG_ATTENTE = 1.0

# Pré-orientation au départ : réduit le zigzag initial.
PREALIGN_DEPART = True
TEMPS_PREALIGN = 0.12


class ClavierNonBloquant:
    """Lecture clavier robuste : appuyer sur M suffit, pas besoin d'Entrée."""

    def __init__(self):
        self.fd = None
        self.ancien_mode = None
        self.mode_cbreak = False

        if sys.stdin.isatty():
            self.fd = sys.stdin.fileno()
            self.ancien_mode = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            self.mode_cbreak = True

    def lire(self):
        derniere_touche = None

        while True:
            dr, _, _ = select.select([sys.stdin], [], [], 0)
            if not dr:
                break

            if self.mode_cbreak:
                c = sys.stdin.read(1)
            else:
                ligne = sys.stdin.readline()
                c = ligne[:1] if ligne else ""

            if not c:
                break

            c = c.upper()
            if c in ("\n", "\r", " "):
                continue

            if c in ("M", "A", "Q"):
                derniere_touche = c

        return derniere_touche

    def restaurer(self):
        if self.mode_cbreak and self.fd is not None and self.ancien_mode is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.ancien_mode)


def clamp(x, mini, maxi):
    return max(mini, min(maxi, x))


def approcher(valeur, cible, pas_max):
    if cible > valeur + pas_max:
        return valeur + pas_max
    if cible < valeur - pas_max:
        return valeur - pas_max
    return cible


def convertir_hsv(image, mode):
    if mode == "RGB":
        return cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    return cv2.cvtColor(image, cv2.COLOR_BGR2HSV)


def masque_rouge_mode(image, mode):
    hsv = convertir_hsv(image, mode)
    masque = (cv2.inRange(hsv, ROUGE_BAS_1, ROUGE_HAUT_1) |
              cv2.inRange(hsv, ROUGE_BAS_2, ROUGE_HAUT_2))

    noyau3 = np.ones((3, 3), np.uint8)
    noyau5 = np.ones((5, 5), np.uint8)
    masque = cv2.morphologyEx(masque, cv2.MORPH_OPEN, noyau3)
    masque = cv2.morphologyEx(masque, cv2.MORPH_CLOSE, noyau5)
    return masque


def score_masque(masque):
    h, w = masque.shape[:2]
    roi = masque[int(0.45 * h):int(0.98 * h), :]

    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    meilleur = 0.0

    for c in contours:
        aire = cv2.contourArea(c)
        if aire < MIN_AIRE_CONTOUR:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        petit = max(1, min(cw, ch))
        grand = max(cw, ch)
        elongation = grand / petit
        meilleur = max(meilleur, aire * min(elongation, 7.0))

    return meilleur


def choisir_masque(image):
    if MODE_COULEUR == "RGB":
        masque = masque_rouge_mode(image, "RGB")
        return masque, "RGB", score_masque(masque), 0.0

    if MODE_COULEUR == "BGR":
        masque = masque_rouge_mode(image, "BGR")
        return masque, "BGR", 0.0, score_masque(masque)

    masque_rgb = masque_rouge_mode(image, "RGB")
    masque_bgr = masque_rouge_mode(image, "BGR")
    score_rgb = score_masque(masque_rgb)
    score_bgr = score_masque(masque_bgr)

    if score_bgr >= score_rgb:
        return masque_bgr, "BGR", score_rgb, score_bgr
    return masque_rgb, "RGB", score_rgb, score_bgr


def mesure_scanline(bande, prendre_bas=True):
    h, w = bande.shape[:2]
    mesures = []

    for y in range(h):
        xs = np.where(bande[y, :] > 0)[0]
        if xs.size < MIN_PIXELS_ROW:
            continue

        largeur_segment = int(xs.max() - xs.min() + 1)
        if largeur_segment > int(0.80 * w):
            continue

        cx = float(xs.mean())
        poids = float(xs.size)
        mesures.append((y, cx, poids))

    if len(mesures) < MIN_ROWS_VALIDES:
        return 0.0, False, 0

    mesures.sort(key=lambda v: v[0], reverse=prendre_bas)
    selection = mesures[:min(12, len(mesures))]

    somme_poids = sum(p for _, _, p in selection)
    cx = sum(cx * p for _, cx, p in selection) / somme_poids
    nb_pixels = int(sum(p for _, _, p in mesures))

    centre = w / 2.0
    err = 100.0 * (cx - centre) / centre
    err -= OFFSET_CAMERA_PCT

    return err, True, nb_pixels


def mesure_contour(bande):
    h, w = bande.shape[:2]
    nb_pixels = cv2.countNonZero(bande)

    if nb_pixels < MIN_PIXELS_BANDE:
        return 0.0, False, nb_pixels

    contours, _ = cv2.findContours(bande, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    meilleur = None
    meilleur_score = -1.0

    for c in contours:
        aire = cv2.contourArea(c)
        if aire < MIN_AIRE_CONTOUR:
            continue

        x, y, cw, ch = cv2.boundingRect(c)
        petit = max(1, min(cw, ch))
        grand = max(cw, ch)
        elongation = grand / petit
        score = aire * min(elongation, 7.0)

        if score > meilleur_score:
            meilleur_score = score
            meilleur = c

    if meilleur is None:
        return 0.0, False, nb_pixels

    M = cv2.moments(meilleur)
    if M["m00"] == 0:
        return 0.0, False, nb_pixels

    cx = M["m10"] / M["m00"]
    centre = w / 2.0
    err = 100.0 * (cx - centre) / centre
    err -= OFFSET_CAMERA_PCT

    return err, True, nb_pixels


def mesurer_bande(masque, y_debut_pct, y_fin_pct, prendre_bas):
    h, w = masque.shape[:2]
    y0 = int(h * y_debut_pct)
    y1 = int(h * y_fin_pct)
    bande = masque[y0:y1, :]

    err, ok, pix = mesure_scanline(bande, prendre_bas=prendre_bas)
    if ok:
        return err, True, pix, "scan"

    err, ok, pix = mesure_contour(bande)
    if ok:
        return err, True, pix, "contour"

    return 0.0, False, pix, "none"


def detecter_ligne(image):
    masque, mode, score_rgb, score_bgr = choisir_masque(image)

    err_proche, ok_proche, pix_proche, src_proche = mesurer_bande(
        masque, BANDE_PROCHE[0], BANDE_PROCHE[1], prendre_bas=True
    )

    err_loin, ok_loin, pix_loin, src_loin = mesurer_bande(
        masque, BANDE_LOIN[0], BANDE_LOIN[1], prendre_bas=False
    )

    if ok_proche and not ok_loin:
        err_loin = err_proche
        ok_loin = True
        src_loin = "copy"
    elif ok_loin and not ok_proche:
        err_proche = err_loin
        ok_proche = True
        src_proche = "copy"

    return {
        "trouvee": ok_proche or ok_loin,
        "err_proche": err_proche,
        "err_loin": err_loin,
        "pix_proche": pix_proche,
        "pix_loin": pix_loin,
        "src_proche": src_proche,
        "src_loin": src_loin,
        "mode": mode,
        "score_rgb": score_rgb,
        "score_bgr": score_bgr,
    }


def corriger_far_si_suspect(det):
    far = det["err_loin"]
    near = det["err_proche"]
    facteur_far = 1.0
    raison = "far_ok"

    if det["src_loin"] == "copy":
        return near, 0.0, "far_copy"

    if det["pix_loin"] < MIN_PIXELS_LOIN_FIABLE:
        return near, 0.0, "far_pix_low"

    if abs(far) > FAR_EXTREME_PCT and det["pix_loin"] < MIN_PIXELS_LOIN_EXTREME:
        return near, 0.0, "far_extreme_lowpix"

    # Si proche et loin sont opposés alors que l'erreur proche est déjà forte,
    # on évite que l'anticipation lointaine annule la correction de centrage.
    if near * far < 0 and abs(near) > 13:
        facteur_far = FAR_OPPOSE_REDUCTION
        raison = "far_opposed_reduced"

    return far, facteur_far, raison


def detecter_carre_bleu(image, mode):
    h, w = image.shape[:2]
    hsv = convertir_hsv(image, mode)

    masque = cv2.inRange(hsv, BLEU_BAS, BLEU_HAUT)
    noyau3 = np.ones((3, 3), np.uint8)
    noyau5 = np.ones((5, 5), np.uint8)
    masque = cv2.morphologyEx(masque, cv2.MORPH_OPEN, noyau3)
    masque = cv2.morphologyEx(masque, cv2.MORPH_CLOSE, noyau5)

    y0 = int(h * ROI_BLEU[0])
    y1 = int(h * ROI_BLEU[1])
    roi = masque[y0:y1, :]

    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    meilleur_infos = {
        "trouve": False,
        "arret": False,
        "arret_approche": False,
        "arret_auto": False,
        "aire": 0.0,
        "cx_pct": 0.0,
        "y_pct": 0.0,
        "y_bas_pct": 0.0,
        "largeur": 0,
        "hauteur": 0,
        "ratio": 0.0,
        "remplissage": 0.0,
    }
    meilleur_score = -1.0

    for c in contours:
        aire = cv2.contourArea(c)
        if aire < 80:
            continue

        x, y, cw, ch = cv2.boundingRect(c)
        if cw < 5 or ch < 5:
            continue

        ratio = cw / max(1, ch)
        if ratio < 0.35 or ratio > 3.2:
            continue

        remplissage = aire / max(1.0, cw * ch)
        if remplissage < 0.25:
            continue

        score = aire * remplissage
        if score > meilleur_score:
            meilleur_score = score
            cx = x + cw / 2.0
            cy = y0 + y + ch / 2.0
            cx_pct = 100.0 * (cx - w / 2.0) / (w / 2.0)
            y_pct = cy / h
            y_bas_pct = (y0 + y + ch) / h

            arret_strict = (
                aire >= MIN_AIRE_BLEU_ARRET and
                y_pct >= Y_BLEU_ARRET and
                abs(cx_pct) < 80
            )

            # Arrêt de fin : on accepte un carré moins massif si son bord bas
            # arrive très bas dans l'image, ce qui est le signe pratique que
            # le robot est au niveau du marqueur. La contrainte de centrage et
            # de forme limite les faux positifs dus aux reflets bleus latéraux.
            arret_approche = (
                aire >= MIN_AIRE_BLEU_APPROCHE_ARRET and
                y_pct >= Y_BLEU_CENTRE_MIN_ARRET and
                y_bas_pct >= Y_BLEU_BAS_ARRET and
                abs(cx_pct) < BLEU_CENTRAGE_APPROCHE_PCT and
                RATIO_BLEU_ARRET_MIN <= ratio <= RATIO_BLEU_ARRET_MAX and
                remplissage >= REMPLISSAGE_BLEU_APPROCHE_MIN
            )

            meilleur_infos = {
                "trouve": True,
                "arret": arret_strict,
                "arret_approche": arret_approche,
                "arret_auto": arret_strict or arret_approche,
                "aire": float(aire),
                "cx_pct": cx_pct,
                "y_pct": y_pct,
                "y_bas_pct": y_bas_pct,
                "largeur": int(cw),
                "hauteur": int(ch),
                "ratio": float(ratio),
                "remplissage": float(remplissage),
            }

    return meilleur_infos


def calculer_commande(det, err_proche_filtre, err_loin_filtre, err_proche_precedent, facteur_far):
    err_proche_cmd = 0.0 if abs(err_proche_filtre) < ZONE_MORTE_ROUES else err_proche_filtre

    derivee = err_proche_filtre - err_proche_precedent

    cible = SENS_ROUES * (
        -KP_PROCHE * err_proche_cmd
        -KP_LOIN * facteur_far * err_loin_filtre
        -KD_PROCHE * derivee
    )

    return clamp(cible, -ANGLE_ROUES_MAX, ANGLE_ROUES_MAX), derivee


def calculer_vitesse(angle_roues, cible_roues, err_proche_filtre, err_loin_filtre, facteur_far):
    # Stress = difficulté courante.
    stress_angle = min(1.0, max(abs(angle_roues), abs(cible_roues)) / ANGLE_ROUES_MAX)
    stress_near = min(1.0, abs(err_proche_filtre) / 28.0)
    stress_far = min(1.0, abs(err_loin_filtre) * facteur_far / 45.0)

    stress = max(stress_angle, stress_near, stress_far)

    # Courbe non linéaire : garde de la vitesse dans les petites erreurs,
    # mais plafonne franchement quand ça devient sérieux.
    v = VITESSE_MIN_COURBE + (VITESSE_MAX - VITESSE_MIN_COURBE) * (1.0 - stress ** 1.35)
    return int(round(clamp(v, VITESSE_MIN_COURBE, VITESSE_MAX)))


def maj_vitesse(vitesse_cible, vitesse_actuelle, dernier_update_moteur):
    maintenant = time.time()

    if vitesse_actuelle == 0:
        drive_full(vitesse_cible, 1, ramp_time=0.1)
        return vitesse_cible, maintenant

    if (
        abs(vitesse_cible - vitesse_actuelle) >= DELTA_VITESSE_MIN and
        maintenant - dernier_update_moteur >= PERIODE_UPDATE_MOTEUR
    ):
        drive_full(vitesse_cible, 1, ramp_time=0.05)
        return vitesse_cible, maintenant

    return vitesse_actuelle, dernier_update_moteur


def prealigner_depart(picam, servo):
    """
    Braque les roues avant de lancer le moteur, si la ligne est visible.

    Différence importante avec V10 : on renvoie aussi facteur_far et une
    vitesse de départ calculée. Ainsi, si VITESSE_MAX vaut 36 ou 40 mais que
    le robot démarre déjà avec une grosse erreur, il ne part pas plein gaz.
    """
    image = picam.capture_array()
    det = detecter_ligne(image)
    if not det["trouvee"]:
        return 0.0, 0.0, 0.0, 0.0, VITESSE_RECHERCHE, det

    far_effectif, facteur_far, _ = corriger_far_si_suspect(det)
    err_proche_filtre = det["err_proche"]
    err_loin_filtre = far_effectif

    cible, _ = calculer_commande(
        det,
        err_proche_filtre,
        err_loin_filtre,
        err_proche_precedent=0.0,
        facteur_far=facteur_far,
    )
    angle = clamp(cible, -ANGLE_ROUES_MAX, ANGLE_ROUES_MAX)

    vitesse_depart = calculer_vitesse(
        angle_roues=angle,
        cible_roues=cible,
        err_proche_filtre=err_proche_filtre,
        err_loin_filtre=err_loin_filtre,
        facteur_far=facteur_far,
    )

    servo.set_servo_angle(CANAL_ROUES, angle)
    time.sleep(TEMPS_PREALIGN)

    return angle, err_proche_filtre, err_loin_filtre, facteur_far, vitesse_depart, det


def main():
    print("=== Mission B : V11 validation pré-test rouge + arrêt bleu ===")
    print("Commandes : M = marche / A = arrêt / Q = quitter / Ctrl+C = quitter")
    print("Initialisation...")

    clavier = ClavierNonBloquant()
    servo = None
    picam = None

    try:
        servo = ServoController()
        picam = Picamera2()
        config = picam.create_preview_configuration(
            main={"size": (LARGEUR, HAUTEUR), "format": "RGB888"}
        )
        picam.configure(config)
        picam.start()
        time.sleep(2)

        angle_roues = 0.0
        err_proche_filtre = 0.0
        err_loin_filtre = 0.0
        err_proche_precedent = 0.0

        en_marche = False
        en_recherche = False
        t_perte = None
        derniere_direction_connue = 0.0
        vitesse_actuelle = 0
        dernier_update_moteur = 0.0
        compteur_bleu_arret = 0
        compteur_bleu_approche = 0
        t_depart_marche = None

        dernier_log = 0.0
        dernier_log_attente = 0.0

        servo.set_servo_angle(CANAL_TETE, ANGLE_TETE_FIXE)
        servo.set_servo_angle(CANAL_ROUES, 0)

        print("Pret. Appuie sur M pour lancer. Pas besoin d'appuyer sur Entrée.\n")

        while True:
            debut = time.time()
            touche = clavier.lire()

            if touche == "M":
                if not en_marche:
                    print(">> MARCHE")
                    en_marche = True
                    en_recherche = False
                    t_perte = None
                    compteur_bleu_arret = 0
                    compteur_bleu_approche = 0
                    t_depart_marche = time.time()

                    angle_roues = 0.0
                    err_proche_filtre = 0.0
                    err_loin_filtre = 0.0
                    err_proche_precedent = 0.0
                    derniere_direction_connue = 0.0

                    servo.set_servo_angle(CANAL_TETE, ANGLE_TETE_FIXE)
                    servo.set_servo_angle(CANAL_ROUES, 0)

                    vitesse_depart = VITESSE_MAX
                    facteur_far_depart = 1.0

                    if PREALIGN_DEPART:
                        (
                            angle_roues,
                            err_proche_filtre,
                            err_loin_filtre,
                            facteur_far_depart,
                            vitesse_depart,
                            det0,
                        ) = prealigner_depart(picam, servo)
                        err_proche_precedent = err_proche_filtre
                        if det0["trouvee"]:
                            print(
                                f">> Pré-alignement : near {det0['err_proche']:+.0f}% "
                                f"far {det0['err_loin']:+.0f}% roues {angle_roues:+.0f} "
                                f"v0 {vitesse_depart}"
                            )
                        else:
                            print(">> Pré-alignement : ligne non visible, départ en recherche")

                    # V11 : départ déjà plafonné par le régulateur de courbe.
                    # Cela évite le départ à 40 alors que le robot voit déjà une grosse erreur.
                    vitesse_actuelle = vitesse_depart
                    dernier_update_moteur = 0.0
                    drive_full(vitesse_actuelle, 1, ramp_time=0.1)
                else:
                    print(">> Déjà en marche")

            elif touche == "A":
                if en_marche:
                    print(">> ARRET")
                en_marche = False
                en_recherche = False
                t_perte = None
                vitesse_actuelle = 0
                compteur_bleu_arret = 0
                compteur_bleu_approche = 0
                t_depart_marche = None
                drive(0)
                angle_roues = 0.0
                servo.set_servo_angle(CANAL_TETE, ANGLE_TETE_FIXE)
                servo.set_servo_angle(CANAL_ROUES, 0)

            elif touche == "Q":
                print(">> QUITTER")
                break

            if not en_marche:
                maintenant = time.time()
                if maintenant - dernier_log_attente >= PERIODE_LOG_ATTENTE:
                    print("ATTENTE  moteur OFF  appuie sur M")
                    dernier_log_attente = maintenant

                dt = time.time() - debut
                if dt < PERIODE_BOUCLE:
                    time.sleep(PERIODE_BOUCLE - dt)
                continue

            image = picam.capture_array()
            det = detecter_ligne(image)
            bleu = detecter_carre_bleu(image, det["mode"])

            bleu_autorise = (
                t_depart_marche is not None and
                time.time() - t_depart_marche >= TEMPS_MIN_BLEU_APRES_DEPART
            )

            if bleu_autorise and bleu["arret"]:
                compteur_bleu_arret += 1
            else:
                compteur_bleu_arret = max(0, compteur_bleu_arret - 1)

            if bleu_autorise and bleu["arret_approche"]:
                compteur_bleu_approche += 1
            else:
                compteur_bleu_approche = max(0, compteur_bleu_approche - 1)

            if (
                compteur_bleu_arret >= BLEU_FRAMES_ARRET or
                compteur_bleu_approche >= BLEU_FRAMES_APPROCHE_ARRET
            ):
                print(
                    f">> CARRÉ BLEU : arrêt automatique "
                    f"aire={bleu['aire']:.0f} cx={bleu['cx_pct']:+.0f}% "
                    f"y={bleu['y_pct']:.2f} yBas={bleu['y_bas_pct']:.2f} "
                    f"strict={int(bleu['arret'])} approche={int(bleu['arret_approche'])}"
                )
                drive(0)
                en_marche = False
                en_recherche = False
                vitesse_actuelle = 0
                compteur_bleu_arret = 0
                compteur_bleu_approche = 0
                t_depart_marche = None
                angle_roues = 0.0
                servo.set_servo_angle(CANAL_TETE, ANGLE_TETE_FIXE)
                servo.set_servo_angle(CANAL_ROUES, 0)
                continue

            if det["trouvee"]:
                if en_recherche:
                    print(">> Ligne rouge retrouvée")
                    en_recherche = False

                t_perte = None

                far_effectif, facteur_far, raison_far = corriger_far_si_suspect(det)

                err_proche_filtre = (
                    ALPHA_PROCHE * det["err_proche"] +
                    (1.0 - ALPHA_PROCHE) * err_proche_filtre
                )
                err_loin_filtre = (
                    ALPHA_LOIN * far_effectif +
                    (1.0 - ALPHA_LOIN) * err_loin_filtre
                )

                cible_roues, derivee = calculer_commande(
                    det,
                    err_proche_filtre,
                    err_loin_filtre,
                    err_proche_precedent,
                    facteur_far,
                )
                err_proche_precedent = err_proche_filtre

                vitesse_cible = calculer_vitesse(
                    angle_roues,
                    cible_roues,
                    err_proche_filtre,
                    err_loin_filtre,
                    facteur_far,
                )

                # Plus on demande une vitesse élevée, plus on autorise les roues à rejoindre la cible vite,
                # mais sans l'excès brutal de la V9.
                ratio_v = max(1.0, vitesse_actuelle / 24.0) if vitesse_actuelle else 1.0
                slew = SLEW_ROUES_BASE + (SLEW_ROUES_RAPIDE - SLEW_ROUES_BASE) * min(1.0, (ratio_v - 1.0) / 0.7)

                angle_roues = approcher(angle_roues, cible_roues, slew)
                angle_roues = clamp(angle_roues, -ANGLE_ROUES_MAX, ANGLE_ROUES_MAX)

                if abs(angle_roues) > 2.0:
                    derniere_direction_connue = angle_roues

                vitesse_actuelle, dernier_update_moteur = maj_vitesse(
                    vitesse_cible,
                    vitesse_actuelle,
                    dernier_update_moteur,
                )

            else:
                maintenant = time.time()

                if t_perte is None:
                    t_perte = maintenant
                    en_recherche = True

                if (maintenant - t_perte) < TEMPS_RECHERCHE_AVANT_ARRET:
                    vitesse_actuelle, dernier_update_moteur = maj_vitesse(
                        VITESSE_RECHERCHE,
                        vitesse_actuelle,
                        dernier_update_moteur,
                    )

                    if abs(derniere_direction_connue) > 2.0:
                        angle_roues = approcher(angle_roues, derniere_direction_connue, SLEW_ROUES_BASE)
                    else:
                        angle_roues = approcher(angle_roues, 0.0, SLEW_ROUES_BASE)

                    raison_far = "recherche"
                    facteur_far = 0.0
                    derivee = 0.0
                    cible_roues = angle_roues
                else:
                    print(">> Ligne rouge perdue longtemps : arrêt sécurité")
                    drive(0)
                    en_marche = False
                    en_recherche = False
                    vitesse_actuelle = 0
                    angle_roues = 0.0
                    raison_far = "perdue"
                    facteur_far = 0.0
                    derivee = 0.0
                    cible_roues = 0.0

            servo.set_servo_angle(CANAL_TETE, ANGLE_TETE_FIXE)
            servo.set_servo_angle(CANAL_ROUES, angle_roues)

            maintenant = time.time()
            if maintenant - dernier_log >= PERIODE_LOG:
                if det["trouvee"]:
                    print(
                        f"OK near {det['err_proche']:+5.0f}% far {det['err_loin']:+5.0f}% "
                        f"nearF {err_proche_filtre:+5.0f}% farF {err_loin_filtre:+5.0f}% "
                        f"roues {angle_roues:+5.0f} cible {cible_roues:+5.0f} "
                        f"v {vitesse_actuelle:2d} "
                        f"pixN {det['pix_proche']:4d} pixF {det['pix_loin']:4d} "
                        f"{det['mode']} {raison_far} fFar {facteur_far:.2f} "
                        f"sRGB/sBGR {int(det['score_rgb'])}/{int(det['score_bgr'])} "
                        f"bleu A{int(bleu['aire']):4d} y{bleu['y_pct']:.2f} "
                        f"yB{bleu['y_bas_pct']:.2f} "
                        f"B{int(bleu['arret'])}/{int(bleu['arret_approche'])} "
                        f"stop{compteur_bleu_arret}/{compteur_bleu_approche}"
                    )
                else:
                    duree = 0.0 if t_perte is None else maintenant - t_perte
                    print(
                        f"RECH {duree:4.1f}s roues {angle_roues:+5.0f} "
                        f"v {vitesse_actuelle:2d} "
                        f"{det['mode']} sRGB/sBGR {int(det['score_rgb'])}/{int(det['score_bgr'])} "
                        f"bleu A{int(bleu['aire']):4d} y{bleu['y_pct']:.2f} "
                        f"yB{bleu['y_bas_pct']:.2f} "
                        f"B{int(bleu['arret'])}/{int(bleu['arret_approche'])}"
                    )
                dernier_log = maintenant

            dt = time.time() - debut
            if dt < PERIODE_BOUCLE:
                time.sleep(PERIODE_BOUCLE - dt)

    except KeyboardInterrupt:
        print("\nArrêt par Ctrl+C")

    finally:
        drive(0)

        if servo is not None:
            servo.set_servo_angle(CANAL_TETE, ANGLE_TETE_FIXE)
            servo.set_servo_angle(CANAL_ROUES, 0)
            servo.deinit()

        destroy()

        if picam is not None:
            picam.stop()

        clavier.restaurer()
        print("Système sécurisé. Fin.")


if __name__ == "__main__":
    main()
