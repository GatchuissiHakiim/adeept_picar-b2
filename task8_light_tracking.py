import time
import argparse
import smbus


ADS7830_ADDRESS = 0x48
ADS7830_CMD = 0x84
LIGHT_TRACKING_CHANNEL = 1

DEFAULT_INTERVAL = 0.30
DEFAULT_CALIBRATION_SAMPLES = 20
DEFAULT_THRESHOLD = 15


class ADS7830:
    def __init__(self, bus_number=1, address=ADS7830_ADDRESS):
        self.bus = smbus.SMBus(bus_number)
        self.address = address
        self.cmd = ADS7830_CMD

    def analog_read(self, channel):
        """
        Lit un canal ADC de l'ADS7830.

        channel : entier de 0 à 7
        retour  : valeur entière de 0 à 255
        """
        if channel < 0 or channel > 7:
            raise ValueError("Le canal ADC doit être compris entre 0 et 7.")

        command = self.cmd | (((channel << 2 | channel >> 1) & 0x07) << 4)
        return self.bus.read_byte_data(self.address, command)


class LightTrackingSensor:
    def __init__(self, threshold=DEFAULT_THRESHOLD):
        self.adc = ADS7830()
        self.channel = LIGHT_TRACKING_CHANNEL
        self.threshold = threshold

        self.center_value = None
        self.min_value = 255
        self.max_value = 0
        self.total_value = 0
        self.measure_count = 0

        self.state_counter = {
            "balanced": 0,
            "low": 0,
            "high": 0,
        }

    def read_value(self):
        """
        Lit la valeur brute du module Light Tracking.
        """
        return self.adc.analog_read(self.channel)

    def calibrate(self, samples=DEFAULT_CALIBRATION_SAMPLES, delay=0.05):
        """
        Calibre la valeur d'équilibre à partir de plusieurs mesures.

        Pendant cette phase, il faut placer le robot dans une condition neutre :
        lumière ambiante stable, sans lampe ni obstacle directement sur LDR1 ou LDR2.
        """
        print("Calibration de la valeur d'équilibre...")
        print("Ne pas éclairer ni occulter directement LDR1 ou LDR2 pendant cette phase.")

        values = []

        for _ in range(samples):
            value = self.read_value()
            values.append(value)
            time.sleep(delay)

        self.center_value = sum(values) / len(values)

        print(f"Valeur d'équilibre calibrée : {self.center_value:.1f}")
        print()

    def classify_value(self, value):
        """
        Classe la mesure par rapport à la valeur d'équilibre calibrée.
        """
        if self.center_value is None:
            raise RuntimeError("Le capteur doit être calibré avant l'interprétation.")

        delta = value - self.center_value

        if abs(delta) <= self.threshold:
            state = "balanced"
            interpretation = "équilibre entre LDR1 et LDR2"
        elif delta < -self.threshold:
            state = "low"
            interpretation = "déséquilibre côté valeur basse : LDR1 occulté / LDR2 dominant"
        else:
            state = "high"
            interpretation = "déséquilibre côté valeur haute : LDR2 occulté / LDR1 dominant"

        return state, delta, interpretation

    def update_stats(self, value, state):
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        self.total_value += value
        self.measure_count += 1

        if state in self.state_counter:
            self.state_counter[state] += 1

    def visual_bar(self, value, width=30):
        """
        Affiche une jauge ASCII proportionnelle à la valeur ADC.
        """
        value = max(0, min(255, value))
        filled = int((value / 255) * width)
        return "[" + "#" * filled + "." * (width - filled) + "]"

    def print_measure(self):
        value = self.read_value()
        state, delta, interpretation = self.classify_value(value)
        self.update_stats(value, state)

        bar = self.visual_bar(value)

        print(
            f"ADC A1: {value:3d} | "
            f"centre: {self.center_value:6.1f} | "
            f"écart: {delta:7.1f} | "
            f"{bar} | "
            f"{interpretation}"
        )

    def print_summary(self):
        print()
        print("Résumé des mesures :")

        if self.measure_count == 0:
            print("Aucune mesure enregistrée.")
            return

        average = self.total_value / self.measure_count

        print(f"  Nombre de mesures : {self.measure_count}")
        print(f"  Valeur minimale   : {self.min_value}")
        print(f"  Valeur maximale   : {self.max_value}")
        print(f"  Valeur moyenne    : {average:.1f}")
        print(f"  Centre calibré    : {self.center_value:.1f}")
        print(f"  Seuil utilisé     : +/- {self.threshold}")
        print()

        total = self.measure_count

        labels = {
            "balanced": "équilibre LDR1/LDR2",
            "low": "valeur basse",
            "high": "valeur haute",
        }

        for state, count in self.state_counter.items():
            percent = (count / total) * 100
            print(f"  {labels[state]:22s} : {count:4d} mesures ({percent:5.1f} %)")


def print_start_message(threshold, interval, samples):
    print("=== Tâche 8 : Capteur de suivi de lumière ===")
    print("Lecture du module Light Tracking sur l'ADC ADS7830.")
    print()
    print("Configuration :")
    print(f"  Adresse I2C ADS7830 : 0x{ADS7830_ADDRESS:02X}")
    print(f"  Canal utilisé       : A{LIGHT_TRACKING_CHANNEL}")
    print(f"  Intervalle mesures  : {interval} s")
    print(f"  Échantillons calib. : {samples}")
    print(f"  Seuil d'écart       : +/- {threshold}")
    print()
    print("Convention expérimentale retenue :")
    print("  centre +/- seuil  -> équilibre entre LDR1 et LDR2")
    print("  valeur basse      -> LDR1 occulté / LDR2 dominant")
    print("  valeur haute      -> LDR2 occulté / LDR1 dominant")
    print()
    print("Protocole conseillé :")
    print("  1. Lancer le programme sans éclairer ni occulter directement le module.")
    print("  2. Laisser la calibration automatique se faire.")
    print("  3. Occulter LDR1 avec le doigt et vérifier l'apparition de la valeur basse.")
    print("  4. Occulter LDR2 avec le doigt et vérifier l'apparition de la valeur haute.")
    print("  5. Ne pas considérer le cas deux doigts comme une mesure directionnelle fiable.")
    print()
    print("Arrêt : Ctrl + C")
    print()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Tâche 8 : mesure du capteur de suivi de lumière Adeept PiCar-B"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="intervalle entre deux mesures en secondes"
    )

    parser.add_argument(
        "--samples",
        type=int,
        default=DEFAULT_CALIBRATION_SAMPLES,
        help="nombre d'échantillons utilisés pour la calibration"
    )

    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help="seuil d'écart autour de la valeur calibrée"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print_start_message(args.threshold, args.interval, args.samples)

    sensor = LightTrackingSensor(threshold=args.threshold)

    try:
        sensor.calibrate(samples=args.samples)

        while True:
            sensor.print_measure()
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nArrêt du programme demandé.")

    finally:
        sensor.print_summary()
        print("Fin.")


if __name__ == "__main__":
    main()