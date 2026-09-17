"""whagent — a small Python library for the WhatsApp Agent Platform.

Two layers, use whichever fits:

* :class:`Client` — one method per endpoint of
  ``https://api.whatsapp.com/agent/v1``, with typed responses, local
  validation, retries and client-side rate limiting.
* :class:`Agent` — a polling loop with handler registration on top of it.

::

    from whagent import Agent

    agent = Agent("<ACCESS_TOKEN>")

    @agent.on_text
    def echo(ctx):
        ctx.reply(f"You said: {ctx.text}")

    agent.run()

Implements version 1 of the WhatsApp Agent Platform Developer Manual
(August 25, 2026).
"""

from __future__ import annotations

__version__ = "0.1.0"

from .agent import Agent, Context, FileOffsetStore
from .client import Client
from .errors import (
    APIError,
    AuthenticationError,
    ForbiddenError,
    InvalidRequestError,
    MediaNotFoundError,
    MediaUploadError,
    NotDeliveredError,
    NotFoundError,
    PollReplacedError,
    RateLimitError,
    ServerError,
    TransportError,
    ValidationError,
    WhagentError,
)
from .limits import (
    ACCEPTED_MIME_TYPES,
    CAPTION_MAX,
    DEFAULT_BASE_URL,
    RATE_LIMITS,
    RECEIVABLE_TYPES,
    SENDABLE_TYPES,
    SIZE_LIMITS,
    TEXT_BODY_MAX,
)
from .models import (
    Contact,
    InboundMedia,
    Media,
    Message,
    MessageContext,
    Reaction,
    SendResult,
    Status,
    Update,
    is_user,
    participant_type,
)

__all__ = [
    "__version__",
    # Entry points
    "Agent",
    "Client",
    "Context",
    "FileOffsetStore",
    # Models
    "Contact",
    "InboundMedia",
    "Media",
    "Message",
    "MessageContext",
    "Reaction",
    "SendResult",
    "Status",
    "Update",
    "is_user",
    "participant_type",
    # Errors
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
    # Constants
    "ACCEPTED_MIME_TYPES",
    "CAPTION_MAX",
    "DEFAULT_BASE_URL",
    "RATE_LIMITS",
    "RECEIVABLE_TYPES",
    "SENDABLE_TYPES",
    "SIZE_LIMITS",
    "TEXT_BODY_MAX",
]
