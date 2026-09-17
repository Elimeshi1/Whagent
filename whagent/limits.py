"""Platform constants: endpoints, caps, accepted media types, rate limits.

Every value here comes from the WhatsApp Agent Platform Developer Manual
(version 1, August 25, 2026).
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_BASE_URL",
    "MESSAGING_PRODUCT",
    "SENDABLE_TYPES",
    "RECEIVABLE_TYPES",
    "MEDIA_TYPES",
    "CAPTIONABLE_TYPES",
    "TEXT_BODY_MAX",
    "CAPTION_MAX",
    "UPDATES_LIMIT_MAX",
    "UPDATES_LIMIT_DEFAULT",
    "UPDATES_TIMEOUT_MAX",
    "UPDATES_TIMEOUT_DEFAULT",
    "TYPING_INDICATOR_SECONDS",
    "RETENTION_DAYS",
    "SIZE_LIMITS",
    "ACCEPTED_MIME_TYPES",
    "MIME_CATEGORY",
    "RATE_LIMITS",
    "size_limit_for",
    "category_for",
]

DEFAULT_BASE_URL = "https://api.whatsapp.com/agent/v1"
MESSAGING_PRODUCT = "whatsapp"

#: Message types an agent may send.
SENDABLE_TYPES = ("text", "image", "audio", "video", "document", "sticker")
#: Message types an agent may receive — the sendable ones plus ``reaction``.
RECEIVABLE_TYPES = SENDABLE_TYPES + ("reaction",)
#: Types whose payload carries a media id.
MEDIA_TYPES = ("image", "audio", "video", "document", "sticker")
#: Types that accept a caption.
CAPTIONABLE_TYPES = ("image", "video", "document")

TEXT_BODY_MAX = 4096
CAPTION_MAX = 1024

UPDATES_LIMIT_DEFAULT = 50
UPDATES_LIMIT_MAX = 100
UPDATES_TIMEOUT_DEFAULT = 15
UPDATES_TIMEOUT_MAX = 25

#: A typing indicator clears once you reply, or after this many seconds.
TYPING_INDICATOR_SECONDS = 25
#: Buffered updates, and uploaded media, expire after this many days.
RETENTION_DAYS = 30

MB = 1024 * 1024
KB = 1024

#: Upload size limit in bytes, per media category.
SIZE_LIMITS = {
    "image": 5 * MB,
    "sticker": 500 * KB,
    "video": 16 * MB,
    "audio": 16 * MB,
    "document": 16 * MB,
    "binary": 16 * MB,
}

#: Accepted upload MIME type -> media category.
MIME_CATEGORY = {
    # Image
    "image/jpeg": "image",
    "image/png": "image",
    # Sticker
    "image/webp": "sticker",
    # Video
    "video/mp4": "video",
    "video/3gpp": "video",
    # Audio
    "audio/aac": "audio",
    "audio/mp4": "audio",
    "audio/mpeg": "audio",
    "audio/amr": "audio",
    "audio/ogg": "audio",
    "audio/opus": "audio",
    # Document
    "application/pdf": "document",
    "text/plain": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    "application/vnd.ms-powerpoint": "document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "document",
    # Generic binary
    "application/octet-stream": "binary",
}

#: Every MIME type the upload endpoint accepts.
ACCEPTED_MIME_TYPES = frozenset(MIME_CATEGORY)

#: Requests per rolling 60-second window, per agent, per method.
RATE_LIMITS = {
    "messages": 12,
    "statuses": 12,
    "media:post": 12,
    "media:get": 12,
    "media:delete": 12,
    "updates": 15,
}


def category_for(mime_type: str) -> str | None:
    """Media category for a MIME type, or ``None`` when it is not accepted."""
    return MIME_CATEGORY.get(_normalize(mime_type))


def size_limit_for(mime_type: str) -> int | None:
    """Upload size limit in bytes for a MIME type, or ``None`` when not accepted."""
    category = category_for(mime_type)
    return SIZE_LIMITS[category] if category else None


def _normalize(mime_type: str) -> str:
    # "audio/ogg; codecs=opus" -> "audio/ogg"
    return (mime_type or "").split(";", 1)[0].strip().lower()
