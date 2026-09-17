# Models

Every response is parsed into a frozen dataclass. Each one keeps the JSON it came from in `.raw`, so a field the platform adds later is reachable without a library upgrade.

```python
from whagent import Message, Status, Update, Media, SendResult, Contact
```

## Update

One response from `GET /updates`. See [Receiving messages](receiving.md).

| Attribute | Type | |
|---|---|---|
| `messages` | `list[Message]` | Inbound messages; always present, may be empty |
| `statuses` | `list[Status]` | Receipts for messages you sent |
| `contacts` | `list[Contact]` | At most one entry per user |
| `next_offset` | `int \| None` | Pass as `offset` on the next poll, unchanged |
| `agent_id` | `str \| None` | Your agent's numeric id |
| `raw` | `dict` | |

| Method | |
|---|---|
| `bool(update)` | `True` when it carries any messages or statuses |
| `for message in update` | iterates `messages` |
| `update.profile_name(wa_id)` | that participant's display name, when this update had one |

## Message

| Attribute | Type | |
|---|---|---|
| `id` | `str` | wamid — quote it, mark it read, deduplicate on it |
| `sender` | `str` | `user:<id>`; send back as a recipient unchanged |
| `type` | `str` | `text`, `image`, `audio`, `video`, `document`, `sticker`, `reaction` |
| `timestamp` | `str \| None` | Unix seconds, as the platform sends it |
| `datetime` | `datetime \| None` | the same, as an aware UTC datetime |
| `text` | `str \| None` | body of a text message; `None` for every other type |
| `caption` | `str \| None` | caption of an image, video or document |
| `media` | `InboundMedia \| None` | |
| `media_id` | `str \| None` | shortcut for `media.id` |
| `reaction` | `Reaction \| None` | |
| `context` | `MessageContext \| None` | the quoted message, when there is one |
| `profile_name` | `str \| None` | sender's display name, when the update carried one |
| `is_media`, `is_reply` | `bool` | |

### InboundMedia

`id`, `mime_type`, `sha256` (**Base64** of the digest), `caption`, `filename` (documents), `voice` (`True` on a voice note), `animated` (always `False` on stickers you receive).

### Reaction

`message_id` (the wamid being reacted to), `emoji`, and `removed` — `True` when the emoji is empty, meaning the reaction was taken back. Reactions are receive-only.

### MessageContext

`message_id` (wamid of the quoted message), `sender` (its author), and `from_agent` — `True` when your agent wrote the quoted message, `False` when the user did.

> The inbound field is `context.id`, while a send uses `context.message_id`. The model normalizes both to `message_id`.

## Status

A delivery or read receipt for a message **your agent sent**.

| Attribute | |
|---|---|
| `id` | wamid of the outbound message |
| `status` | `"delivered"` or `"read"` |
| `recipient_id` | `user:<id>` |
| `timestamp`, `datetime` | |
| `delivered`, `read` | `bool` shortcuts |

## Contact

`wa_id` (`user:<id>`) and `name` — the profile name, present only when the user has set one. See [profile names](receiving.md#profile-names).

## SendResult

Returned by every send.

| Attribute | |
|---|---|
| `message_id` | server-assigned wamid — record it; receipts refer to it |
| `wa_id` | the user the message was routed to |
| `input` | the `to` value echoed back |

`str(result)` is the message id.

## Media

Metadata from `GET /media/<id>`. See [Files and media](media.md).

| Attribute | |
|---|---|
| `id` | |
| `url` | fetch it with your token in the `Authorization` header |
| `mime_type` | |
| `sha256` | **hex** digest (inbound payloads carry Base64 of the same digest) |
| `file_size` | bytes |

## Identifier helpers

```python
from whagent import participant_type, is_user

participant_type("user:509...")   # "user"
participant_type("agent:123")     # "agent"
participant_type("509...")        # None
is_user(message.sender)           # True
```

See [How it works → participant identifiers](concepts.md#identifiers-name-accounts-and-accounts-change) for why they should never be used as a primary key.

## Unknown types

A message type the library doesn't know still parses: `type` is whatever the platform sent, `text` and `media` are `None`, and the payload is in `.raw`.

```python
@agent.on_update
def peek(update):
    for message in update.raw["entry"][0]["changes"][0]["value"]["messages"]:
        ...
```
