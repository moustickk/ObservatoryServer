"""Genere l'icone .ico de l'application (et de l'installateur).

A lancer une fois, puis le fichier produit est versionne :

    .\\.venv\\Scripts\\python.exe packaging\\make_icon.py

L'icone reprend celle de la tray app : un disque vert avec un toit.
"""

from pathlib import Path

from PIL import Image, ImageDraw


SIZES = (16, 32, 48, 64, 128, 256)

GREEN = (63, 185, 80, 255)
DARK = (15, 20, 26, 255)

ROOT = Path(__file__).resolve().parents[1]

OUTPUT = ROOT / "assets" / "observatory.ico"


def draw(size):

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)

    margin = max(1, size // 16)
    pen.ellipse(
        (margin, margin, size - margin, size - margin),
        fill=GREEN,
    )

    width = max(1, size // 10)

    pen.line(
        [(size * 0.28, size * 0.60), (size * 0.50, size * 0.38)],
        fill=DARK,
        width=width,
    )
    pen.line(
        [(size * 0.50, size * 0.38), (size * 0.72, size * 0.60)],
        fill=DARK,
        width=width,
    )
    pen.line(
        [(size * 0.34, size * 0.70), (size * 0.66, size * 0.70)],
        fill=DARK,
        width=max(1, width - 1),
    )

    return image


def main():

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    largest = draw(max(SIZES))

    largest.save(
        OUTPUT,
        format="ICO",
        sizes=[(size, size) for size in SIZES],
    )

    print(f"ecrit : {OUTPUT} ({OUTPUT.stat().st_size} octets)")


if __name__ == "__main__":
    main()
