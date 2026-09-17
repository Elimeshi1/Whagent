# Getting started

## Install

```bash
git clone https://github.com/Elimeshi1/Whagent.git
cd Whagent
pip install -e .
```

Python 3.9 or newer. The only runtime dependency is [`requests`](https://pypi.org/project/requests/).

For the test suite:

```bash
pip install -e ".[dev]"
pytest
```

## Get an API token

1. Open WhatsApp → **Settings → Agents → Create an agent**.
2. Set a display name and an avatar.
3. Open the agent's chat → **Chat info → API key**.
4. Copy the key. That is your API token.

Store it as a secret — it is an opaque string, so don't try to parse it. Rotating the token invalidates the old one, and reinstalling WhatsApp means regenerating it.

```bash
export WHATSAPP_AGENT_TOKEN='...'
```

> An agent may only exchange messages with **its creator**, and that account must have the agent API enabled. Messaging anyone else fails with [`ForbiddenError`](errors.md).

## Your first agent

```python
import os
from whagent import Agent

agent = Agent(os.environ["WHATSAPP_AGENT_TOKEN"])

@agent.on_text
def echo(ctx):
    ctx.reply(f"You said: {ctx.text}")

agent.run()
```

Run it, then write to your agent in WhatsApp. `run()` polls for updates, marks each message as read, shows a typing indicator while your handler runs, and dispatches the message to the handlers that match.

## Sending without the Agent layer

```python
from whagent import Client

with Client(os.environ["WHATSAPP_AGENT_TOKEN"]) as client:
    result = client.send_text("user:50972923564215", "Hello from my agent!")
    print(result.message_id)   # wamid.HBg...
```

The recipient is a [participant identifier](concepts.md#3-participant-identifiers) of the form `user:<id>` — take it from the `sender` of an inbound message and pass it back unchanged.

## What to read next

* [Concepts](concepts.md) — what the platform guarantees, and what it doesn't
* [Agent](agent.md) — every handler type and what `Context` gives you
* [Receiving updates](receiving.md) — offsets, the one thing worth understanding properly
* [Recipes](recipes.md) — persistence, slow work, shutdown
