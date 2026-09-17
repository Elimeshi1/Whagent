"""A small handler-based layer on top of :class:`whagent.Client`.

Register handlers, call :meth:`Agent.run`, and the agent polls for updates,
marks messages read, shows a typing indicator and dispatches each message::

    from whagent import Agent

    agent = Agent("<ACCESS_TOKEN>")

    @agent.on_text
    def echo(ctx):
        ctx.reply(f"You said: {ctx.text}")

    agent.run()
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Pattern

from . import limits as _limits
from .client import Client
from .errors import APIError, ValidationError
from .models import Message, SendResult, Update

__all__ = ["Agent", "Context", "FileOffsetStore"]

logger = logging.getLogger("whagent")

#: How many handled message ids to remember, so a replayed offset is not
#: answered twice.
_SEEN_CAPACITY = 5000


@dataclass
class Context:
    """What a message handler is given: the message, plus ways to respond."""

    client: Client
    message: Message
    update: Update

    # -- shortcuts onto the message ------------------------------------ #

    @property
    def sender(self) -> str:
        """The WhatsApp user who wrote the message, as ``user:<id>``."""
        return self.message.sender

    @property
    def text(self) -> str | None:
        """Body of a text message, or the caption of a media message."""
        return self.message.text if self.message.type == "text" else self.message.caption

    @property
    def type(self) -> str:
        return self.message.type

    @property
    def profile_name(self) -> str | None:
        """The sender's profile name, when the platform has supplied one."""
        return self.message.profile_name or self.update.profile_name(self.message.sender)

    # -- responding ----------------------------------------------------- #

    def reply(self, body: str, *, quote: bool = False, **kwargs: Any) -> SendResult:
        """Send a text message back to the sender."""
        return self.client.send_text(self.sender, body, **self._with_quote(quote, kwargs))

    def reply_image(self, **kwargs: Any) -> SendResult:
        """Send an image back — ``file=`` a path/bytes, or ``media_id=``."""
        return self.client.send_image(self.sender, **self._with_quote(kwargs.pop("quote", False), kwargs))

    def reply_audio(self, **kwargs: Any) -> SendResult:
        return self.client.send_audio(self.sender, **self._with_quote(kwargs.pop("quote", False), kwargs))

    def reply_video(self, **kwargs: Any) -> SendResult:
        return self.client.send_video(self.sender, **self._with_quote(kwargs.pop("quote", False), kwargs))

    def reply_document(self, **kwargs: Any) -> SendResult:
        return self.client.send_document(self.sender, **self._with_quote(kwargs.pop("quote", False), kwargs))

    def reply_sticker(self, **kwargs: Any) -> SendResult:
        return self.client.send_sticker(self.sender, **self._with_quote(kwargs.pop("quote", False), kwargs))

    def mark_read(self, *, typing: bool = False) -> bool:
        """Mark this message as read, optionally with a typing indicator."""
        return self.client.mark_read(self.message.id, typing=typing)

    def typing(self) -> bool:
        """Refresh the typing indicator (it clears after 25 seconds)."""
        return self.client.send_typing(self.message.id)

    def download(self, dest: Any = None) -> Any:
        """Download this message's media, to ``dest`` or into memory."""
        if not self.message.media_id:
            raise ValidationError(f"A {self.message.type} message carries no media to download.")
        return self.client.download_media(self.message.media_id, dest)

    def _with_quote(self, quote: bool, kwargs: dict[str, Any]) -> dict[str, Any]:
        if quote:
            kwargs.setdefault("reply_to", self.message.id)
        return kwargs


class FileOffsetStore:
    """Persists the poll offset in a file, so a restart resumes where it left off."""

    def __init__(self, path: Any) -> None:
        self.path = Path(path)

    def load(self) -> int | None:
        try:
            return int(self.path.read_text().strip())
        except (OSError, ValueError):
            return None

    def save(self, offset: int) -> None:
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_text(str(offset))
        temp.replace(self.path)


class Agent:
    """Polls for updates and dispatches them to the handlers you register.

    Args:
        token: The agent's API token.  Omit it when passing ``client``.
        client: An existing :class:`~whagent.Client`.
        mark_read: Mark each dispatched message as read.
        typing: Show a typing indicator while a handler runs.  Implies
            ``mark_read``, since both travel in the same call.
        start: Where the first poll begins when no offset is stored —
            ``"new"`` for traffic that arrives from now on, or ``"beginning"``
            to replay up to 30 days of backlog.
        offset_store: Object with ``load()`` and ``save(offset)``, e.g.
            :class:`FileOffsetStore`, to survive restarts.
        skip_own_replays: Ignore a message id that was already handled in this
            process.
        Remaining keyword arguments are passed to :class:`~whagent.Client`.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        client: Client | None = None,
        mark_read: bool = True,
        typing: bool = True,
        start: str | int = "new",
        offset_store: Any = None,
        skip_own_replays: bool = True,
        **client_kwargs: Any,
    ) -> None:
        if (client is None) == (token is None):
            raise ValidationError("Pass either a token or client=, not both.")
        self.client = client or Client(token, **client_kwargs)  # type: ignore[arg-type]
        self.mark_read = mark_read or typing
        self.typing = typing
        self.start = start
        self.offset_store = offset_store
        self.skip_own_replays = skip_own_replays

        self._message_handlers: list[tuple[frozenset[str] | None, Pattern[str] | None, Callable]] = []
        self._status_handlers: list[Callable] = []
        self._update_handlers: list[Callable] = []
        self._error_handlers: list[Callable] = []
        self._seen: dict[str, None] = {}

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def on_message(
        self,
        types: str | Iterable[str] | Callable | None = None,
        *,
        pattern: str | Pattern[str] | None = None,
    ) -> Callable:
        """Register a handler for inbound messages.

        Usable bare (``@agent.on_message``) or with a filter
        (``@agent.on_message("image")``, ``@agent.on_message(pattern=r"^/help")``).
        """
        if callable(types) and not isinstance(types, str):
            return self._add_message_handler(types, None, None)

        selected = self._normalize_types(types)
        compiled = re.compile(pattern, re.IGNORECASE) if isinstance(pattern, str) else pattern

        def decorator(func: Callable) -> Callable:
            return self._add_message_handler(func, selected, compiled)

        return decorator

    def on_text(self, pattern: str | Pattern[str] | Callable | None = None) -> Callable:
        """Register a handler for text messages, optionally matching a regex.

        ``@agent.on_text`` takes every text message; ``@agent.on_text(r"^/start")``
        takes the ones whose body matches (searched, case-insensitive).
        """
        if callable(pattern) and not isinstance(pattern, (str, re.Pattern)):
            return self._add_message_handler(pattern, frozenset({"text"}), None)
        compiled = re.compile(pattern, re.IGNORECASE) if isinstance(pattern, str) else pattern

        def decorator(func: Callable) -> Callable:
            return self._add_message_handler(func, frozenset({"text"}), compiled)

        return decorator

    def on_media(self, func: Callable) -> Callable:
        """Register a handler for every media message type."""
        return self._add_message_handler(func, frozenset(_limits.MEDIA_TYPES), None)

    def on_reaction(self, func: Callable) -> Callable:
        """Register a handler for reactions (receive-only)."""
        return self._add_message_handler(func, frozenset({"reaction"}), None)

    def on_status(self, func: Callable) -> Callable:
        """Register a handler for delivery and read receipts: ``f(status)``."""
        self._status_handlers.append(func)
        return func

    def on_update(self, func: Callable) -> Callable:
        """Register a handler that sees each raw :class:`~whagent.models.Update`."""
        self._update_handlers.append(func)
        return func

    def on_error(self, func: Callable) -> Callable:
        """Register an error handler: ``f(exception, context_or_None)``.

        Without one, handler exceptions are logged and the loop continues.
        """
        self._error_handlers.append(func)
        return func

    # ------------------------------------------------------------------ #
    # Running
    # ------------------------------------------------------------------ #

    def run(
        self,
        *,
        offset: int | None = None,
        limit: int = _limits.UPDATES_LIMIT_DEFAULT,
        timeout: int = _limits.UPDATES_TIMEOUT_DEFAULT,
        max_polls: int | None = None,
        stop: Callable[[], bool] | None = None,
    ) -> None:
        """Poll and dispatch until interrupted.

        Run one agent at a time per API token: a second poller makes the first
        fail with :class:`~whagent.errors.PollReplacedError`.
        """
        start_offset = self._resolve_offset(offset)
        logger.info("whagent: polling from offset %s", "head" if start_offset is None else start_offset)
        try:
            for update in self.client.poll_updates(
                offset=start_offset,
                limit=limit,
                timeout=timeout,
                on_offset=self._save_offset,
                max_polls=max_polls,
                stop=stop,
            ):
                self.dispatch(update)
        except KeyboardInterrupt:  # pragma: no cover - interactive
            logger.info("whagent: stopped")

    def dispatch(self, update: Update) -> None:
        """Route one update to the registered handlers."""
        for handler in self._update_handlers:
            self._call(handler, (update,), None)

        for status in update.statuses:
            for handler in self._status_handlers:
                self._call(handler, (status,), None)

        for message in update.messages:
            if self.skip_own_replays and self._already_seen(message.id):
                continue
            handlers = [h for types, pattern, h in self._message_handlers
                        if self._matches(message, types, pattern)]
            if not handlers:
                continue
            context = Context(client=self.client, message=message, update=update)
            self._acknowledge(message)
            for handler in handlers:
                self._call(handler, (context,), context)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _add_message_handler(
        self,
        func: Callable,
        types: frozenset[str] | None,
        pattern: Pattern[str] | None,
    ) -> Callable:
        self._message_handlers.append((types, pattern, func))
        return func

    @staticmethod
    def _normalize_types(types: str | Iterable[str] | None) -> frozenset[str] | None:
        if types is None:
            return None
        names = frozenset({types} if isinstance(types, str) else types)
        unknown = names - set(_limits.RECEIVABLE_TYPES)
        if unknown:
            raise ValidationError(
                f"Unknown message type(s): {', '.join(sorted(unknown))}. "
                f"Receivable types: {', '.join(_limits.RECEIVABLE_TYPES)}."
            )
        return names

    @staticmethod
    def _matches(message: Message, types: frozenset[str] | None, pattern: Pattern[str] | None) -> bool:
        if types is not None and message.type not in types:
            return False
        if pattern is not None:
            body = message.text if message.type == "text" else message.caption
            if not body or not pattern.search(body):
                return False
        return True

    def _already_seen(self, message_id: str) -> bool:
        if not message_id:
            return False
        if message_id in self._seen:
            return True
        self._seen[message_id] = None
        while len(self._seen) > _SEEN_CAPACITY:
            self._seen.pop(next(iter(self._seen)))
        return False

    def _acknowledge(self, message: Message) -> None:
        if not self.mark_read:
            return
        try:
            self.client.mark_read(message.id, typing=self.typing)
        except APIError as exc:
            # Not fatal: only the creator's messages can be marked read, and
            # the platform may decline a receipt with a 503.
            logger.warning("whagent: could not mark %s as read: %s", message.id, exc)

    def _call(self, handler: Callable, args: tuple, context: Context | None) -> None:
        try:
            handler(*args)
        except Exception as exc:  # noqa: BLE001 - a handler must not kill the loop
            if self._error_handlers:
                for error_handler in self._error_handlers:
                    try:
                        error_handler(exc, context)
                    except Exception:  # noqa: BLE001
                        logger.exception("whagent: error handler failed")
            else:
                logger.exception("whagent: handler %s failed", getattr(handler, "__name__", handler))

    def _resolve_offset(self, offset: int | None) -> int | None:
        if offset is not None:
            return offset
        if self.offset_store is not None:
            stored = self.offset_store.load()
            if stored is not None:
                return int(stored)
        if isinstance(self.start, int):
            return self.start
        if self.start == "beginning":
            return 0
        if self.start == "new":
            return None
        raise ValidationError(f"start must be 'new', 'beginning' or an integer offset, got {self.start!r}.")

    def _save_offset(self, offset: int) -> None:
        if self.offset_store is not None:
            try:
                self.offset_store.save(offset)
            except Exception:  # noqa: BLE001
                logger.exception("whagent: could not persist offset %s", offset)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "Agent":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
