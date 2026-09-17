# whagent

[![PyPI](https://img.shields.io/pypi/v/whagent)](https://pypi.org/project/whagent/)
[![Python](https://img.shields.io/pypi/pyversions/whagent)](https://pypi.org/project/whagent/)
[![Docs](https://img.shields.io/badge/docs-elimeshi1.github.io-blue)](https://elimeshi1.github.io/Whagent/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/Elimeshi1/Whagent/blob/main/LICENSE)

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
pip install whagent
```

Python 3.9+. The only runtime dependency is `requests`. Upgrade with `pip install -U whagent`; releases are listed on [PyPI](https://pypi.org/project/whagent/).

## Documentation

**https://elimeshi1.github.io/Whagent/** — built from [`docs/`](https://github.com/Elimeshi1/Whagent/tree/main/docs) with MkDocs Material.

| | |
|---|---|
| [Getting started](https://elimeshi1.github.io/Whagent/getting-started/) | Create an agent, get a token, run your first reply |
| [How it works](https://elimeshi1.github.io/Whagent/concepts/) | Polling, offsets, identifiers — the model in six pieces |
| [Questions and answers](https://elimeshi1.github.io/Whagent/faq/) | Who it can message, what happens offline, running two agents |
| [Sending messages](https://elimeshi1.github.io/Whagent/sending/) | `POST /messages` — every type, captions, quotes |
| [Receiving messages](https://elimeshi1.github.io/Whagent/receiving/) | `GET /updates` and offsets |
| [Files and media](https://elimeshi1.github.io/Whagent/media/) | Upload, download, delete |
| [Receipts and typing](https://elimeshi1.github.io/Whagent/receipts/) | `POST /statuses` |
| [Agent](https://elimeshi1.github.io/Whagent/agent/) | Handlers, `Context`, the run loop |
| [Client](https://elimeshi1.github.io/Whagent/client/) | One method per endpoint |
| [Models](https://elimeshi1.github.io/Whagent/models/) | `Update`, `Message`, `Status`, `Media` |
| [Errors](https://elimeshi1.github.io/Whagent/errors/) | Exception hierarchy, codes, retry policy |
| [Rate limits](https://elimeshi1.github.io/Whagent/rate-limits/) | Per-method caps and the built-in limiter |
| [Limits and formats](https://elimeshi1.github.io/Whagent/limits/) | Length caps, sizes, accepted MIME types |
| [Recipes](https://elimeshi1.github.io/Whagent/recipes/) | Persistence, slow work, shutdown, deployment |
| [Testing](https://elimeshi1.github.io/Whagent/testing/) | Testing an agent without touching the network |

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

* [`examples/echo_bot.py`](https://github.com/Elimeshi1/Whagent/blob/main/examples/echo_bot.py) — text, media and reactions
* [`examples/media_bot.py`](https://github.com/Elimeshi1/Whagent/blob/main/examples/media_bot.py) — download an attachment, send a file back
* [`examples/raw_client.py`](https://github.com/Elimeshi1/Whagent/blob/main/examples/raw_client.py) — the loop without the `Agent` layer

## Tests

```bash
git clone https://github.com/Elimeshi1/Whagent.git
cd Whagent
pip install -U pip        # editable installs need pip 21.3 or newer
pip install -e ".[dev]"
pytest
```

## License

MIT
