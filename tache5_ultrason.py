from gpiozero import DistanceSensor
from time import sleep

TRIG = 23
ECHO = 24

sensor = DistanceSensor(
    echo=ECHO,
    trigger=TRIG,
    max_distance=2
)

def distance_mm(nb_mesures=5):
    mesures = []

    for _ in range(nb_mesures):
        d = sensor.distance * 1000

        if 20 <= d <= 2000:
            mesures.append(d)

        sleep(0.02)

    if len(mesures) == 0:
        return None

    return sum(mesures) / len(mesures)


if __name__ == "__main__":

    print("Test du capteur ultrason")

    try:
        while True:

            distance = distance_mm()

            if distance is None:
                print("Mesure invalide")

            else:
                print(f"Distance : {distance:.0f} mm")

            sleep(0.2)

    except KeyboardInterrupt:
        print("\nProgramme arrêté")
