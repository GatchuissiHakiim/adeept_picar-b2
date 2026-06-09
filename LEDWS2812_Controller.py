print("Hi")

import spidev
import time


from Adeept_SPI_LedPixel import Adeept_SPI_LedPixet


NB_LEDS      = 14
COULEURS_OK  = ('R', 'G', 'B', 'N')


led = Adeept_SPI_LedPixel(count=NB_LEDS, bright=255)
led.setDaemon(True)
led.start()

def piloter_led(numero: int, couleur: str, intensite: int = 255) -> None:

    if numero < 0 or numero > NB_LEDS:
        raise ValueError(f"Numéro de LED invalide : {numero} (doit être entre 0 et {NB_LEDS - 1})")


    if couleur not in COULEURS_OK:
        raise ValueError(f"Couleur invalide : {couleur} (doit être une de {COULEURS_OK})")


    if intensite < 0 or intensite > 255:
        raise ValueError(f"Intensité invalide : {couleur} (doit être entre 0 et 255)")

    r, g, b = 0, 0, 0

    if couleur == 'R':
        r = intensite
        g = 0
        b = 0
    elif couleur == 'G':
        r = 0
        g = intensite
        b = 0
    elif couleur == 'B':
        r = 0
        g = 0
        b = intensite
    elif couleur == 'N':
        r = 0
        g = 0
        b = 0

    led.set_led_color(numero, r, g, b)


def protocole_manuel() -> None:
    """Boucle interactive pour piloter les LEDs depuis le terminal."""

    print("-Controleur WS2812-")
    print(f"LEDs disponibles : 0 à {NB_LEDS - 1}")
    print("Couleurs : R, G, B, N (éteinte)")
    print("Tapez 'q' à n'importe quelle étape pour quitter.\n")

    while True:


        while True:
            saisie = input("Numéro de LED : ").strip()
            if saisie.lower() == 'q':
                return
            try:
                numero = int(saisie)
            except ValueError:
                print("  Erreur : entre un nombre entier.")
                continue
            if numero < 0 or numero >= NB_LEDS:
                print(f"  Erreur : doit être entre 0 et {NB_LEDS - 1}.")
                continue
            break


        while True:
            saisie = input("Couleur (R/G/B/N) : ").strip().upper()
            if saisie.lower() == 'q':
                return
            if saisie not in COULEURS_OK:
                print(f"  Erreur : choisir parmi {COULEURS_OK}.")
                continue
            couleur = saisie
            break


        intensite = 255
        if couleur != 'N':
            while True:
                saisie = input("Intensité (0-255) [Entrée = 255] : ").strip()
                if saisie.lower() == 'q':
                    return
                if saisie == '':
                    break  # garde la valeur par défaut 255
                try:
                    intensite = int(saisie)
                except ValueError:
                    print("  Erreur : entre un nombre entier.")
                    continue
                if intensite < 0 or intensite > 255:
                    print("  Erreur : l'intensité doit être entre 0 et 255.")
                    continue
                break


        try:
            piloter_led(numero, couleur, intensite)
            print(f"  → LED {numero} : {couleur} à intensité {intensite}\n")
        except ValueError as e:
            print(f"  Erreur : {e}\n")


if __name__ == '__main__':
    try:
        protocole_manuel()
    except KeyboardInterrupt:
        pass
    finally:
        led.set_all_led_color(0, 0, 0)
        print("\nToutes les LEDs éteintes. Au revoir.")