from time import sleep
import sys

sys.path.append("./tache4_moteur")

from drive import drive_full, drive, destroy
from tache5_ultrason import distance_mm, alerte_sonore


DISTANCE_DANGER = 200      # mm
DISTANCE_ATTENTION = 500   # mm


def stop_robot():
    drive(0)
    sleep(0.1)


def reculer_robot():
    print("Obstacle devant -> recul")
    drive_full(25, -1, 0.5)   # vitesse 25%, direction arrière, rampe 0.5s
    sleep(0.8)                # temps de recul
    stop_robot()


def main():
    print("Integration Tache 7 : ultrason + moteur + buzzer")

    try:
        while True:
            distance = distance_mm()

            if distance is None:
                print("Mesure invalide -> stop")
                stop_robot()

            elif distance < DISTANCE_DANGER:
                print(f"DANGER : {distance:.0f} mm")
                alerte_sonore(distance)
                stop_robot()
                reculer_robot()

            elif distance < DISTANCE_ATTENTION:
                print(f"ATTENTION : {distance:.0f} mm -> avance lente")
                alerte_sonore(distance)
                drive_full(15, 1, 0.5)

            else:
                print(f"OK : {distance:.0f} mm -> avance normale")
                alerte_sonore(distance)
                drive_full(25, 1, 0.5)

            sleep(0.2)

    except KeyboardInterrupt:
        print("\nArret clavier")

    finally:
        print("Arret securise du robot")
        stop_robot()
        destroy()


if __name__ == "__main__":
    main()
