# Receipts and typing

`POST /agent/v1/statuses`

One endpoint does both: it marks a message the user sent you as **read**, and optionally shows a **typing indicator** in the same call.

```python
client.mark_read("wamid.HBg...")                  # blue ticks
client.mark_read("wamid.HBg...", typing=True)     # ticks + "typing…"
client.send_typing("wamid.HBg...")                # same as the line above
```

Both return `True` when the platform accepted it.

## What you may mark

Only a message **the agent's creator sent to this agent**, identified by a wamid from `GET /updates`. Marking anything else is HTTP 403 (code `131005`); a `message_id` that is not a wamid issued by the platform is a 400.

`"read"` is the only status an agent can set — there is no "delivered" to send, and no unread.

## The typing indicator

```python
@agent.on_text
def slow_work(ctx):
    answer = think_hard(ctx.text)     # takes a while
    ctx.reply(answer)
```

With `Agent`, the indicator is sent for you before each handler runs (`typing=True`, the default). By hand it is `{"type": "text"}` — the only accepted shape.

Two rules:

* **It clears when you reply, or after 25 seconds** — whichever comes first. For a reply that takes longer, repeat the call to refresh it:

  ```python
  @agent.on_text
  def very_slow(ctx):
      for chunk in long_running_job(ctx.text):
          ctx.typing()          # refresh before each 25-second window elapses
      ctx.reply("done")
  ```

  See [Recipes → work that takes longer than 25 seconds](recipes.md#work-that-takes-longer-than-25-seconds) for a version that refreshes on a timer.

* **Show it only when you are going to reply.** An indicator that never resolves into a message is worse than none.

## Turning the automatic receipts off

```python
agent = Agent(token, typing=False)                  # mark read, no indicator
agent = Agent(token, typing=False, mark_read=False) # neither; you decide in the handler
```

With both off, nothing is sent for a message until you call `ctx.mark_read()` yourself. Note that `Agent` only acknowledges messages that at least one handler matches.

## What can go wrong

| Code | Meaning | Action |
|---|---|---|
| 400 | A field is missing or malformed; `typing_indicator` has a `type` other than `"text"` | Read `error_data.details`, which names the field |
| 401 | Missing or malformed `Authorization` header | Check the token |
| 403 | The message was not sent by the agent's creator | Mark only the creator's messages |
| 429 | More than 12 requests per minute | [Paced for you by default](rate-limits.md) |
| 500 | Internal error — the message may already be marked read | Back off and retry |
| 503 | The receipt or the indicator was not accepted | Retry; the two cases are indistinguishable, so it may already be read |

A failed receipt is not worth crashing over: `Agent` logs it as a warning and runs the handler anyway.
