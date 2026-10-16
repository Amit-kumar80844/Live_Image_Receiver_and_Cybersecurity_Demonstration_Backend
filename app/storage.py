import io
from pathlib import Path
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException, UploadFile
from app.config import settings
ALLOWED = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}
async def read_and_validate(upload: UploadFile):
    if upload.content_type not in {v[0] for v in ALLOWED.values()}: raise HTTPException(415, "Only JPEG, PNG, and WebP images are supported")
    data = await upload.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes: raise HTTPException(413, "Image exceeds the maximum upload size")
    try:
        image = Image.open(io.BytesIO(data)); image.verify(); image = Image.open(io.BytesIO(data)); fmt = image.format
        if fmt not in ALLOWED or ALLOWED[fmt][0] != upload.content_type: raise ValueError("signature mismatch")
        if image.width > settings.max_image_width or image.height > settings.max_image_height: raise ValueError("dimensions too large")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc: raise HTTPException(400, f"Invalid image: {exc}") from exc
    return data, image, fmt, ALLOWED[fmt][1]
def save_image(data, suffix):
    settings.upload_dir.mkdir(parents=True, exist_ok=True); name = f"{uuid4().hex}{suffix}"; (settings.upload_dir / name).write_bytes(data); return name
def remove_image(filename):
    path = settings.upload_dir / Path(filename).name
    if path.parent.resolve() == settings.upload_dir.resolve() and path.exists(): path.unlink()
