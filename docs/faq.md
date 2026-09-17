# Questions and answers

The questions that come up first, answered directly.

## Who can my agent send messages to?

**Only its creator — the WhatsApp account that made it.** That is the whole address book.

The platform enforces it twice over:

* `to` accepts a WhatsApp user identifier and nothing else. An agent identifier, a bare phone number, or any other shape comes back as **400**, code `131009`.
* Even a well-formed user identifier that is not the creator comes back as **403**, code `131005`: *"The bot may only message its own API-enabled owner"*.
* A `user:` identifier carrying an agent's id comes back as **500**, code `2`, and nothing is delivered.

So: no other people, no customers, no broadcast lists.

## Can my agents talk to each other?

**No** — not even between two agents created by the same account:

| Attempt | Result |
|---|---|
| `to="agent:<id>"` | 400, code `131009` — *Invalid participant type; expected: user, got: agent* |
| the bare numeric id | 400, code `131009` — *Invalid participant format* |
| `to="user:<agent id>"` | 500, code `2` |
| `get_media` / `delete_media` / sending the other agent's media id | 400 — *No media found* |
| fetching the other agent's media URL with your token | 404, code `100` |
| `mark_read` on the other agent's message | 400, code `131009` |

Media and receipts are fully isolated per agent. One exception: `reply_to` accepts a wamid from the other agent's chat, so do not rely on the API to reject a foreign wamid there.

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

## Do I need to pass a recipient?

**No.** An agent has exactly one recipient, so every send works without one:

```python
client.send_text("Hello")           # to whoever created this agent
ctx.reply("Hello")                  # same, inside a handler
```

The client remembers the identifier from every poll and every send, and a client that has never polled looks it up by itself before its first send — so a send-only script needs nothing at all. See [the recipient](sending.md#the-recipient).

`to` is still accepted, as an option. If you pass it, take it from a **recent** inbound message (`message.sender`) and never hardcode it: an identifier points at an *account*, not a person, and it changes with a new phone number or a re-registered account.

```python
client.send_text(message.sender, "hi")          # fine: current
client.send_text("user:50972923564215", "hi")   # a value that can expire
```

## Then what are the identifiers on a message for?

Mostly for reading, not for addressing:

* **Who wrote a quoted message.** `context.from` is `user:<id>` when you wrote the quoted message and `agent:<id>` when your agent did — `message.context.from_agent` gives you that as a `bool`:

  ```python
  @agent.on_text
  def handle(ctx):
      if ctx.message.context and ctx.message.context.from_agent:
          ...     # they replied to something the agent said
  ```

* **One format everywhere.** `from`, `wa_id`, `recipient_id` and `input` all use the same `<type>:<id>` shape.

Treat an identifier as an opaque internal handle: never build one, never parse one, and never show one to a person — it is not a phone number.

## Do I need a server, a domain or a webhook?

No. The agent **polls** — it opens a request to WhatsApp and waits up to 25 seconds for something to arrive. Nothing connects to you, so it runs behind any firewall, on a laptop, in a container, with only outbound HTTPS. See [How it works](concepts.md).

## What happens to messages sent while my agent is off?

They wait. Updates are buffered for **30 days**, and polling does not consume them — only marking a message read does. When your agent starts again it continues from the offset it stored:

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

Yes. Nothing requires an inbound message before you send — a scheduled job that calls `client.send_text("...")` works, and stays inside the rate limit. You don't need an identifier: a client that has never polled looks it up by itself before its first send. See [the recipient](sending.md#the-recipient).

## Can it read my other WhatsApp chats?

No. The API exposes exactly one conversation: messages you send to this agent, and receipts for messages it sent you. Nothing else on your account is visible.

## What can it send?

Text (4096 characters), images, video, audio, documents and stickers. It can *receive* one more thing than it can send: reactions. Sending a reaction is not supported — `ValidationError` locally, 400 from the API. [Formats and sizes](limits.md)

## What does a "wamid" mean?

The id of a single message, returned when you send one and present on everything you receive. You use it to quote a message, to mark one as read, and to match a delivery receipt to what you sent. Opaque — store it, compare it, never parse it.

## My agent answered a month of old messages. Why?

It started from `offset=0`, which replays the 30-day buffer — every message in it that was never marked read. (Messages that were marked read are gone from the buffer, so they are not replayed.) Use `start="new"` (the default) for traffic from now on, or keep a record of the message ids you have already handled. [Replaying a backlog safely](recipes.md)

## I get a 400 with code 100 and everything looks fine

Check the token before the payload. An absent or malformed `Authorization` header is a 401, but a token that is *present and invalid* — rotated, revoked, regenerated after a reinstall — is a **400 with code 100**, which reads like a request problem. [Errors](errors.md)
