"""Flask-compatible boundary for safely preparing legacy Studio uploads.

This module intentionally avoids importing Flask. It accepts request-like
form/files mappings and duck-typed FileStorage objects, so the shared engine
remains framework-independent and easy to test.
"""
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, Dict

from .adapters import adapt_legacy_studio_request
from .uploads import (
    MAX_REFERENCE_BYTES,
    ReferenceUpload,
    validate_reference_uploads,
)


@dataclass(frozen=True)
class PreparedLegacyStudioRequest:
    """Validated request metadata plus image bytes keyed by legacy field name."""

    payload: Dict[str, Any]
    uploads_by_field: Dict[str, ReferenceUpload]


def _read_upload(files: Mapping[str, Any], field_name: str):
    """Read one optional FileStorage-like object and restore its stream position."""
    upload = files.get(field_name)
    if upload is None:
        return None

    filename = getattr(upload, "filename", None)
    # Match the old route: an absent file or an empty browser filename is omitted.
    if not filename:
        return None
    if not isinstance(filename, str):
        raise ValueError(f"{field_name} has an invalid filename.")

    mime_type = getattr(upload, "mimetype", None)
    if not isinstance(mime_type, str):
        raise ValueError(f"{field_name} has an invalid image MIME type.")

    stream = getattr(upload, "stream", None)
    if stream is None or not callable(getattr(stream, "read", None)):
        raise ValueError(f"{field_name} is not a readable upload.")

    try:
        # Read at most one byte beyond the per-image limit. This lets the
        # validator reject oversized files without loading an unbounded upload
        # into memory first.
        content = stream.read(MAX_REFERENCE_BYTES + 1)
    except Exception as exc:
        raise ValueError(f"{field_name} could not be read.") from exc
    finally:
        # FileStorage streams are seekable; restore them for any later consumer.
        seek = getattr(stream, "seek", None)
        if callable(seek):
            try:
                seek(0)
            except Exception:
                pass

    if not isinstance(content, bytes):
        raise ValueError(f"{field_name} did not contain binary image data.")

    return ReferenceUpload(
        filename=filename,
        declared_mime_type=mime_type.lower(),
        content=content,
    )


def prepare_legacy_studio_request(
    form: Mapping[str, Any],
    files: Mapping[str, Any],
) -> PreparedLegacyStudioRequest:
    """Validate legacy image bytes, then adapt the form into Vision Studio.

    Raises ValueError for malformed form/files mappings or unsafe uploads.
    No Flask route, AI provider, filesystem, or background job is touched.
    """
    if not isinstance(form, Mapping):
        raise ValueError("Legacy form data must be a mapping.")
    if not isinstance(files, Mapping):
        raise ValueError("Uploaded files must be a mapping.")

    uploads_by_field = {}
    for field_name in ("image1", "image2"):
        upload = _read_upload(files, field_name)
        if upload is not None:
            uploads_by_field[field_name] = upload

    if uploads_by_field:
        result = validate_reference_uploads(list(uploads_by_field.values()))
        if not result.valid:
            raise ValueError("; ".join(result.errors))

    metadata = {
        field_name: {
            "filename": upload.filename,
            "mime_type": upload.declared_mime_type,
        }
        for field_name, upload in uploads_by_field.items()
    }
    payload = adapt_legacy_studio_request(form, metadata)
    return PreparedLegacyStudioRequest(
        payload=payload,
        uploads_by_field=uploads_by_field,
    )
