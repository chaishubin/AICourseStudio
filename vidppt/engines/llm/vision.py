"""Bounded local slide images for OpenAI-compatible multimodal requests."""
import base64
import io
from pathlib import Path
from PIL import Image, ImageOps


def image_content(text: str, image_path: Path) -> list[dict]:
    with Image.open(image_path) as source:
        picture = ImageOps.exif_transpose(source).convert('RGB')
        picture.thumbnail((2048, 2048))
        stream = io.BytesIO()
        picture.save(stream, format='PNG')
    encoded = base64.b64encode(stream.getvalue()).decode('ascii')
    return [
        {'type': 'text', 'text': text},
        {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{encoded}'}},
    ]
