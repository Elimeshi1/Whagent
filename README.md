# whagent

A small Python library for the [WhatsApp Agent Platform](https://www.whatsapp.com/developer/WhatsApp-Agent-Platform-Developer-Manual.pdf) API (`https://api.whatsapp.com/agent/v1`).

It covers every endpoint in version 1 of the developer manual — sending, long-poll receiving, read receipts, the typing indicator and media — and adds what you would otherwise write yourself: typed responses, offset tracking, retries with backoff, client-side rate limiting and local validation against the documented caps.

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
pip install -e .
```

Python 3.9+. The only runtime dependency is `requests`.

## Documentation

**https://elimeshi1.github.io/Whagent/** — built from [`docs/`](docs/index.md) with MkDocs Material.

| | |
|---|---|
| [Getting started](docs/getting-started.md) | Create an agent, get a token, run your first reply |
| [How it works](docs/concepts.md) | Polling, offsets, identifiers — the model in six pieces |
| [Questions and answers](docs/faq.md) | Who it can message, what happens offline, running two agents |
| [Sending messages](docs/sending.md) | `POST /messages` — every type, captions, quotes |
| [Receiving messages](docs/receiving.md) | `GET /updates` and offsets |
| [Files and media](docs/media.md) | Upload, download, delete |
| [Receipts and typing](docs/receipts.md) | `POST /statuses` |
| [Agent](docs/agent.md) | Handlers, `Context`, the run loop |
| [Client](docs/client.md) | One method per endpoint |
| [Models](docs/models.md) | `Update`, `Message`, `Status`, `Media` |
| [Errors](docs/errors.md) | Exception hierarchy, codes, retry policy |
| [Rate limits](docs/rate-limits.md) | Per-method caps and the built-in limiter |
| [Limits and formats](docs/limits.md) | Length caps, sizes, accepted MIME types |
| [Recipes](docs/recipes.md) | Persistence, slow work, shutdown, deployment |
| [Testing](docs/testing.md) | Testing an agent without touching the network |

Build the site locally with:

```bash
pip install -r docs/requirements.txt
mkdocs serve
```


## At a glance

Two layers — use whichever fits.

**`Agent`** registers handlers and runs the loop for you:

```python
@agent.on_text(r"^/help")     # regex filter
def help_command(ctx):
    ctx.reply("Send me a photo and I'll tell you how big it is.")

@agent.on_message("image")
def on_image(ctx):
    data = ctx.download()
    ctx.reply(f"{len(data)} bytes, thanks {ctx.profile_name or 'there'}!")
```

**`Client`** is one method per endpoint:

```python
from whagent import Client

with Client(token) as client:
    client.send_text("Hello!")                  # an agent has exactly one recipient
    client.send_image(file="cat.jpg", caption="look at this")
    update = client.get_updates(offset=1287, timeout=25)
```

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
