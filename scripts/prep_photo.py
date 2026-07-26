from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import remove


def preprocess(image_path: str):
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(image_path)

    # Load image
    img = Image.open(image_path).convert("RGBA")

    # Remove background
    print("Removing background...")
    img = remove(img)

    # Convert to numpy
    rgba = np.array(img)

    # White background
    white = np.ones((rgba.shape[0], rgba.shape[1], 3), dtype=np.uint8) * 255

    alpha = rgba[:, :, 3:] / 255.0
    rgb = rgba[:, :, :3]

    composite = (rgb * alpha + white * (1 - alpha)).astype(np.uint8)

    # Convert to grayscale
    gray = cv2.cvtColor(composite, cv2.COLOR_RGB2GRAY)

    # CLAHE
    clahe = cv2.createCLAHE(
        clipLimit=2.5,
        tileGridSize=(8, 8)
    )

    enhanced = clahe.apply(gray)

    output = image_path.parent / "source-prepped.png"

    cv2.imwrite(str(output), enhanced)

    print(f"Saved: {output}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("python scripts/prep_photo.py assets/profile.png")
        sys.exit(1)

    preprocess(sys.argv[1])