"""Typed views over the JSON the API returns.

Every model keeps the payload it was parsed from in ``raw``, so fields added
to the platform later are still reachable without a library upgrade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

__all__ = [
    "Contact",
    "MessageContext",
    "InboundMedia",
    "Reaction",
    "Message",
    "Status",
    "Update",
    "SendResult",
    "Media",
    "participant_type",
    "is_user",
]


def participant_type(identifier: str) -> str | None:
    """``"user"`` or ``"agent"`` for a ``<type>:<id>`` participant identifier.

    Returns ``None`` when the string has no recognizable prefix.  Identifiers
    are opaque: compare them in full and never show them to a WhatsApp user.
    """
    prefix, sep, rest = (identifier or "").partition(":")
    if not sep or not rest:
        return None
    return prefix if prefix in ("user", "agent") else None


def is_user(identifier: str) -> bool:
    """``True`` when the identifier names a WhatsApp user rather than an agent."""
    return participant_type(identifier) == "user"


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dt(timestamp: str | None) -> datetime | None:
    seconds = _as_int(timestamp)
    if seconds is None:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


@dataclass(frozen=True)
class Contact:
    """The other party in a conversation, from an update or a send response."""

    wa_id: str
    name: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Contact":
        profile = data.get("profile")
        name = profile.get("name") if isinstance(profile, dict) else None
        return cls(wa_id=data.get("wa_id", ""), name=name, raw=data)


@dataclass(frozen=True)
class MessageContext:
    """The message an inbound message quotes."""

    message_id: str
    sender: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def from_agent(self) -> bool:
        """``True`` when the quoted message was written by an agent."""
        return participant_type(self.sender) == "agent"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageContext":
        # Inbound context uses "id"; the send request uses "message_id".
        return cls(
            message_id=data.get("id") or data.get("message_id", ""),
            sender=data.get("from", ""),
            raw=data,
        )


@dataclass(frozen=True)
class InboundMedia:
    """The media payload of an inbound image/audio/video/document/sticker."""

    id: str
    mime_type: str | None = None
    #: Base64 of the SHA-256 digest.  ``GET /media/<id>`` reports the same
    #: digest as hex — see :attr:`Media.sha256`.
    sha256: str | None = None
    caption: str | None = None
    filename: str | None = None
    #: ``True`` on a voice note (audio recorded in the chat).
    voice: bool = False
    #: Always ``False`` on stickers you receive.
    animated: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InboundMedia":
        return cls(
            id=data.get("id", ""),
            mime_type=data.get("mime_type"),
            sha256=data.get("sha256"),
            caption=data.get("caption"),
            filename=data.get("filename"),
            voice=bool(data.get("voice", False)),
            animated=bool(data.get("animated", False)),
            raw=data,
        )


@dataclass(frozen=True)
class Reaction:
    """An inbound reaction.  Reactions are receive-only."""

    message_id: str
    emoji: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def removed(self) -> bool:
        """``True`` when the reaction was taken back (an empty emoji)."""
        return not self.emoji

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Reaction":
        return cls(
            message_id=data.get("message_id", ""),
            emoji=data.get("emoji", ""),
            raw=data,
        )


@dataclass(frozen=True)
class Message:
    """An inbound message."""

    id: str
    #: Sender, as ``user:<id>``.  Send it back as ``to`` unchanged.
    sender: str
    type: str
    timestamp: str | None = None
    #: Body of a text message, ``None`` for every other type.
    text: str | None = None
    media: InboundMedia | None = None
    reaction: Reaction | None = None
    context: MessageContext | None = None
    #: Profile name of the sender, when the update carried one.
    profile_name: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def caption(self) -> str | None:
        """Caption on an image, video or document."""
        return self.media.caption if self.media else None

    @property
    def media_id(self) -> str | None:
        """Handle to pass to :meth:`~whagent.Client.download_media`."""
        return self.media.id if self.media else None

    @property
    def datetime(self) -> datetime | None:
        """:attr:`timestamp` as an aware UTC datetime."""
        return _dt(self.timestamp)

    @property
    def is_media(self) -> bool:
        return self.media is not None

    @property
    def is_reply(self) -> bool:
        """``True`` when this message quotes an earlier one."""
        return self.context is not None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, profile_name: str | None = None) -> "Message":
        msg_type = data.get("type", "")
        payload = data.get(msg_type) if isinstance(data.get(msg_type), dict) else None
        context = data.get("context")
        return cls(
            id=data.get("id", ""),
            sender=data.get("from", ""),
            type=msg_type,
            timestamp=data.get("timestamp"),
            text=(payload or {}).get("body") if msg_type == "text" else None,
            media=InboundMedia.from_dict(payload) if payload and msg_type in (
                "image", "audio", "video", "document", "sticker"
            ) else None,
            reaction=Reaction.from_dict(payload) if payload and msg_type == "reaction" else None,
            context=MessageContext.from_dict(context) if isinstance(context, dict) else None,
            profile_name=profile_name,
            raw=data,
        )


@dataclass(frozen=True)
class Status:
    """A delivery or read receipt for a message your agent sent."""

    id: str
    #: ``"delivered"`` or ``"read"``.
    status: str
    recipient_id: str
    timestamp: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def datetime(self) -> datetime | None:
        return _dt(self.timestamp)

    @property
    def delivered(self) -> bool:
        return self.status == "delivered"

    @property
    def read(self) -> bool:
        return self.status == "read"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Status":
        return cls(
            id=data.get("id", ""),
            status=data.get("status", ""),
            recipient_id=data.get("recipient_id", ""),
            timestamp=data.get("timestamp"),
            raw=data,
        )


@dataclass(frozen=True)
class Update:
    """One response from ``GET /agent/v1/updates``.

    Messages and statuses share a single per-agent sequence, so one update can
    carry both and a single :attr:`next_offset` advances past all of it.
    """

    messages: list[Message] = field(default_factory=list)
    statuses: list[Status] = field(default_factory=list)
    contacts: list[Contact] = field(default_factory=list)
    #: Pass back as ``offset`` on the next poll, unchanged.
    next_offset: int | None = None
    #: Your agent's numeric id.
    agent_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __bool__(self) -> bool:
        return bool(self.messages or self.statuses)

    def __iter__(self) -> Iterator[Message]:
        return iter(self.messages)

    def profile_name(self, wa_id: str) -> str | None:
        """Profile name for a participant, when this update carried one."""
        for contact in self.contacts:
            if contact.wa_id == wa_id and contact.name:
                return contact.name
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Update":
        entries = data.get("entry") or []
        entry = entries[0] if entries and isinstance(entries[0], dict) else {}
        changes = entry.get("changes") or []
        change = changes[0] if changes and isinstance(changes[0], dict) else {}
        value = change.get("value") if isinstance(change.get("value"), dict) else {}

        contacts = [Contact.from_dict(c) for c in value.get("contacts") or [] if isinstance(c, dict)]
        names = {c.wa_id: c.name for c in contacts if c.name}
        messages = [
            Message.from_dict(m, profile_name=names.get(m.get("from", "")))
            for m in value.get("messages") or []
            if isinstance(m, dict)
        ]
        statuses = [Status.from_dict(s) for s in value.get("statuses") or [] if isinstance(s, dict)]
        return cls(
            messages=messages,
            statuses=statuses,
            contacts=contacts,
            next_offset=_as_int(data.get("next_offset")),
            agent_id=entry.get("id"),
            raw=data,
        )


@dataclass(frozen=True)
class SendResult:
    """The response to ``POST /agent/v1/messages``."""

    #: Server-assigned message id, in wamid format.
    message_id: str
    #: The WhatsApp user the message was routed to, as ``user:<id>``.
    wa_id: str = ""
    #: The ``to`` value echoed back exactly as supplied.
    input: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __str__(self) -> str:
        return self.message_id

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SendResult":
        messages = data.get("messages") or [{}]
        contacts = data.get("contacts") or [{}]
        message = messages[0] if isinstance(messages[0], dict) else {}
        contact = contacts[0] if isinstance(contacts[0], dict) else {}
        return cls(
            message_id=message.get("id", ""),
            wa_id=contact.get("wa_id", ""),
            input=contact.get("input", ""),
            raw=data,
        )


@dataclass(frozen=True)
class Media:
    """Metadata from ``GET /agent/v1/media/<MEDIA_ID>``."""

    id: str
    #: URL for the stored bytes.  Fetch it with the API token in the
    #: ``Authorization`` header — :meth:`~whagent.Client.download_media` does this.
    url: str = ""
    mime_type: str | None = None
    #: SHA-256 digest as hex.  Inbound payloads carry Base64 of the same digest.
    sha256: str | None = None
    file_size: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Media":
        return cls(
            id=data.get("id", ""),
            url=data.get("url", ""),
            mime_type=data.get("mime_type"),
            sha256=data.get("sha256"),
            file_size=_as_int(data.get("file_size")),
            raw=data,
        )
