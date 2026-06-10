from time import sleep
#rien
from tache5_ultrason import distance_mm,alerte_sonore
from tache4_moteur.drive import drive_full


def main():
    print("Test integration - Tache 7")

    while True:
        distance = distance_mm()

        if distance is None:
            print("Mesure invalide")

        elif distance < 200:
            drive_full(0,1,0.0)

        elif distance < 500:
  	        drive_full(15,1,0.5)

        else:
            drive_full(30,1,1.0)
        alerte_sonore(distance)

        sleep(0.5)


if __name__ == "__main__":
    main()
