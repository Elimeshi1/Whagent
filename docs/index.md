# whagent

whagent is a Python library for the [WhatsApp Agent Platform](https://www.whatsapp.com/developer/WhatsApp-Agent-Platform-Developer-Manual.pdf) — the API behind the agents you create from WhatsApp's own settings. You write a function that answers a message; the library handles the rest: polling, read receipts, media, retries and rate limits.
{ .lead }

```python
from whagent import Agent

agent = Agent("<ACCESS_TOKEN>")

@agent.on_text
def echo(ctx):
    ctx.reply(f"You said: {ctx.text}")

agent.run()
```

That is a complete agent. It polls for your messages, marks them read, shows a typing indicator while your function runs, and sends the reply.

## Installation

```bash
git clone https://github.com/Elimeshi1/Whagent.git
cd Whagent
pip install -e .
```

Python 3.9 or newer. The only runtime dependency is `requests`.

## First, the one rule that shapes everything

**An agent talks to exactly one person: the WhatsApp account that created it — you.**

It cannot message anyone else, cannot message your other agents, and cannot post in groups. It is a private assistant in your own chat list, not a bot with an audience. [Why, and what follows from it](faq.md).

## How this documentation is organized

<div class="sections" markdown>

### Start

- [Getting started](getting-started.md) — create an agent, get a token, run your first reply
- [How it works](concepts.md) — polling, offsets and identifiers, in six short pieces
- [Questions and answers](faq.md) — who it can message, what happens offline, running two agents

### Guides

- [Sending messages](sending.md) — text, media, captions, quotes, link previews
- [Receiving messages](receiving.md) — the poll loop, and never missing or repeating one
- [Files and media](media.md) — download what you are sent, upload what you send back
- [Receipts and typing](receipts.md) — blue ticks and the typing indicator

### Reference

- [`Agent`](agent.md) — handlers, `Context`, the run loop
- [`Client`](client.md) — one method per endpoint
- [Models](models.md) — what `Message`, `Status` and `Update` carry
- [Errors](errors.md) — every error code, and what to do about it
- [Rate limits](rate-limits.md) — the per-method caps and the built-in limiter
- [Limits and formats](limits.md) — sizes, MIME types, codecs

### Practice

- [Recipes](recipes.md) — persistence, slow work, worker threads, deployment
- [Testing](testing.md) — testing an agent without touching the network

</div>

---

whagent is an independent library built against version 1 of the developer manual (August 25, 2026). It is not affiliated with or endorsed by WhatsApp.
