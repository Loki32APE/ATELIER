"""Safe metadata and byte-signature checks for reference image uploads.

This module is framework-independent. Flask routes can call it before
persisting or forwarding uploaded images to an AI provider.
"""

from dataclasses import dataclass
from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError
from pathlib import PurePath
from typing import Iterable, Optional, Tuple

from .schemas import SUPPORTED_IMAGE_MIME_TYPES, ValidationResult

MAX_REFERENCE_COUNT = 6
MAX_REFERENCE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_REFERENCE_BYTES = 10 * 1024 * 1024

MAX_IMAGE_PIXELS = 40_000_000

_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}

_SIGNATURES = {
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda data: (
        len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    ),
}


@dataclass(frozen=True)
class ReferenceUpload:
    """An in-memory reference upload awaiting persistence or AI processing."""

    filename: str
    declared_mime_type: str
    content: bytes


def _safe_filename(filename: str) -> bool:
    """Reject empty names and path-like values; never trust client paths."""
    if not isinstance(filename, str) or not filename.strip():
        return False
    if "\x00" in filename or "/" in filename or "\\" in filename:
        return False
    return PurePath(filename).name == filename and filename not in {".", ".."}


def validate_reference_uploads(
    uploads: Iterable[ReferenceUpload],
    *,
    max_references: int = MAX_REFERENCE_COUNT,
    max_file_bytes: int = MAX_REFERENCE_BYTES,
    max_total_bytes: int = MAX_TOTAL_REFERENCE_BYTES,
) -> ValidationResult:
    """Validate count, sizes, filenames, MIME declarations, and file signatures.

    The declared MIME type is checked against the actual file signature so a
    client cannot pass an arbitrary file by merely labelling it as an image.
    The caller remains responsible for request-size limits and safe storage.
    """
    errors = []
    items = list(uploads)

    if not items:
        return ValidationResult(False, ("At least one reference image is required.",))
    if len(items) > max_references:
        errors.append(f"No more than {max_references} reference images are allowed.")

    total_bytes = 0
    for index, upload in enumerate(items):
        label = f"Reference {index + 1}"
        if not isinstance(upload, ReferenceUpload):
            errors.append(f"{label} has an invalid upload descriptor.")
            continue

        if not _safe_filename(upload.filename):
            errors.append(f"{label} has an unsafe filename.")

        if upload.declared_mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
            errors.append(f"{label} uses an unsupported image type.")
            continue

        if not isinstance(upload.content, bytes) or not upload.content:
            errors.append(f"{label} is empty or has invalid content.")
            continue

        size = len(upload.content)
        total_bytes += size
        if size > max_file_bytes:
            errors.append(f"{label} exceeds the per-image size limit.")

        signature_check = _SIGNATURES[upload.declared_mime_type]
        if not signature_check(upload.content):
            errors.append(f"{label} content does not match its declared image type.")
            continue

        # A matching magic header is not proof that the file is a valid image.
        # Decode metadata and verify the complete file before forwarding bytes.
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(upload.content)) as image:
                    if image.format != _FORMATS[upload.declared_mime_type]:
                        errors.append(f"{label} actual image format does not match its declared MIME type.")
                        continue
                    width, height = image.size
                    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                        errors.append(f"{label} dimensions exceed the safe image pixel limit.")
                        continue
                    image.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
                Image.DecompressionBombWarning):
            errors.append(f"{label} is not a valid, safely decodable image.")

    if total_bytes > max_total_bytes:
        errors.append("Combined reference images exceed the total size limit.")

    return ValidationResult(valid=not errors, errors=tuple(errors))
