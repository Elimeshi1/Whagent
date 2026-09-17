# Receiving messages

`GET /agent/v1/updates`

Inbound messages and delivery receipts arrive through a long poll. The connection stays open until something arrives or the timeout elapses.

```python
for update in client.poll_updates():
    for message in update.messages:
        print(message.sender, message.text)
    for status in update.statuses:
        print(status.id, status.status)
```

`poll_updates()` handles offsets, empty polls and backoff. `get_updates()` is the single request underneath it.

## One request

```python
update = client.get_updates(offset=1287, limit=50, timeout=15)
```

| Argument | Default | Range | Meaning |
|---|---|---|---|
| `offset` | head at request time | ≥ 0, or omitted | Where to read from |
| `limit` | 50 | ≤ 100 | Max entries in the response |
| `timeout` | 15 | 0–25 s | How long to hold the connection open |

Out-of-range values are adjusted rather than rejected; the library clamps them before sending. Only a non-integer is a 400.

The return value is an [`Update`](models.md#update), or **`None`** when the timeout elapsed with nothing to deliver (HTTP 204).

## Offsets

Messages and statuses share **one per-agent sequence**. Each 200 response carries `next_offset`; pass it to the next poll, unchanged. Store it as a 64-bit signed integer and never compute one of your own.

```python
offset = None
while True:
    update = client.get_updates(offset=offset)
    if update is None:
        continue            # 204: no next_offset — re-poll with the SAME offset
    offset = update.next_offset
    handle(update)
```

Three things follow, and they are the whole subtlety of this endpoint:

1. **A 204 carries no `next_offset`.** Re-poll with the same offset. `get_updates()` returns `None`; `poll_updates()` does this for you.
2. **Polling does not consume entries.** They are retained for 30 days, so the same offset can be re-read — which also means *you* decide what counts as already handled.
3. **Marking a message read removes it.** A message drops out of the buffer as soon as it is marked read, and a poll at an earlier offset no longer returns it. Receipts (`statuses`) are unaffected. So a message is replayable only until you mark it — mark it once you have handled it, not before.

### Where to start

| Start | How | Effect |
|---|---|---|
| New traffic only | omit `offset` | Resolves to the head at the moment the request arrives. **Do this once** — an offset-less poll re-resolves the head, so a loop built on them can miss whatever arrived between one response and the next request. |
| Everything retained | `offset=0` | Replays up to 30 days of backlog — every receipt, and every message not yet marked read. An agent that answers automatically will answer all of those. |
| Where you left off | `offset=<stored next_offset>` | The normal case once you persist it. |

With `Agent`, that is `start="new"`, `start="beginning"` or an `offset_store` — see [Agent → offset persistence](agent.md#offset-persistence).

> Before replaying a backlog, record which `message.id` values you have handled, or filter on `message.timestamp`. `Agent` deduplicates within a process (`skip_own_replays=True`); across restarts, that is your store's job.

## The poll loop

```python
for update in client.poll_updates(
    offset=None,
    limit=50,
    timeout=25,
    on_offset=save_offset,   # called with each new next_offset
    max_polls=None,          # stop after N polls
    stop=None,               # callable checked before each poll
):
    ...
```

It yields only **non-empty** updates, calls `on_offset` only after your loop body has finished with an update (so a crash mid-update re-reads it), skips 204s without moving the offset, and backs off on `RateLimitError` and `ServerError` while reusing the prior offset — nothing was consumed, so nothing is lost.

`PollReplacedError` is raised, not retried: it means a second poll for the same agent replaced this one. Run one poll loop per token.

## What an update contains

```python
update.messages        # list[Message]  — always present, may be empty
update.statuses        # list[Status]   — receipts for messages you sent
update.contacts        # list[Contact]  — at most one entry per user
update.next_offset     # int
update.agent_id        # your agent's numeric id
update.raw             # the untouched JSON
bool(update)           # True when it has any messages or statuses
```

A poll can return only messages, only statuses, or both.

### Profile names

`contacts[].profile` appears **only** when the user has set a profile name, and an entry may omit it even when earlier ones had it. Accumulate names across polls rather than relying on a single response:

```python
names = {}

@agent.on_update
def remember_names(update):
    for contact in update.contacts:
        if contact.name:
            names[contact.wa_id] = contact.name
```

`ctx.profile_name` and `message.profile_name` give you the name from the update the message arrived in, when there was one.

## Timeouts

Hold the connection open as long as the platform allows (`timeout=25`) to cut the number of requests and the latency of a reply. The library sets the HTTP read timeout well past the long-poll window so an ordinary delay never looks like a failure.

## What can go wrong

| Code | Meaning | Action |
|---|---|---|
| 204 | Nothing to deliver before the timeout | Re-poll with the same offset |
| 400 | A query parameter is not a plain integer | Fix the value |
| 401 | Missing or malformed `Authorization` header | Check the token |
| 409 | A newer poll replaced this one | Run one poll at a time per agent |
| 429 | More than 15 polls per minute | Reuse the offset, back off |
| 500 | Internal error | Reuse the offset, back off |
