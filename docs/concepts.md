# Concepts

[← Documentation index](README.md)

What the platform is, in the six facts that shape how you write against it.

## 1. You poll; there is no webhook

Inbound messages arrive through a **long poll** of `GET /agent/v1/updates`, not a callback to a server of yours. The connection stays open until something arrives or the timeout elapses (up to 25 seconds). This means an agent can run from a laptop or a container with no inbound networking at all.

Run **one poll at a time per agent**. A second concurrent poll replaces the first, and the first fails with [`PollReplacedError`](errors.md) (HTTP 409).

See [Receiving updates](receiving.md).

## 2. Updates are a sequence you read with an offset

Messages and delivery receipts share a single per-agent sequence. Each response carries a `next_offset` to pass to the next poll. Entries are retained for **30 days** and polling does not consume them, so the same offset can be re-read.

The consequence: what your agent has already handled is *your* bookkeeping, not the platform's. See [offsets](receiving.md#offsets).

## 3. Participant identifiers

A participant identifier is written as `<type>:<id>`:

| Form | Meaning |
|---|---|
| `user:50972923564215` | a WhatsApp user |
| `agent:123456789` | an agent |

Treat the whole string as **opaque**: compare it in full, never parse it, and never show it to a WhatsApp user.

Where it appears:

| Field | Endpoint |
|---|---|
| `messages[].from`, `contacts[].wa_id`, `statuses[].recipient_id` | `GET /updates` |
| `to` | `POST /messages` — `user:<id>` only |
| `contacts[].wa_id`, `contacts[].input` | `POST /messages` response |
| `messages[].context.from` | either form — read the prefix to tell them apart |

In this library: `message.sender`, `status.recipient_id`, `contact.wa_id`, and `message.context.sender` (with `.from_agent` to tell which kind it is). Helpers: `whagent.participant_type(s)` and `whagent.is_user(s)`.

### Identifiers are not stable

An identifier refers to an **account**, not a person, and it can change — a new phone number, or an account deleted and re-registered, may produce a new one.

* Treat an identifier as a **conversation key**, not as a primary key for a user record.
* An unrecognized identifier is a new conversation. A returning user whose identifier changed cannot be matched to their earlier one.
* Prefer the `sender` of a **recent** inbound message over one you stored long ago; a user may no longer be reachable at the old one.

## 4. An agent talks to its creator only

The recipient of every outbound message must be the agent's creator, and that account must have the agent API enabled. Anything else is HTTP 403 / code `131005`. The same applies to read receipts: you may only mark messages that the creator sent.

## 5. Message ids

Every message — inbound or outbound — has a **wamid**, an opaque id like `wamid.HBgONTA5...`. You use it to:

* quote a message (`reply_to=` on a send),
* mark a message as read,
* match a delivery receipt to what you sent (`status.id`),
* deduplicate, when an offset replays.

## 6. Media is a two-step affair

You never attach bytes to a message. You upload the file, get a media id, and send a message that references it. Inbound media works the same way in reverse: the message carries a media id, and you fetch the bytes separately. Media expires after **30 days**.

See [Media](media.md). The library's `send_image(..., file=...)` does both steps for you.

---

[← Getting started](getting-started.md) · [Index](README.md) · [Agent →](agent.md)
