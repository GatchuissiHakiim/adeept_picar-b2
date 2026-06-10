#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  CTP2 Mastercamp - Systemes Embarques
#  Tache 10 : Suivi de source lumineuse avec gestion d'obstacle
#
#  Auteur : Maiwenn
#  Date   : 10 juin 2026
# =============================================================

import sys
import select
import time

def lire_touche():
    """Lit une touche au clavier SANS bloquer la boucle.

       Renvoie le caractere tape s'il y en a un, sinon None.
       Fonctionne dans un terminal (SSH / MobaXterm).
       """
    # select() regarde si une entree clavier est disponible.
    # Le timeout=0 veut dire : on ne patiente pas, on regarde et on repart
    dr,_,_ = select.select([sys.stdin], [], [], 0)
    if dr :
        return sys.stdin.readline().strip()
    return None

def main():
    print("=== Tache 10 - Brique 1 (squelette) ===")
    print("Commandes : 'M' = marche / 'A' = arret / Ctrl+C = quitter")

    en_marche = False  # etat du robot : avance ou non
    try:
        while True:
            # --- 1. Lecture clavier (non bloquante) ---
            touche = lire_touche()

            if touche is not None:
                if touche == 'M':
                    en_marche = True
                    print(">> Commande M : MARCHE")
                elif touche in ('A', 'a'):
                    en_marche = False
                    print(">> Commande A : ARRET")
                else:
                    print(f">> Touche ignoree : '{touche}'")

            # --- 2. Code principal (pour l'instant : juste un temoin) ---
            # Ici viendront plus tard : suivi de lumiere, detection obstacle...
            if en_marche:
                print("   [robot en marche...]")

            # --- 3. Petite pause pour ne pas saturer le processeur ---
            time.sleep(0.2)

    except KeyboardInterrupt:
        print("\nFin de programme par Ctrl-C")

    finally:
        # Ici viendra plus tard le nettoyage : arret moteur, LED off, etc.
        print("Nettoyage final realise")


if __name__ == "__main__":
    main()
