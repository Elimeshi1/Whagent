"""Exceptions raised by :mod:`whagent`.

Every error returned by the WhatsApp Agent Platform has the shape::

    {"error": {"message": ..., "type": "OAuthException", "code": 131009,
               "error_data": {"messaging_product": "whatsapp", "details": ...},
               "fbtrace_id": "..."}}

``error.code`` identifies the failure; the HTTP status only indicates its
broad class.  :func:`error_from_response` maps both onto the classes below.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "WhagentError",
    "ValidationError",
    "TransportError",
    "APIError",
    "AuthenticationError",
    "InvalidRequestError",
    "ForbiddenError",
    "NotFoundError",
    "MediaNotFoundError",
    "MediaUploadError",
    "RateLimitError",
    "NotDeliveredError",
    "PollReplacedError",
    "ServerError",
    "error_from_response",
]


class WhagentError(Exception):
    """Base class for everything this library raises."""


class ValidationError(WhagentError, ValueError):
    """A request was rejected locally, before it reached the API."""


class TransportError(WhagentError):
    """The request never produced an HTTP response (network failure, timeout)."""


class APIError(WhagentError):
    """An error response from the API."""

    #: ``True`` when the same request may reasonably be sent again after a backoff.
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: int | None = None,
        details: str | None = None,
        fbtrace_id: str | None = None,
        error_type: str | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.details = details
        self.fbtrace_id = fbtrace_id
        self.error_type = error_type
        self.raw = raw or {}

    def __str__(self) -> str:
        parts = [self.message]
        if self.details and self.details not in self.message:
            parts.append(self.details)
        suffix = ", ".join(
            f"{k}={v}"
            for k, v in (("http", self.status), ("code", self.code), ("fbtrace_id", self.fbtrace_id))
            if v is not None
        )
        text = " — ".join(parts)
        return f"{text} [{suffix}]" if suffix else text


class AuthenticationError(APIError):
    """HTTP 401 / code 190 — the ``Authorization`` header is absent or malformed."""


class InvalidRequestError(APIError):
    """HTTP 400 — a required field is missing, malformed, or over a length cap.

    Also raised for an invalid (rotated or revoked) token, which the API
    reports as HTTP 400 with ``error.code`` 100.
    """


class ForbiddenError(APIError):
    """HTTP 403 / code 131005 — the other party is not the agent's creator."""


class NotFoundError(APIError):
    """HTTP 404."""


class MediaNotFoundError(NotFoundError):
    """The media id is unknown or expired."""


class MediaUploadError(InvalidRequestError):
    """Code 131053 — media over its size limit, or a MIME type that is not accepted."""


class RateLimitError(APIError):
    """HTTP 429 / code 130429 — back off exponentially."""

    retryable = True

    def __init__(self, *args: Any, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        #: Seconds from a ``Retry-After`` header, when the API supplied one.
        self.retry_after = retry_after


class NotDeliveredError(APIError):
    """HTTP 503 / code 131016 — not accepted for delivery, so nothing was sent.

    Safe to send again after a backoff.
    """

    retryable = True


class PollReplacedError(APIError):
    """HTTP 409 / code 1752041 — a newer poll for this agent replaced this one.

    Run only one :meth:`~whagent.Client.get_updates` call at a time per agent.
    """


class ServerError(APIError):
    """HTTP 5xx.

    For ``POST /agent/v1/messages`` a 500 leaves it unknown whether the message
    was sent, so this is not retried automatically unless the client was built
    with ``retry_send_on_server_error=True``.
    """

    retryable = True


#: ``error.code`` -> exception class.
_CODE_MAP: dict[int, type[APIError]] = {
    2: ServerError,
    100: InvalidRequestError,
    190: AuthenticationError,
    130429: RateLimitError,
    131005: ForbiddenError,
    131009: InvalidRequestError,
    131016: NotDeliveredError,
    131053: MediaUploadError,
    1752041: PollReplacedError,
}

#: HTTP status -> exception class, used when the code is unknown or missing.
_STATUS_MAP: dict[int, type[APIError]] = {
    400: InvalidRequestError,
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    409: PollReplacedError,
    429: RateLimitError,
}


def error_from_response(status: int, body: Any, headers: Any = None) -> APIError:
    """Build the right :class:`APIError` from an HTTP status and a parsed body."""
    error: dict[str, Any] = {}
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        error = body["error"]

    code = error.get("code")
    code = int(code) if isinstance(code, (int, str)) and str(code).lstrip("-").isdigit() else None
    message = error.get("message") or _fallback_message(status, body)
    error_data = error.get("error_data") if isinstance(error.get("error_data"), dict) else {}
    details = error_data.get("details")

    cls = _CODE_MAP.get(code) if code is not None else None
    if cls is None:
        cls = _STATUS_MAP.get(status) or (ServerError if status >= 500 else APIError)
    # Code 100 covers both "unknown media id" and "invalid token"; the 404 comes
    # only from fetching a media URL whose id is unknown or expired.
    if code == 100 and status == 404:
        cls = MediaNotFoundError

    kwargs: dict[str, Any] = dict(
        status=status,
        code=code,
        details=details,
        fbtrace_id=error.get("fbtrace_id"),
        error_type=error.get("type"),
        raw=body if isinstance(body, dict) else {"body": body},
    )
    if cls is RateLimitError:
        return RateLimitError(message, retry_after=_retry_after(headers), **kwargs)
    return cls(message, **kwargs)


def _fallback_message(status: int, body: Any) -> str:
    if isinstance(body, str) and body.strip():
        return f"HTTP {status}: {body.strip()[:200]}"
    return f"HTTP {status}"


def _retry_after(headers: Any) -> float | None:
    if not headers:
        return None
    try:
        value = headers.get("Retry-After")
    except AttributeError:
        return None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None
