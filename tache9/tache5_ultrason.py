from gpiozero import DistanceSensor, TonalBuzzer
from time import sleep

TRIG = 23
ECHO = 24

sensor = DistanceSensor(echo=ECHO, trigger=TRIG, max_distance=2)
buzzer = TonalBuzzer(18)

def alerte_sonore(distance):
    if distance is None:
        buzzer.stop()
        return

    if distance > 600:
        buzzer.stop()

    elif distance > 300:
        buzzer.play("C4")
        sleep(0.08)
        buzzer.stop()
        sleep(0.8)

    elif distance > 150:
        buzzer.play("E4")
        sleep(0.08)
        buzzer.stop()
        sleep(0.3)

    else:
        buzzer.play("G4")
        sleep(0.08)
        buzzer.stop()
        sleep(0.08)



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
	   

            alerte_sonore(distance)
            sleep(0.2)

    except KeyboardInterrupt:
        print("\nProgramme arrêté")
