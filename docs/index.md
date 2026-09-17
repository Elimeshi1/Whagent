---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# WhatsApp agents, in Python

whagent is a small library for the [WhatsApp Agent Platform](https://www.whatsapp.com/developer/WhatsApp-Agent-Platform-Developer-Manual.pdf). You write a function that answers a message; it handles the API — polling, receipts, media, retries and rate limits.

[Get started](getting-started.md){ .md-button .md-button--primary }
[How it works](concepts.md){ .md-button }
[Questions](faq.md){ .md-button }

</div>

<div class="prose" markdown>

```python
from whagent import Agent

agent = Agent("<ACCESS_TOKEN>")

@agent.on_text
def echo(ctx):
    ctx.reply(f"You said: {ctx.text}")

agent.run()
```

That is a complete, running agent. It polls for your messages, marks them read, shows a typing indicator while your function runs, and sends the reply.

```bash
pip install -e .
```

Python 3.9+, one dependency (`requests`).

## The one thing to know first

**An agent talks to exactly one person: the WhatsApp account that created it — you.**

It cannot message anyone else, cannot message your other agents, and cannot post in groups. Think of it as a private assistant in your own chat list, not a bot with an audience. [Why, and what that means →](faq.md)

</div>

## Start here

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting started**

    ---

    Create an agent in WhatsApp, get a token, run your first reply.

    [:octicons-arrow-right-24: Five minutes](getting-started.md)

-   :material-lightbulb-on:{ .lg .middle } **How it works**

    ---

    Polling instead of webhooks, why messages have ids, and what stays yours to track.

    [:octicons-arrow-right-24: The model](concepts.md)

-   :material-comment-question:{ .lg .middle } **Questions and answers**

    ---

    Who can it message? What if it is offline? Can I run two? Straight answers.

    [:octicons-arrow-right-24: Q&A](faq.md)

</div>

## Do something

<div class="grid cards" markdown>

-   :material-send:{ .lg .middle } **Send a message**

    ---

    Text, photos, documents, stickers — with captions, quotes and link previews.

    [:octicons-arrow-right-24: Sending messages](sending.md)

-   :material-inbox-arrow-down:{ .lg .middle } **Receive messages**

    ---

    The poll loop, and how to never miss or double-answer a message.

    [:octicons-arrow-right-24: Receiving messages](receiving.md)

-   :material-file-download:{ .lg .middle } **Handle files**

    ---

    Download what you are sent, upload what you send back.

    [:octicons-arrow-right-24: Files and media](media.md)

-   :material-server:{ .lg .middle } **Run it for real**

    ---

    Surviving restarts, slow work, worker threads, systemd.

    [:octicons-arrow-right-24: Recipes](recipes.md)

</div>

## Look something up

<div class="grid cards" markdown>

-   **[`Agent`](agent.md)** — handlers, `Context`, the run loop
-   **[`Client`](client.md)** — one method per endpoint
-   **[Models](models.md)** — what `Message`, `Status` and `Update` carry
-   **[Errors](errors.md)** — every code, and what to do about it
-   **[Rate limits](rate-limits.md)** — 12 sends a minute, and how to live in it
-   **[Limits and formats](limits.md)** — sizes, MIME types, codecs

</div>

---

whagent is an independent library built against version 1 of the developer manual (August 25, 2026). It is not affiliated with or endorsed by WhatsApp.
