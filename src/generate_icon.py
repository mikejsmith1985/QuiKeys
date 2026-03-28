"""Generate the QuiKeys system tray icon (saved to assets/icon.png)."""

import os
import sys
from PIL import Image, ImageDraw, ImageFont


def generate_icon(size: tuple[int, int] = (64, 64)) -> Image.Image:
    """Create a simple 'QK' icon on a dark teal background."""
    img = Image.new("RGBA", size, (30, 120, 120, 255))
    draw = ImageDraw.Draw(img)

    # Draw a simple key outline
    cx, cy = size[0] // 2, size[1] // 2
    r = size[0] // 4

    # Key bow (circle)
    bow_r = r - 2
    draw.ellipse(
        [cx - bow_r - 8, cy - bow_r, cx - 8 + bow_r, cy + bow_r],
        outline=(220, 240, 220, 255),
        width=4,
    )
    # Key blade (rectangle)
    blade_x = cx - 8 + bow_r - 2
    draw.rectangle(
        [blade_x, cy - 4, blade_x + r + 6, cy + 4],
        fill=(220, 240, 220, 255),
    )
    # Notches
    for notch_x in [blade_x + r - 4, blade_x + r + 2]:
        draw.rectangle([notch_x, cy + 4, notch_x + 3, cy + 9], fill=(220, 240, 220, 255))

    return img


def save_icon(out_path: str) -> None:
    img = generate_icon()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, format="PNG")
    # Also save .ico for Windows
    ico_path = os.path.splitext(out_path)[0] + ".ico"
    img.save(ico_path, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(base, "assets", "icon.png")
    save_icon(out)
    print(f"Icon saved to {out}")
