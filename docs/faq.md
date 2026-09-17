# Questions and answers

The questions that come up first, answered directly.

## Who can my agent send messages to?

**Only its creator — the WhatsApp account that made it.** That is the whole address book.

The platform enforces it twice over:

* `to` accepts a WhatsApp user identifier and nothing else. An agent identifier, a bare phone number, or any other shape comes back as **400**, code `131009`.
* Even a well-formed user identifier that is not the creator comes back as **403**, code `131005`: *"An agent may only message its creator."*

So: no other people, no customers, no broadcast lists.

## Can my agents talk to each other?

**No.** `to` rejects an `agent:<id>` outright — 400, code `131009`.

If you want two of your agents to cooperate, wire that up on your side: run both in one process and call a function, or put a queue between them. From WhatsApp's point of view each agent has exactly one conversation, with you.

```python
# Not possible:
client.send_text("agent:123456789", "hello colleague")   # -> 400 / 131009

# Do this instead — your own code, no API involved:
result = billing_agent.handle(question)
ctx.reply(result)
```

## Can it post in a group?

No. There is no group recipient in this API — only the one-to-one chat between you and your agent.

## Then why do messages carry an identifier at all?

Fair question, and the answer is not "so you can choose a recipient". Three reasons:

**1. It is not stable, so you must not hardcode it.** An identifier points at an *account*, not at a person, and it can change — a new phone number, or an account deleted and registered again. The manual is explicit: treat it as a conversation key, not a primary key, and prefer the `sender` of a **recent** message over one you stored months ago. If you paste today's identifier into your source code, one day your agent quietly stops reaching you.

```python
@agent.on_text
def handle(ctx):
    ctx.reply("hi")                       # replies to whoever wrote, always current

# rather than
client.send_text("user:50972923564215", "hi")   # a value that can expire
```

**2. The prefix tells you who wrote a quoted message.** This is the one place both forms really appear — `context.from` is `user:<id>` when you wrote the quoted message and `agent:<id>` when your agent did:

```python
@agent.on_text
def handle(ctx):
    if ctx.message.context and ctx.message.context.from_agent:
        ...     # they replied to something the agent said
```

**3. It is the platform's generic participant format**, used in the same shape for `wa_id`, `recipient_id` and `input`. One format everywhere is simpler than a different field per role.

One rule covers all of it: **take the identifier from an inbound message and send it back unchanged.** Never build one, never parse one, and never show one to a person — it is an internal handle, not a phone number.

## Do I need a server, a domain or a webhook?

No. The agent **polls** — it opens a request to WhatsApp and waits up to 25 seconds for something to arrive. Nothing connects to you, so it runs behind any firewall, on a laptop, in a container, with only outbound HTTPS. See [How it works](concepts.md).

## What happens to messages sent while my agent is off?

They wait. Updates are buffered for **30 days**, and reading them does not consume them. When your agent starts again it continues from the offset it stored:

```python
from whagent import Agent, FileOffsetStore

agent = Agent(token, offset_store=FileOffsetStore(".whagent-offset"))
```

Without a store, a restart begins from "now" and whatever arrived in between is skipped. With one, nothing is lost. [Details](receiving.md)

## Can I run two agents?

Yes — create each one in WhatsApp and give it its own token. Each has its own chat with you, its own buffer and its own rate limits.

What you must not do is run **two pollers on one token**. The second poll replaces the first, and the first fails with `PollReplacedError` (HTTP 409). One process per token.

## How fast can it answer?

12 outbound messages per minute, per agent — one every five seconds. Read receipts and typing indicators come out of a separate 12/minute budget, and polls out of 15/minute. The library paces itself so you get the wait instead of an error. [Rate limits](rate-limits.md)

## Can my agent message me first?

Yes. Nothing requires an inbound message before you send — a scheduled job that calls `send_text` works, as long as you have a current identifier for yourself and stay inside the rate limit. Get that identifier from a recent message rather than from a constant.

## Can it read my other WhatsApp chats?

No. The API exposes exactly one conversation: messages you send to this agent, and receipts for messages it sent you. Nothing else on your account is visible.

## What can it send?

Text (4096 characters), images, video, audio, documents and stickers. It can *receive* one more thing than it can send: reactions. Sending a reaction is not supported — `ValidationError` locally, 400 from the API. [Formats and sizes](limits.md)

## What does a "wamid" mean?

The id of a single message, returned when you send one and present on everything you receive. You use it to quote a message, to mark one as read, and to match a delivery receipt to what you sent. Opaque — store it, compare it, never parse it.

## My agent answered a month of old messages. Why?

It started from `offset=0`, which replays the whole 30-day buffer. Use `start="new"` (the default) for traffic from now on, or keep a record of the message ids you have already handled. [Replaying a backlog safely](recipes.md)

## I get a 400 with code 100 and everything looks fine

Check the token before the payload. An absent or malformed `Authorization` header is a 401, but a token that is *present and invalid* — rotated, revoked, regenerated after a reinstall — is a **400 with code 100**, which reads like a request problem. [Errors](errors.md)
