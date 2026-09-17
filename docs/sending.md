# Sending messages

`POST /agent/v1/messages`

An agent can send `text`, `image`, `audio`, `video`, `document` and `sticker`. Reactions are **receive-only**.

```python
result = client.send_text("user:50972923564215", "Hello! How can I help you?")
result.message_id     # "wamid.HBg..." — record this; it identifies the message in receipts
result.wa_id          # "user:50972923564215"
```

Every send returns a [`SendResult`](models.md#sendresult).

## The recipient

`to` must be `user:<id>` — a WhatsApp user, and the agent's creator. An `agent:<id>`, a bare phone number or any other shape is rejected (HTTP 400, code `131009`); the library catches these before the request leaves.

Take it from an inbound message and pass it back unchanged:

```python
client.send_text(message.sender, "...")
```

## Text

```python
client.send_text(to, "Hello", preview_url=True, reply_to="wamid.HBg...")
```

| Argument | |
|---|---|
| `body` | up to **4096 characters** |
| `preview_url` | render a preview for the first URL in the body; it must begin with `http://` or `https://` |
| `reply_to` | wamid of a message to quote |

## Media

Each media send takes **either** a `media_id` from an earlier upload, **or** a `file` that the library uploads first:

```python
# upload once, send many times
media_id = client.upload_media("logo.png")
client.send_image(to, media_id=media_id, caption="our logo")

# or in one call
client.send_image(to, file="cat.jpg", caption="look at this")
client.send_image(to, file=open("cat.jpg", "rb"))
client.send_image(to, file=photo_bytes, mime_type="image/jpeg")
```

| Method | Caption | Filename |
|---|---|---|
| `send_image` | ✅ ≤1024 chars | — |
| `send_video` | ✅ ≤1024 chars | — |
| `send_document` | ✅ ≤1024 chars | ✅ |
| `send_audio` | — | — |
| `send_sticker` | — | — |

Documents keep a filename, including its extension:

```python
client.send_document(to, file="invoice.pdf")                      # filename: invoice.pdf
client.send_document(to, media_id=mid, filename="invoice.pdf")    # set it yourself
```

Formats, size caps and codec constraints are in [Limits and formats](limits.md). Uploading is covered in [Files and media](media.md).

## Quoting a message

```python
client.send_text(to, "On it", reply_to=message.id)
client.reply(message, "On it")          # same thing, to the message's sender
ctx.reply("On it", quote=True)          # from an Agent handler
```

The wamid must come from this conversation — an id from `GET /updates`, or one you got back from a send. Anything else is a 400.

## Sending a type the library doesn't know

`send_message` takes any payload, so a type the platform adds later needs no library upgrade:

```python
client.send_message(to, "text", {"body": "Hello", "preview_url": True})
```

## Ordering

**Do not issue concurrent sends to the same recipient.** The order in which they arrive is not guaranteed. Send sequentially, or serialize per recipient — see [Recipes](recipes.md#handling-messages-off-the-poll-loop).

## What can go wrong

| Situation | Result |
|---|---|
| Body over 4096, or caption over 1024 | `ValidationError` locally; 400 + code `100` from the API |
| Payload object missing for the declared type | 400 |
| Media id missing, unknown or expired | 400 + code `131009` |
| `to` is malformed, or an `agent:` id | 400 + code `131009` |
| `type` is `reaction` | `ValidationError` locally; 400 from the API |
| Recipient is not the agent's creator | 403 + code `131005` |
| More than 12 sends per minute | 429 — [paced for you by default](rate-limits.md) |
| Not accepted for delivery | 503 + code `131016` — retried automatically |

Fields in payload objects other than the one being sent are still validated, so a stray over-long caption in an unused object can fail the request.

## Retrying a send

This is the one place where "just retry" is wrong. What to do depends on what came back:

| Response | Meaning | Action |
|---|---|---|
| `2xx` | Sent. | Record `message_id`. Never retry. |
| `4xx` | Not sent. | Fix the request or the token. A repeat fails the same way. |
| `429` | Not sent. | Back off and retry — **the library does this**. |
| `503` code `131016` | Not accepted for delivery, so not sent. | Back off and retry — **the library does this**. |
| `500`, connection reset, read timeout | **Unknown** whether it was sent. | Decide in advance. A retry may deliver twice. |

The library therefore does **not** retry a send after a 500 or a dropped connection. Opt in when a duplicate is cheaper than a loss:

```python
client = Client(token, retry_send_on_server_error=True)
```

A long read timeout is the cheaper protection — it keeps an ordinary delay from turning into an unknown outcome. `Client(timeout=...)` sets it.
