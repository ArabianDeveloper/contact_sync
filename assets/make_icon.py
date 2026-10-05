"""Creates assets/icon.ico (needs Pillow: pip install pillow). Run it only if you want to change the icon."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
ACCENT = (79, 140, 255, 255)       # #4f8cff
WHITE = (255, 255, 255, 255)


def draw() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((32, 32, SIZE - 32, SIZE - 32), radius=230, fill=ACCENT)
    # a person: head and shoulders
    pen.ellipse((362, 200, 662, 500), fill=WHITE)
    pen.pieslice((222, 520, 802, 1100), start=180, end=360, fill=WHITE)
    return image


if __name__ == "__main__":
    target = Path(__file__).with_name("icon.ico")
    draw().resize((256, 256), Image.LANCZOS).save(
        target, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print("written", target)
