# Agent

[← Documentation index](README.md)

`Agent` is the high-level layer: you register handlers, call `run()`, and it polls, acknowledges and dispatches.

```python
from whagent import Agent

agent = Agent("<ACCESS_TOKEN>")

@agent.on_text
def echo(ctx):
    ctx.reply(f"You said: {ctx.text}")

agent.run()
```

## Construction

```python
Agent(
    token=None,              # or client=<Client>, but not both
    client=None,
    mark_read=True,          # mark each dispatched message as read
    typing=True,             # show a typing indicator while a handler runs
    start="new",             # "new" | "beginning" | an integer offset
    offset_store=None,       # e.g. FileOffsetStore(".whagent-offset")
    skip_own_replays=True,   # ignore a message id already handled in this process
    **client_kwargs,         # forwarded to Client (timeout, rate_limit, ...)
)
```

| Argument | Notes |
|---|---|
| `mark_read` | A read receipt is sent only for messages that at least one handler matches. |
| `typing` | Implies `mark_read` — both travel in the same `POST /statuses` call. |
| `start` | Where the first poll begins when nothing is stored. See [starting points](receiving.md#where-to-start). |
| `offset_store` | Any object with `load()` and `save(offset)`. |
| `skip_own_replays` | Guards against answering the same message twice when an offset replays. |

To share one client between an agent and your own code:

```python
from whagent import Agent, Client

client = Client(token, timeout=60)
agent = Agent(client=client)
```

## Handlers

Every decorator can be used bare or with a filter.

| Decorator | Fires on | Signature |
|---|---|---|
| `@agent.on_text` | text messages | `f(ctx)` |
| `@agent.on_text(r"^/start")` | text matching a regex (searched, case-insensitive) | `f(ctx)` |
| `@agent.on_message` | every message | `f(ctx)` |
| `@agent.on_message("image")` | one type | `f(ctx)` |
| `@agent.on_message(["audio", "video"])` | several types | `f(ctx)` |
| `@agent.on_message(pattern=r"invoice")` | text body or caption matching a regex | `f(ctx)` |
| `@agent.on_media` | `image`, `audio`, `video`, `document`, `sticker` | `f(ctx)` |
| `@agent.on_reaction` | reactions (receive-only) | `f(ctx)` |
| `@agent.on_status` | delivery and read receipts | `f(status)` |
| `@agent.on_update` | each raw `Update`, before anything else | `f(update)` |
| `@agent.on_error` | an exception from any handler | `f(exc, ctx_or_None)` |

Handlers are **not** mutually exclusive: every matching handler runs, in registration order.

```python
@agent.on_text(r"^/help")
def help_command(ctx):
    ctx.reply("Send me a photo and I'll tell you how big it is.")

@agent.on_text
def everything_else(ctx):
    if ctx.text.startswith("/"):
        return          # already handled above
    ctx.reply("Try /help")
```

Registering an unknown message type raises `ValidationError` at import time rather than failing silently at runtime.

### Errors in handlers

An exception inside a handler never stops the loop. With an `on_error` handler it is passed to it; without one it is logged through the `whagent` logger:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Context

What a message handler receives.

### Reading

| | |
|---|---|
| `ctx.message` | the full [`Message`](models.md#message) |
| `ctx.text` | text body, or the **caption** of a media message |
| `ctx.type` | `"text"`, `"image"`, `"reaction"`, … |
| `ctx.sender` | `user:<id>` — pass back as a recipient unchanged |
| `ctx.profile_name` | display name, when the platform supplied one, else `None` |
| `ctx.update` | the `Update` this message arrived in |
| `ctx.client` | the underlying [`Client`](client.md) |

### Responding

| | |
|---|---|
| `ctx.reply(body, quote=False, preview_url=False)` | send text back |
| `ctx.reply_image(...)`, `ctx.reply_video(...)`, `ctx.reply_audio(...)`, `ctx.reply_document(...)`, `ctx.reply_sticker(...)` | `file=` a path or bytes (uploaded for you), or `media_id=` |
| `ctx.download(dest=None)` | this message's media, as bytes or written to `dest` |
| `ctx.mark_read(typing=False)` | send a receipt by hand |
| `ctx.typing()` | refresh the typing indicator (it clears after 25 s) |

`quote=True` makes the reply quote the incoming message:

```python
@agent.on_text
def handle(ctx):
    ctx.reply("got it", quote=True)
```

Every `reply_*` accepts the same keyword arguments as the matching `Client.send_*` — see [Sending messages](sending.md).

## Running

```python
agent.run(
    offset=None,      # overrides start= for this run
    limit=50,         # entries per poll, 1–100
    timeout=15,       # long-poll seconds, 0–25
    max_polls=None,   # stop after N polls (useful in tests)
    stop=None,        # callable checked before each poll; True ends the loop
)
```

`run()` blocks. `Ctrl-C` ends it cleanly. To stop it from another thread, see [Recipes → graceful shutdown](recipes.md#graceful-shutdown).

Dispatching an update by hand — for tests, or to drive the loop yourself:

```python
update = agent.client.get_updates(offset=0)
if update:
    agent.dispatch(update)
```

## Offset persistence

Without a store, a restart uses `start=` again: with `"new"` you lose whatever arrived while the process was down. `FileOffsetStore` fixes that:

```python
from whagent import Agent, FileOffsetStore

agent = Agent(token, offset_store=FileOffsetStore(".whagent-offset"))
```

Any object with `load() -> int | None` and `save(offset)` works — Redis, a database row, a config file:

```python
class RedisOffsetStore:
    def __init__(self, redis, key="whagent:offset"):
        self.redis, self.key = redis, key

    def load(self):
        value = self.redis.get(self.key)
        return int(value) if value else None

    def save(self, offset):
        self.redis.set(self.key, offset)
```

Store the offset as a **64-bit signed integer** and pass it back unchanged — never compute one of your own.

---

[← Concepts](concepts.md) · [Index](README.md) · [Client →](client.md)
