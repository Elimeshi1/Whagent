"""A synchronous client for the WhatsApp Agent Platform API."""

from __future__ import annotations

import mimetypes
import os
import random
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import requests

from . import limits as _limits
from ._ratelimit import SlidingWindowLimiter
from .errors import (
    APIError,
    NotDeliveredError,
    PollReplacedError,
    RateLimitError,
    ServerError,
    TransportError,
    ValidationError,
    error_from_response,
)
from .models import Media, Message, SendResult, Update

__all__ = ["Client"]

#: Extensions the platform accepts that ``mimetypes`` may not know about.
_EXTRA_EXTENSIONS = {
    ".amr": "audio/amr",
    ".opus": "audio/opus",
    ".m4a": "audio/mp4",
    ".3gp": "video/3gpp",
    ".webp": "image/webp",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
}


class Client:
    """Talks to ``https://api.whatsapp.com/agent/v1``.

    ::

        with Client("<ACCESS_TOKEN>") as client:
            for update in client.poll_updates():
                for message in update.messages:
                    client.send_text(message.sender, f"You said: {message.text}")

    Args:
        token: The agent's API token, from WhatsApp → Settings → Agents →
            your agent's chat → Chat info → API key.  Treat it as a secret.
        base_url: Override the API base URL (useful for tests and proxies).
        timeout: Default read timeout in seconds for ordinary requests.  Polls
            extend it past the long-poll timeout automatically.
        max_retries: Retries after a retryable failure (429, 503/131016, and —
            where the outcome is knowable — 500 and network errors).
        rate_limit: Keep requests under the documented per-method caps by
            sleeping rather than letting the API return 429.
        retry_send_on_server_error: Retry ``POST /messages`` after a 500 or a
            dropped connection.  Off by default: those leave it unknown whether
            the message was sent, so a retry may deliver it twice.
        validate: Check lengths, recipients and media locally before sending.
        session: A pre-built :class:`requests.Session` (for connection reuse,
            proxies or custom TLS settings).
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = _limits.DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        backoff_max: float = 30.0,
        rate_limit: bool = True,
        retry_send_on_server_error: bool = False,
        validate: bool = True,
        session: requests.Session | None = None,
        user_agent: str | None = None,
    ) -> None:
        if not token or not isinstance(token, str):
            raise ValidationError("An API token is required.")

        from . import __version__

        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.validate = validate
        self.retry_send_on_server_error = retry_send_on_server_error
        self._session = session or requests.Session()
        self._owns_session = session is None
        self._user_agent = user_agent or f"whagent/{__version__}"
        self._limiter = SlidingWindowLimiter(_limits.RATE_LIMITS) if rate_limit else None

    # ------------------------------------------------------------------ #
    # Messages
    # ------------------------------------------------------------------ #

    def send_text(
        self,
        to: str,
        body: str,
        *,
        preview_url: bool = False,
        reply_to: str | None = None,
    ) -> SendResult:
        """Send a text message (max 4096 characters).

        Args:
            to: Recipient as ``user:<id>`` — the ``sender`` of an inbound
                message, passed back unchanged.
            body: The message text.
            preview_url: Render a link preview for the first URL in the body.
            reply_to: wamid of a message to quote.
        """
        if self.validate:
            _check_length("text.body", body, _limits.TEXT_BODY_MAX)
        payload: dict[str, Any] = {"body": body}
        if preview_url:
            payload["preview_url"] = True
        return self.send_message(to, "text", payload, reply_to=reply_to)

    def send_image(
        self,
        to: str,
        *,
        media_id: str | None = None,
        file: Any = None,
        mime_type: str | None = None,
        caption: str | None = None,
        reply_to: str | None = None,
    ) -> SendResult:
        """Send an image, from a media id or by uploading ``file`` first."""
        return self._send_media(
            to, "image", media_id=media_id, file=file, mime_type=mime_type,
            caption=caption, reply_to=reply_to,
        )

    def send_audio(
        self,
        to: str,
        *,
        media_id: str | None = None,
        file: Any = None,
        mime_type: str | None = None,
        reply_to: str | None = None,
    ) -> SendResult:
        """Send an audio file.  Audio is delivered as a plain attachment."""
        return self._send_media(
            to, "audio", media_id=media_id, file=file, mime_type=mime_type, reply_to=reply_to,
        )

    def send_video(
        self,
        to: str,
        *,
        media_id: str | None = None,
        file: Any = None,
        mime_type: str | None = None,
        caption: str | None = None,
        reply_to: str | None = None,
    ) -> SendResult:
        """Send a video (H.264 + AAC, ``+faststart``)."""
        return self._send_media(
            to, "video", media_id=media_id, file=file, mime_type=mime_type,
            caption=caption, reply_to=reply_to,
        )

    def send_document(
        self,
        to: str,
        *,
        media_id: str | None = None,
        file: Any = None,
        mime_type: str | None = None,
        filename: str | None = None,
        caption: str | None = None,
        reply_to: str | None = None,
    ) -> SendResult:
        """Send a document.

        ``filename`` defaults to the uploaded file's own name; set it
        explicitly when sending from a media id, so the recipient sees a name
        with the right extension.
        """
        return self._send_media(
            to, "document", media_id=media_id, file=file, mime_type=mime_type,
            caption=caption, filename=filename, reply_to=reply_to,
        )

    def send_sticker(
        self,
        to: str,
        *,
        media_id: str | None = None,
        file: Any = None,
        mime_type: str | None = None,
        reply_to: str | None = None,
    ) -> SendResult:
        """Send a WebP sticker (max 500 KB, canvas up to 4096 × 4096)."""
        return self._send_media(
            to, "sticker", media_id=media_id, file=file, mime_type=mime_type, reply_to=reply_to,
        )

    def send_message(
        self,
        to: str,
        type: str,
        payload: Mapping[str, Any],
        *,
        reply_to: str | None = None,
    ) -> SendResult:
        """Send any message type.

        The typed helpers above cover every sendable type; use this for a
        payload shape the platform adds later.
        """
        if self.validate:
            _check_recipient(to)
            if type == "reaction":
                raise ValidationError("Reactions are receive-only; they cannot be sent.")
            if type not in _limits.SENDABLE_TYPES:
                raise ValidationError(
                    f"Unsupported message type {type!r}. "
                    f"Sendable types: {', '.join(_limits.SENDABLE_TYPES)}."
                )

        body: dict[str, Any] = {
            "messaging_product": _limits.MESSAGING_PRODUCT,
            "to": to,
            "type": type,
            type: dict(payload),
        }
        if reply_to:
            body["context"] = {"message_id": reply_to}

        data = self._request(
            "POST",
            "/messages",
            rate_key="messages",
            json=body,
            retry_unknown=self.retry_send_on_server_error,
        )
        return SendResult.from_dict(data or {})

    def reply(self, message: Message, body: str, **kwargs: Any) -> SendResult:
        """Reply to an inbound message, quoting it."""
        kwargs.setdefault("reply_to", message.id)
        return self.send_text(message.sender, body, **kwargs)

    # ------------------------------------------------------------------ #
    # Updates
    # ------------------------------------------------------------------ #

    def get_updates(
        self,
        *,
        offset: int | None = None,
        limit: int = _limits.UPDATES_LIMIT_DEFAULT,
        timeout: int = _limits.UPDATES_TIMEOUT_DEFAULT,
    ) -> Update | None:
        """Long-poll for inbound messages and receipts.

        Returns ``None`` when the timeout elapsed with nothing to deliver
        (HTTP 204) — there is no ``next_offset`` then, so re-poll with the
        same ``offset``.

        Args:
            offset: Where to read from.  Omit it to start at the head as of
                the moment the request arrives (new traffic only — do this
                once, not in a loop), or pass ``0`` to replay the backlog.
                Otherwise pass the previous response's ``next_offset``.
            limit: Max entries to return (1–100).
            timeout: How long to hold the connection open (0–25 seconds).
        """
        params: dict[str, Any] = {
            "limit": _clamp(limit, 1, _limits.UPDATES_LIMIT_MAX),
            "timeout": _clamp(timeout, 0, _limits.UPDATES_TIMEOUT_MAX),
        }
        if offset is not None:
            params["offset"] = max(0, int(offset))

        data = self._request(
            "GET",
            "/updates",
            rate_key="updates",
            params=params,
            # Hold the socket open well past the server-side long-poll window,
            # so an ordinary delay never looks like a failure.
            read_timeout=params["timeout"] + max(self.timeout, 15.0),
        )
        return Update.from_dict(data) if data is not None else None

    def poll_updates(
        self,
        *,
        offset: int | None = None,
        limit: int = _limits.UPDATES_LIMIT_DEFAULT,
        timeout: int = _limits.UPDATES_TIMEOUT_DEFAULT,
        on_offset: Callable[[int], None] | None = None,
        max_polls: int | None = None,
        stop: Callable[[], bool] | None = None,
    ) -> Iterator[Update]:
        """Poll in a loop, tracking the offset, and yield non-empty updates.

        Empty polls (HTTP 204) are skipped, rate limits and server errors are
        backed off and retried with the same offset.  Run one poll loop at a
        time per agent — a second one makes the first fail with
        :class:`~whagent.errors.PollReplacedError`.

        Args:
            on_offset: Called with each new ``next_offset``, for persisting it.
            max_polls: Stop after this many polls (handy in tests).
            stop: Called before each poll; returning ``True`` ends the loop.
        """
        polls = 0
        failures = 0
        while max_polls is None or polls < max_polls:
            if stop is not None and stop():
                return
            polls += 1
            try:
                update = self.get_updates(offset=offset, limit=limit, timeout=timeout)
            except (RateLimitError, ServerError) as exc:
                # Reuse the prior offset and back off; nothing was consumed.
                failures += 1
                self._sleep_backoff(failures - 1, getattr(exc, "retry_after", None))
                continue
            failures = 0
            if update is None:
                continue  # 204: no next_offset, re-poll from the same offset.
            if update.next_offset is not None:
                offset = update.next_offset
                if on_offset is not None:
                    on_offset(update.next_offset)
            if update:
                yield update

    # ------------------------------------------------------------------ #
    # Read receipts and typing indicator
    # ------------------------------------------------------------------ #

    def mark_read(self, message_id: str, *, typing: bool = False) -> bool:
        """Mark an inbound message as read, optionally showing a typing indicator.

        Only messages the agent's creator sent to this agent can be marked.
        Show a typing indicator only when you are going to reply; it clears
        once you do, or after 25 seconds.
        """
        body: dict[str, Any] = {
            "messaging_product": _limits.MESSAGING_PRODUCT,
            "status": "read",
            "message_id": message_id,
        }
        if typing:
            body["typing_indicator"] = {"type": "text"}
        data = self._request("POST", "/statuses", rate_key="statuses", json=body)
        return bool((data or {}).get("success"))

    def send_typing(self, message_id: str) -> bool:
        """Show a typing indicator, marking ``message_id`` as read in the same call.

        Repeat it for a reply that takes longer than 25 seconds.
        """
        return self.mark_read(message_id, typing=True)

    # ------------------------------------------------------------------ #
    # Media
    # ------------------------------------------------------------------ #

    def upload_media(
        self,
        file: Any,
        *,
        mime_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        """Upload media and return its id, for use in an outbound message.

        Args:
            file: A path, raw ``bytes``, or an open binary file object.
            mime_type: Declared MIME type.  Guessed from the filename when
                omitted.
            filename: Name for the upload part; taken from the path when
                ``file`` is one.

        Media expires 30 days after it is stored.
        """
        content, guessed_name = _read_file(file)
        filename = filename or guessed_name or "upload"
        mime_type = mime_type or _guess_mime(filename)

        if not mime_type:
            raise ValidationError(
                f"Could not determine a MIME type for {filename!r}. "
                "Pass mime_type explicitly (for example mime_type='application/pdf')."
            )
        if self.validate:
            _check_media(mime_type, len(content))

        data = self._request(
            "POST",
            "/media",
            rate_key="media:post",
            data={"messaging_product": _limits.MESSAGING_PRODUCT, "type": mime_type},
            files={"file": (filename, content, mime_type)},
        )
        media_id = (data or {}).get("id", "")
        if not media_id:
            raise APIError("Upload succeeded but the response carried no media id.", raw=data or {})
        return media_id

    def get_media(self, media_id: str) -> Media:
        """Fetch metadata (URL, MIME type, hex SHA-256, size) for a media object."""
        data = self._request("GET", f"/media/{media_id}", rate_key="media:get")
        return Media.from_dict(data or {})

    def download_media(self, media_id: str, dest: Any = None, *, chunk_size: int = 64 * 1024) -> Any:
        """Download the bytes behind a media id.

        Returns the bytes, or — when ``dest`` is a path or a writable binary
        file object — writes to it and returns the destination.
        """
        media = self.get_media(media_id)
        if not media.url:
            raise APIError(f"No download URL for media {media_id!r}.", raw=media.raw)
        return self.download_url(media.url, dest, chunk_size=chunk_size)

    def download_url(self, url: str, dest: Any = None, *, chunk_size: int = 64 * 1024) -> Any:
        """Download a media URL from :meth:`get_media`, authenticated as the agent."""
        response = self._send("GET", url, stream=True, read_timeout=self.timeout)
        if response.status_code >= 400:
            raise error_from_response(response.status_code, _parse_body(response), response.headers)

        if dest is None:
            return response.content

        if hasattr(dest, "write"):
            for chunk in response.iter_content(chunk_size):
                dest.write(chunk)
            return dest

        path = Path(dest)
        with open(path, "wb") as handle:
            for chunk in response.iter_content(chunk_size):
                handle.write(chunk)
        return path

    def delete_media(self, media_id: str) -> bool:
        """Delete a media object you uploaded, or one that was sent to you."""
        data = self._request("DELETE", f"/media/{media_id}", rate_key="media:delete")
        return bool((data or {}).get("success"))

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Close the underlying HTTP session, if this client created it."""
        if self._owns_session:
            self._session.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} base_url={self.base_url!r}>"

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _send_media(
        self,
        to: str,
        type: str,
        *,
        media_id: str | None,
        file: Any,
        mime_type: str | None,
        caption: str | None = None,
        filename: str | None = None,
        reply_to: str | None = None,
    ) -> SendResult:
        if (media_id is None) == (file is None):
            raise ValidationError(
                f"send_{type}() needs exactly one of media_id= or file=."
            )
        if file is not None:
            if type == "document" and filename is None:
                _, guessed = _read_file(file, peek=True)
                filename = guessed
            media_id = self.upload_media(file, mime_type=mime_type)

        payload: dict[str, Any] = {"id": media_id}
        if caption is not None:
            if self.validate:
                if type not in _limits.CAPTIONABLE_TYPES:
                    raise ValidationError(
                        f"A caption is not available on {type}; it is accepted on "
                        f"{', '.join(_limits.CAPTIONABLE_TYPES)}."
                    )
                _check_length(f"{type}.caption", caption, _limits.CAPTION_MAX)
            payload["caption"] = caption
        if filename is not None:
            payload["filename"] = filename
        return self.send_message(to, type, payload, reply_to=reply_to)

    def _request(
        self,
        method: str,
        path: str,
        *,
        rate_key: str,
        retry_unknown: bool = True,
        read_timeout: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Perform an API call with rate limiting and retries.

        Returns the parsed JSON body, or ``None`` for a 204.
        """
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            if self._limiter is not None:
                self._limiter.acquire(rate_key)
            try:
                response = self._send(method, url, read_timeout=read_timeout, **kwargs)
            except TransportError:
                # A dropped connection leaves a send in an unknown state.
                if not retry_unknown or attempt >= self.max_retries:
                    raise
                self._sleep_backoff(attempt)
                attempt += 1
                continue

            if response.status_code == 204:
                return None
            if response.status_code < 400:
                body = _parse_body(response)
                return body if isinstance(body, dict) else {}

            error = error_from_response(response.status_code, _parse_body(response), response.headers)
            unknown_outcome = isinstance(error, ServerError)
            retryable = error.retryable and (retry_unknown or not unknown_outcome)
            if not retryable or attempt >= self.max_retries:
                raise error
            self._sleep_backoff(attempt, getattr(error, "retry_after", None))
            attempt += 1

    def _send(self, method: str, url: str, *, read_timeout: float | None = None, **kwargs: Any) -> Any:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        headers.update(kwargs.pop("headers", None) or {})
        try:
            return self._session.request(
                method,
                url,
                headers=headers,
                timeout=(10.0, read_timeout or self.timeout),
                **kwargs,
            )
        except requests.RequestException as exc:  # pragma: no cover - network dependent
            raise TransportError(f"{method} {url} failed: {exc}") from exc

    def _sleep_backoff(self, attempt: int, retry_after: float | None = None) -> None:
        if retry_after is not None:
            delay = min(retry_after, self.backoff_max)
        else:
            delay = min(self.backoff_max, self.backoff_base * (2 ** attempt))
            delay += random.uniform(0, delay * 0.1)  # jitter, to spread retries out
        time.sleep(delay)


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _check_recipient(to: Any) -> None:
    if not isinstance(to, str) or not to:
        raise ValidationError("'to' is required and must be a 'user:<id>' identifier.")
    if not to.startswith("user:") or to == "user:":
        raise ValidationError(
            f"'to' must be a WhatsApp user identifier of the form 'user:<id>', got {to!r}. "
            "Use the 'sender' of an inbound message, unchanged."
        )


def _check_length(field: str, value: Any, maximum: int) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string, got {type(value).__name__}.")
    if len(value) > maximum:
        raise ValidationError(
            f"{field} is {len(value)} characters; the limit is {maximum}. Truncate before sending."
        )


def _check_media(mime_type: str, size: int) -> None:
    limit = _limits.size_limit_for(mime_type)
    if limit is None:
        raise ValidationError(
            f"MIME type {mime_type!r} is not accepted for upload. "
            "See whagent.limits.ACCEPTED_MIME_TYPES."
        )
    if size > limit:
        category = _limits.category_for(mime_type)
        raise ValidationError(
            f"File is {size} bytes; the limit for {category} ({mime_type}) is {limit} bytes."
        )
    if size == 0:
        raise ValidationError("Refusing to upload an empty file.")


def _guess_mime(filename: str | None) -> str | None:
    if not filename:
        return None
    suffix = Path(filename).suffix.lower()
    if suffix in _EXTRA_EXTENSIONS:
        return _EXTRA_EXTENSIONS[suffix]
    guessed, _ = mimetypes.guess_type(filename)
    return guessed


def _read_file(file: Any, *, peek: bool = False) -> tuple[bytes, str | None]:
    """Return ``(content, filename)`` for a path, bytes, or binary file object.

    With ``peek=True`` only the filename is resolved; the content comes back
    empty and a file object is left unread.
    """
    if isinstance(file, (str, os.PathLike)):
        path = Path(file)
        if peek:
            return b"", path.name
        try:
            return path.read_bytes(), path.name
        except OSError as exc:
            raise ValidationError(f"Could not read {path}: {exc}") from exc
    if isinstance(file, (bytes, bytearray)):
        return bytes(file), None
    if hasattr(file, "read"):
        name = getattr(file, "name", None)
        name = Path(name).name if isinstance(name, str) else None
        if peek:
            return b"", name
        content = file.read()
        if isinstance(content, str):
            raise ValidationError("Open media files in binary mode ('rb').")
        return content, name
    raise ValidationError(
        f"Unsupported file input {type(file).__name__}; pass a path, bytes, or an open binary file."
    )


def _parse_body(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return getattr(response, "text", "")
