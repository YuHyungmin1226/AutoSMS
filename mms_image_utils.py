import math
import os
import tempfile
from typing import Iterable, List, Optional

from PIL import Image, ImageOps


MMS_MAX_BYTES = 200 * 1024
MMS_MAX_WIDTH = 1500
MMS_MAX_HEIGHT = 1440
MMS_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}


def validate_image_paths(image_paths: Iterable[str]) -> List[str]:
    paths = [os.path.abspath(path) for path in image_paths if path]
    for path in paths:
        ext = os.path.splitext(path)[1].lower()
        if ext not in MMS_ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported image format: {os.path.basename(path)}")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image file not found: {path}")
    return paths


def prepare_mms_image(image_paths: Iterable[str]) -> Optional[str]:
    paths = validate_image_paths(image_paths)
    if not paths:
        return None

    images = [_open_image(path) for path in paths]
    try:
        if len(images) == 1:
            canvas = _fit_image(images[0], MMS_MAX_WIDTH, MMS_MAX_HEIGHT)
        else:
            canvas = _make_collage(images)
        return _save_under_limit(canvas)
    finally:
        for image in images:
            image.close()


def _open_image(path: str) -> Image.Image:
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    if getattr(image, "is_animated", False):
        image.seek(0)
    return image.convert("RGB")


def _fit_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    fitted = image.copy()
    resample = getattr(Image, "Resampling", Image).LANCZOS
    fitted.thumbnail((max_width, max_height), resample)
    background = Image.new("RGB", fitted.size, "white")
    background.paste(fitted, (0, 0))
    return background


def _make_collage(images: List[Image.Image]) -> Image.Image:
    count = len(images)
    cols = min(3, math.ceil(math.sqrt(count)))
    rows = math.ceil(count / cols)
    gap = 12
    outer = 12
    cell_w = (MMS_MAX_WIDTH - outer * 2 - gap * (cols - 1)) // cols
    cell_h = (MMS_MAX_HEIGHT - outer * 2 - gap * (rows - 1)) // rows

    canvas = Image.new("RGB", (MMS_MAX_WIDTH, MMS_MAX_HEIGHT), "white")
    for index, image in enumerate(images):
        row = index // cols
        col = index % cols
        fitted = _fit_image(image, cell_w, cell_h)
        x = outer + col * (cell_w + gap) + (cell_w - fitted.width) // 2
        y = outer + row * (cell_h + gap) + (cell_h - fitted.height) // 2
        canvas.paste(fitted, (x, y))
    return canvas


def _save_under_limit(image: Image.Image) -> str:
    quality = 88
    scale = 1.0

    while scale >= 0.55:
        working = image
        if scale < 1.0:
            size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
            resample = getattr(Image, "Resampling", Image).LANCZOS
            working = image.resize(size, resample)

        while quality >= 45:
            fd, path = tempfile.mkstemp(prefix="autosms_mms_", suffix=".jpg")
            os.close(fd)
            working.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
            if os.path.getsize(path) <= MMS_MAX_BYTES:
                return path
            os.remove(path)
            quality -= 8

        quality = 84
        scale -= 0.1

    raise ValueError("Could not compress MMS image under 200KB.")
