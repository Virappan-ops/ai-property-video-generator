"""Generates required folders, font license, and 5 synthetic 1600x1000 placeholder images."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def create_placeholder_images() -> None:
    """Create 5 synthetic gradient placeholder images (1600x1000) in input/images/."""
    img_dir = Path("input/images")
    img_dir.mkdir(parents=True, exist_ok=True)

    palettes = [
        ((28, 58, 94), (72, 126, 176)),
        ((44, 82, 52), (96, 158, 108)),
        ((92, 52, 40), (168, 108, 86)),
        ((62, 44, 88), (124, 98, 164)),
        ((34, 78, 82), (82, 148, 154)),
    ]

    for idx, (top_rgb, bot_rgb) in enumerate(palettes, start=1):
        width, height = 1600, 1000
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        for y in range(height):
            ratio = y / float(height - 1)
            r = int(top_rgb[0] * (1 - ratio) + bot_rgb[0] * ratio)
            g = int(top_rgb[1] * (1 - ratio) + bot_rgb[1] * ratio)
            b = int(top_rgb[2] * (1 - ratio) + bot_rgb[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        draw.rectangle([80, 80, width - 80, height - 80], outline=(255, 255, 255), width=3)
        draw.rectangle([120, 120, width - 120, height - 120], outline=(220, 220, 220), width=1)

        text = f"Placeholder {idx} – replace with property photo"
        font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])
        draw.text(((width - tw) // 2, (height - th) // 2), text, fill=(255, 255, 255), font=font)

        img.save(img_dir / f"img{idx}.jpg", "JPEG", quality=92)


def setup_directories_and_licenses() -> None:
    """Ensure required asset, input, and output folders exist."""
    for folder in ["assets/fonts", "assets/music", "output/logs", "output/temp"]:
        Path(folder).mkdir(parents=True, exist_ok=True)

    license_path = Path("assets/fonts/LICENSE-DejaVu.txt")
    if not license_path.exists():
        license_path.write_text(
            "DejaVu Fonts License (Bitstream Vera / Arev Fonts)\n"
            "Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved.\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
            "of the fonts accompanying this license to use, reproduce, and distribute them.\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    setup_directories_and_licenses()
    create_placeholder_images()
    print("Created directories, license file, and 5 synthetic placeholder images in input/images/.")