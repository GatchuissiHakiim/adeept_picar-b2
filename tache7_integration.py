from time import sleep
import sys

sys.path.append("./tache4_moteur")

from drive import drive_full, drive, destroy
from tache5_ultrason import distance_mm, alerte_sonore
from task3_servo import ServoController


DISTANCE_DANGER = 200
DISTANCE_ATTENTION = 500


def main():
    print("Integration Tache 7 : ultrason + moteur + buzzer + servo")

    servo_controller = ServoController()

    try:
        servo_controller.set_servo_angle(0, 0)

        while True:
            distance = distance_mm()

            if distance is None:
                print("Mesure invalide -> stop")
                drive(0)

            elif distance < DISTANCE_DANGER:
                print(f"DANGER : {distance:.0f} mm -> stop + recul")
                alerte_sonore(distance)

                drive(0)
                sleep(0.2)

                servo_controller.set_servo_angle(0, 0)

                drive_full(25, -1, 0.5)
                sleep(0.8)

                drive(0)

            elif distance < DISTANCE_ATTENTION:
                print(f"ATTENTION : {distance:.0f} mm -> avance lente")
                alerte_sonore(distance)
                servo_controller.set_servo_angle(0, 0)
                drive_full(15, 1, 0.5)

            else:
                print(f"OK : {distance:.0f} mm -> avance normale")
                alerte_sonore(distance)
                servo_controller.set_servo_angle(0, 0)
                drive_full(25, 1, 0.5)

            sleep(0.2)

    except KeyboardInterrupt:
        print("\nArret clavier")

    finally:
        print("Arret securise")
        drive(0)
        destroy()

        try:
            servo_controller.center_robot_servos()
            servo_controller.deinit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
