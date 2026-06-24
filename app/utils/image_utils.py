# =========================================================
# FILE: app/utils/image_utils.py
# =========================================================

from __future__ import annotations

from typing import Tuple

from PIL import Image


MAX_AVATAR_SIZE = (1024, 1024)
THUMBNAIL_SIZE = (300, 300)


def get_image_size(
    image_path: str,
) -> Tuple[int, int]:

    with Image.open(image_path) as image:
        return image.size


def resize_image(
    input_path: str,
    output_path: str,
    size: Tuple[int, int] = MAX_AVATAR_SIZE,
) -> str:

    with Image.open(input_path) as image:
        image.thumbnail(size)
        image.save(output_path)

    return output_path


def create_thumbnail(
    input_path: str,
    output_path: str,
) -> str:

    with Image.open(input_path) as image:
        image.thumbnail(THUMBNAIL_SIZE)
        image.save(output_path)

    return output_path


def validate_image(
    image_path: str,
) -> bool:

    try:
        with Image.open(image_path) as image:
            image.verify()

        return True

    except Exception:
        return False