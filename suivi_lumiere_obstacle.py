#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP2 Mastercamp - Systemes Embarques
#  Tache 10 : Suivi de source lumineuse avec gestion d'obstacle
#
#  Auteur : Maïwen
#  Date   : 10 juin 2026
# =============================================================

import sys
import select
import time
from drive import drive_full, drive, destroy

# --- Module moteur de la Tache 4 (ecrit par Anthony) ---
# drive_full(speed, direction, ramp_time) : avance/recule avec rampe
#   direction : 1 = avant, -1 = arriere, 0 = stop
# drive(0)   : arret simple
# destroy()  : arret + liberation propre du PWM
from drive import drive_full, drive, destroy

# -------------------------------------------------------------
#  Parametres
# -------------------------------------------------------------
VITESSE_MARCHE = 25  # % du max : vitesse reduite pour les tests (consigne)
RAMPE = 1.0  # duree de la rampe d'acceleration en secondes
PERIODE_BOUCLE = 0.2  # pause entre deux tours de boucle (secondes)


# -------------------------------------------------------------
#  Lecture clavier non bloquante
# -------------------------------------------------------------
def lire_touche():
    """Lit une touche au clavier SANS bloquer la boucle.

    Renvoie le caractere tape (suivi de Entree) s'il y en a un,
    sinon None. Fonctionne dans un terminal (SSH / MobaXterm).
    """
    dr, _, _ = select.select([sys.stdin], [], [], 0)
    if dr:  # une entree est disponible
        return sys.stdin.readline().strip()
    return None  # rien tape : la boucle continue


# -------------------------------------------------------------
#  Programme principal
# -------------------------------------------------------------
def main():
    print("=== Tache 10 - Brique 2 (marche avant / arret) ===")
    print("Commandes : 'M' = marche / 'A' = arret / Ctrl+C = quitter")

    en_marche = False  # etat courant du robot

    try:
        while True:
            # --- 1. Lecture des commandes clavier ---
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

            # --- 2. Code principal ---
            # (ici viendront plus tard : detection obstacle, suivi lumiere)

            # --- 3. Pause pour ne pas saturer le processeur ---
            time.sleep(PERIODE_BOUCLE)

    except KeyboardInterrupt:
        print("\nFin de programme par Ctrl-C")

    finally:
        # Securite : quoi qu'il arrive, on coupe le moteur proprement
        destroy()
        print("Nettoyage final realise")


if __name__ == "__main__":
    main()