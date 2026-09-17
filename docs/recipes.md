# Recipes

Patterns for the things a real agent runs into.

## Contents

* [Surviving a restart](#surviving-a-restart)
* [Replaying a backlog safely](#replaying-a-backlog-safely)
* [Work that takes longer than 25 seconds](#work-that-takes-longer-than-25-seconds)
* [Handling messages off the poll loop](#handling-messages-off-the-poll-loop)
* [Graceful shutdown](#graceful-shutdown)
* [Splitting a long reply](#splitting-a-long-reply)
* [Commands and routing](#commands-and-routing)
* [Structuring a larger agent](#structuring-a-larger-agent)
* [Logging](#logging)
* [Running it as a service](#running-it-as-a-service)

## Surviving a restart

Store the offset. Without it, `start="new"` silently drops whatever arrived while the process was down.

```python
from whagent import Agent, FileOffsetStore

agent = Agent(token, offset_store=FileOffsetStore("/var/lib/myagent/offset"))
```

Any object with `load()` and `save(offset)` works — see [Agent → offset persistence](agent.md#offset-persistence) for a Redis version.

## Replaying a backlog safely

`start="beginning"` replays up to 30 days — every message not yet marked read (a marked message drops out of the buffer). An agent that answers automatically will answer *all* of it. Keep a record of what you have already handled — across restarts, not just in memory:

```python
import sqlite3
from whagent import Agent

db = sqlite3.connect("handled.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS handled (wamid TEXT PRIMARY KEY)")

agent = Agent(token, start="beginning")

@agent.on_message
def once_only(ctx):
    try:
        with db:
            db.execute("INSERT INTO handled VALUES (?)", (ctx.message.id,))
    except sqlite3.IntegrityError:
        return                      # already handled in an earlier run
    handle(ctx)
```

A cheaper filter when you only care about what is recent:

```python
import time

CUTOFF = time.time() - 3600

@agent.on_message
def recent_only(ctx):
    if int(ctx.message.timestamp or 0) < CUTOFF:
        return
    handle(ctx)
```

## Work that takes longer than 25 seconds

The typing indicator clears after 25 seconds. Refresh it on a timer while the work runs:

```python
import threading
from contextlib import contextmanager

@contextmanager
def keep_typing(ctx, every=20):
    done = threading.Event()

    def refresh():
        while not done.wait(every):
            try:
                ctx.typing()
            except Exception:
                return
    thread = threading.Thread(target=refresh, daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join(timeout=1)

@agent.on_text
def slow(ctx):
    with keep_typing(ctx):
        answer = long_running_job(ctx.text)
    ctx.reply(answer)
```

Show an indicator only when a reply really is coming. Each refresh spends one of your 12 `POST /statuses` per minute — every 20 seconds is three a minute, which is fine.

## Handling messages off the poll loop

A handler runs inside the poll loop, so slow work delays the next poll. Hand it to a worker instead — while keeping **sends to one recipient sequential**, since concurrent sends have no guaranteed order:

```python
import queue
import threading

work = queue.Queue()

@agent.on_text
def enqueue(ctx):
    work.put(ctx)

def worker():
    while True:
        ctx = work.get()
        try:
            ctx.reply(expensive(ctx.text))
        except Exception:
            logging.exception("work failed")
        finally:
            work.task_done()

threading.Thread(target=worker, daemon=True).start()   # one worker == one send at a time
agent.run()
```

For several recipients in parallel, shard by `ctx.sender` — one queue and one thread per conversation — so each conversation stays ordered. And keep **one poll loop per token**, always: a second concurrent poll makes the first fail with `PollReplacedError`.

## Graceful shutdown

`run()` returns on `Ctrl-C`. For a container, stop on `SIGTERM` too — the loop checks `stop` before each poll:

```python
import signal
import threading

shutdown = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
signal.signal(signal.SIGINT, lambda *_: shutdown.set())

agent.run(stop=shutdown.is_set)
agent.close()
```

The check happens between polls, so with `timeout=25` a shutdown can take up to 25 seconds to be noticed. Lower the poll timeout if you need it snappier.

## Splitting a long reply

The cap is 4096 characters per message, and each part costs a send from your 12/minute.

```python
def chunks(text, size=4000):
    while text:
        if len(text) <= size:
            yield text
            return
        cut = text.rfind("\n", 0, size)     # prefer a line break
        cut = cut if cut > size // 2 else size
        yield text[:cut]
        text = text[cut:].lstrip("\n")

@agent.on_text
def long_answer(ctx):
    for part in chunks(build_answer(ctx.text)):
        ctx.reply(part)
```

If the content is long enough to need many parts, send a document instead:

```python
ctx.reply_document(file=report_bytes, mime_type="text/plain", filename="answer.txt")
```

## Commands and routing

`on_text` takes a regex, so commands need no parser:

```python
@agent.on_text(r"^/start\b")
def start(ctx):
    ctx.reply(f"Hi {ctx.profile_name or 'there'}!")

@agent.on_text(r"^/status\b")
def status(ctx):
    ctx.reply(f"Up since {started_at:%H:%M}")

@agent.on_text(r"^/(?!start|status)")      # any other slash command
def unknown_command(ctx):
    ctx.reply("Unknown command. Try /start or /status.")

@agent.on_text(r"^[^/]")                   # anything that isn't a command
def conversation(ctx):
    ctx.reply(answer(ctx.text))
```

Patterns are searched case-insensitively, so anchor with `^` when you mean "starts with".

## Structuring a larger agent

Keep handlers in modules and import them for their side effect of registering:

```
myagent/
    __init__.py
    bot.py          # agent = Agent(...)
    handlers/
        __init__.py # from . import commands, media, fallback
        commands.py # from myagent.bot import agent
        media.py
        fallback.py
    __main__.py     # import myagent.handlers; agent.run()
```

```python
# myagent/__main__.py
from myagent.bot import agent
import myagent.handlers          # registers everything

if __name__ == "__main__":
    agent.run()
```

Registration order is dispatch order, so `handlers/__init__.py` decides which handler sees a message first.

## Logging

The library logs through the `whagent` logger — offsets at startup, failed receipts, and any handler exception when you have no `on_error`.

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("whagent").setLevel(logging.DEBUG)
```

Never log the token, and remember that a participant identifier should not be shown to a WhatsApp user — logs are fine, your UI is not.

## Running it as a service

```ini
# /etc/systemd/system/myagent.service
[Unit]
Description=WhatsApp agent
After=network-online.target

[Service]
Type=simple
User=myagent
Environment=WHATSAPP_AGENT_TOKEN=...
WorkingDirectory=/opt/myagent
ExecStart=/opt/myagent/.venv/bin/python -m myagent
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Because the agent polls, it needs no inbound networking and no public hostname — only outbound HTTPS. Run **one instance per token**: a second one takes the poll away from the first.

Point the offset store at a path that survives restarts (`/var/lib/myagent/offset`, or a volume in a container).
