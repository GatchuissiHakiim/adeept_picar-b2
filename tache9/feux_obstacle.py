# feux_obstacle.py
import sys
import threading
sys.path.append('/home/vigiris/adeept_picar-b2/task1_leds')
sys.path.append('/home/vigiris/adeept_picar-b2/examples')

from drive import drive, destroy
from feux_detresse import setup, feux_detresse_on, feux_off
from tache5_ultrason import distance_mm

en_marche = False

def surveillance():
    global en_marche
    while True:
        if en_marche:
            dist = distance_mm()
            if dist is not None and dist < 200:
                print(f"\nObstacle à {dist:.0f} mm — ARRÊT + feux de détresse")
                drive(0)
                en_marche = False
                while not en_marche:
                    feux_detresse_on()

def main():
    global en_marche
    setup()
    thread = threading.Thread(target=surveillance, daemon=True)
    thread.start()
    print("M = avancer  |  A = arrêt  |  Ctrl+C = quitter")
    try:
        while True:
            cmd = input("Commande : ").strip().lower()
            if cmd == 'm':
                print("→ Marche avant")
                feux_off()
                en_marche = True
                drive(1)
            elif cmd == 'a':
                print("→ Arrêt")
                en_marche = False
                drive(0)
                feux_off()
    except KeyboardInterrupt:
        en_marche = False
        drive(0)
        feux_off()
        destroy()
        print("Arrêt.")

if __name__ == '__main__':
    main()
