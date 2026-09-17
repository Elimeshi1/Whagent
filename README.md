# whagent

A small Python library for the [WhatsApp Agent Platform](https://www.whatsapp.com/developer/WhatsApp-Agent-Platform-Developer-Manual.pdf) API (`https://api.whatsapp.com/agent/v1`).

It covers every endpoint in version 1 of the developer manual — sending, long-poll receiving, read receipts, the typing indicator and media — and adds the things you would otherwise write yourself: typed responses, offset tracking, retries with backoff, client-side rate limiting and local validation against the documented caps.

```python
from whagent import Agent

agent = Agent("<ACCESS_TOKEN>")

@agent.on_text
def echo(ctx):
    ctx.reply(f"You said: {ctx.text}")

agent.run()
```

## Install

```bash
pip install -e .          # from a clone
pip install requests      # the only runtime dependency
```

Python 3.9+.

## Get a token

In WhatsApp: **Settings → Agents → Create an agent**, then open the agent's chat → **Chat info → API key**. Copy the key — that is the token. Store it as a secret; rotating it invalidates the old one, and reinstalling the app means regenerating it.

```bash
export WHATSAPP_AGENT_TOKEN='...'
```

## Two layers

### `Agent` — handlers and a poll loop

```python
import os
from whagent import Agent, FileOffsetStore

agent = Agent(
    os.environ["WHATSAPP_AGENT_TOKEN"],
    start="new",                                    # or "beginning" to replay the backlog
    offset_store=FileOffsetStore(".whagent-offset"),  # survive restarts
)

@agent.on_text(r"^/help")            # regex filter, searched case-insensitively
def help_command(ctx):
    ctx.reply("Send me a photo and I'll tell you how big it is.")

@agent.on_message("image")           # or a list: ["image", "video"]
def on_image(ctx):
    data = ctx.download()            # bytes, or ctx.download("/tmp/photo.jpg")
    ctx.reply(f"{len(data)} bytes, thanks {ctx.profile_name or 'there'}!")

@agent.on_status                     # delivery and read receipts for what you sent
def on_status(status):
    print(status.id, status.status)

@agent.on_error                      # without this, handler errors are logged
def on_error(exc, ctx):
    print("handler failed:", exc)

agent.run()
```

Decorators: `on_text`, `on_message`, `on_media`, `on_reaction`, `on_status`, `on_update`, `on_error`.

While it runs, the agent marks each dispatched message as read, shows a typing indicator (both `mark_read=` and `typing=` can be turned off), keeps the poll offset moving, and skips a message id it has already handled so a replayed offset is not answered twice.

The handler gets a `Context`:

| | |
|---|---|
| `ctx.text` | text body, or the caption of a media message |
| `ctx.sender` / `ctx.profile_name` | `user:<id>`, and the display name when the platform sent one |
| `ctx.type` / `ctx.message` | message type, and the full [`Message`](#models) |
| `ctx.reply(body, quote=False)` | send text back; `quote=True` quotes the incoming message |
| `ctx.reply_image/_video/_audio/_document/_sticker(...)` | `file=` a path or bytes (uploaded for you), or `media_id=` |
| `ctx.download(dest=None)` | the message's media, as bytes or written to `dest` |
| `ctx.mark_read()` / `ctx.typing()` | receipts by hand; refresh typing every 25s for a slow reply |
| `ctx.client` | the underlying `Client` |

### `Client` — one method per endpoint

```python
from whagent import Client

with Client("<ACCESS_TOKEN>") as client:
    client.send_text("user:50972923564215", "Hello from my agent!", preview_url=False)

    media_id = client.upload_media("invoice.pdf")           # MIME type guessed from the name
    client.send_document("user:509...", media_id=media_id, filename="invoice.pdf")
    client.send_image("user:509...", file="cat.jpg", caption="look at this")  # uploads, then sends

    update = client.get_updates(offset=1287, limit=50, timeout=15)  # None on a 204
    client.mark_read("wamid...", typing=True)
    client.delete_media(media_id)
```

| Method | Endpoint |
|---|---|
| `send_text`, `send_image`, `send_audio`, `send_video`, `send_document`, `send_sticker`, `send_message`, `reply` | `POST /messages` |
| `get_updates`, `poll_updates` | `GET /updates` |
| `mark_read`, `send_typing` | `POST /statuses` |
| `upload_media`, `get_media`, `download_media`, `download_url`, `delete_media` | `POST`/`GET`/`DELETE /media` |

## Receiving: offsets

`GET /updates` is a long poll, and messages and receipts share one per-agent sequence.

* **Omit `offset`** to start from the head as of the moment the request arrives — new traffic only. Do this once: an offset-less poll re-resolves the head, so a loop built on them can miss whatever arrives between one response and the next request.
* **`offset=0`** replays up to 30 days of backlog. An agent that answers automatically will answer all of it.
* Otherwise pass back the previous response's `next_offset` unchanged.
* A **204** means the timeout elapsed with nothing to deliver. There is no `next_offset` on a 204, so re-poll with the same offset — `get_updates()` returns `None`, and `poll_updates()` handles it for you.

`poll_updates()` does the bookkeeping and yields only non-empty updates:

```python
for update in client.poll_updates(offset=None, timeout=25, on_offset=save_offset):
    for message in update.messages:
        ...
```

Run **one poll at a time per agent** — a second poll replaces the first, which then fails with `PollReplacedError`.

## Models

`Update` → `.messages`, `.statuses`, `.contacts`, `.next_offset`, `.profile_name(wa_id)`.

`Message` → `.id`, `.sender`, `.type`, `.text`, `.caption`, `.media` (`.id`, `.mime_type`, `.sha256`, `.filename`, `.voice`, `.animated`), `.reaction` (`.emoji`, `.removed`), `.context` (`.message_id`, `.sender`, `.from_agent`), `.profile_name`, `.datetime`.

`Status` → `.id`, `.status`, `.recipient_id`, `.delivered`, `.read`, `.datetime`.

Every model keeps the payload it came from in `.raw`, so a field the platform adds later is still reachable.

### Participant identifiers

An identifier is `user:<id>` or `agent:<id>`. Treat the whole string as opaque, compare it in full, and never show it to a WhatsApp user. It names an account, not a person, and can change — use it as a conversation key, not a primary key, and prefer the `sender` of a recent message over one you stored long ago.

`to` accepts `user:<id>` only; the library rejects anything else before the request leaves.

## Errors

Every failure raises a subclass of `WhagentError`. `ValidationError` means the library stopped the request locally; `APIError` and its subclasses carry `.status`, `.code`, `.details` and `.fbtrace_id`.

| Exception | HTTP | `error.code` |
|---|---|---|
| `AuthenticationError` | 401 | 190 |
| `InvalidRequestError` | 400 | 100, 131009 |
| `MediaUploadError` | 400 | 131053 |
| `MediaNotFoundError` | 404 | 100 |
| `ForbiddenError` | 403 | 131005 |
| `RateLimitError` | 429 | 130429 |
| `NotDeliveredError` | 503 | 131016 |
| `PollReplacedError` | 409 | 1752041 |
| `ServerError` | 5xx | 2 |

```python
from whagent import RateLimitError, ForbiddenError

try:
    client.send_text(to, body)
except ForbiddenError:
    ...  # an agent may only message its creator
except RateLimitError as exc:
    ...  # already retried; exc.retry_after is set when the API sent one
```

### Retries

`RateLimitError` (429) and `NotDeliveredError` (503/131016) are retried with exponential backoff and jitter — in both cases nothing was sent. A 500 or a dropped connection on `POST /messages` leaves it **unknown** whether the message went out, so it is *not* retried by default; a retry may deliver it twice. Opt in with `Client(..., retry_send_on_server_error=True)`. Reads and deletes are retried either way.

Don't issue concurrent sends to the same recipient: their order is not guaranteed.

## Rate limits

12 requests/minute for `POST /messages`, `POST /statuses` and each media method; 15/minute for `GET /updates`; each counter is per agent over a rolling 60 seconds. The client paces itself to stay inside them, sleeping rather than collecting 429s. Turn it off with `Client(..., rate_limit=False)`.

## Caps the library checks before sending

| | |
|---|---|
| Text body | 4096 characters |
| Caption | 1024 characters, on image/video/document only |
| Image | 5 MB, JPEG or PNG, 8-bit RGB/RGBA, ≤25 megapixels |
| Sticker | 500 KB, WebP, canvas ≤4096 × 4096 |
| Video, audio, document, binary | 16 MB |
| Media retention | 30 days |

Video should be H.264 + AAC with the `moov` atom first (`ffmpeg -movflags +faststart`). Reactions are receive-only — sending one raises `ValidationError`.

## Configuration

```python
Client(
    token,
    base_url="https://api.whatsapp.com/agent/v1",
    timeout=30.0,                       # read timeout; polls extend it past the long-poll window
    max_retries=3,
    rate_limit=True,
    retry_send_on_server_error=False,
    validate=True,                      # local checks on lengths, recipients and media
    session=None,                       # bring your own requests.Session
)
```

`Agent(token, ...)` forwards any extra keyword arguments to `Client`, or takes a ready one as `client=`.

## Examples

* [`examples/echo_bot.py`](examples/echo_bot.py) — text, media and reactions
* [`examples/media_bot.py`](examples/media_bot.py) — download an attachment, send a file back
* [`examples/raw_client.py`](examples/raw_client.py) — the loop without the `Agent` layer

## Tests

```bash
pip install -e ".[dev]"
pytest
```

120 tests, no network: the HTTP session is faked, so they assert the exact requests the library builds against the payloads in the manual.

## License

MIT
