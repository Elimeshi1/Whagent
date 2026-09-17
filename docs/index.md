# whagent

A Python library for the [WhatsApp Agent Platform](https://www.whatsapp.com/developer/WhatsApp-Agent-Platform-Developer-Manual.pdf) API (`https://api.whatsapp.com/agent/v1`).

It covers every endpoint in version 1 of the developer manual — sending, long-poll receiving, read receipts, the typing indicator and media — and adds what you would otherwise write yourself: typed responses, offset tracking, retries with backoff, client-side rate limiting and local validation against the documented caps.

```python
from whagent import Agent

agent = Agent("<ACCESS_TOKEN>")

@agent.on_text
def echo(ctx):
    ctx.reply(f"You said: {ctx.text}")

agent.run()
```

```bash
pip install -e .
```

Python 3.9+. The only runtime dependency is `requests`.

## Two layers

Use whichever fits.

**[Agent](agent.md)** registers handlers and runs the poll loop for you — it polls, marks messages read, shows a typing indicator and dispatches each message to the handlers that match.

**[Client](client.md)** is one method per endpoint, with nothing hidden:

```python
from whagent import Client

with Client(token) as client:
    client.send_text("user:50972923564215", "Hello!")
    client.send_image("user:50972923564215", file="cat.jpg", caption="look at this")
    update = client.get_updates(offset=1287, timeout=25)
```

## Documentation

| Page | What it covers |
|---|---|
| [Getting started](getting-started.md) | Install, get an API token, run your first agent |
| [Concepts](concepts.md) | Polling, identifiers, what an agent may do |
| [Agent](agent.md) | Handlers, `Context`, the poll loop, offset persistence |
| [Client](client.md) | Construction, configuration, session and lifecycle |
| [Sending messages](sending.md) | `POST /messages` |
| [Receiving updates](receiving.md) | `GET /updates` and offsets |
| [Receipts and typing](receipts.md) | `POST /statuses` |
| [Media](media.md) | Upload, download, delete |
| [Models](models.md) | `Update`, `Message`, `Status`, `Media`, identifiers |
| [Errors](errors.md) | Exception hierarchy, error codes, retry policy |
| [Rate limits](rate-limits.md) | Per-method caps and the built-in limiter |
| [Limits and formats](limits.md) | Length caps, media sizes, accepted MIME types |
| [Recipes](recipes.md) | Persistence, slow work, shutdown, deployment |
| [Testing](testing.md) | Testing an agent without touching the network |

## Scope

whagent is an independent library built against version 1 of the WhatsApp Agent Platform developer manual (August 25, 2026). It is not affiliated with or endorsed by WhatsApp.
