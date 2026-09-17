# Rate limits

Each method has its own counter over a rolling 60-second window, **per agent**.

| Endpoint | Limit |
|---|---|
| `POST /messages` | 12 / minute |
| `POST /statuses` | 12 / minute |
| `GET /updates` | 15 / minute |
| `POST /media` | 12 / minute |
| `GET /media/<id>` | 12 / minute |
| `DELETE /media/<id>` | 12 / minute |

The three media methods count **separately** — 12 uploads and 12 downloads in the same minute is fine.

Exceeding a limit is HTTP 429 with `error.code` `130429`.

## The built-in limiter

On by default. Before each request the client checks that method's window and, if it is full, sleeps exactly long enough for the oldest call to age out. So a burst is paced rather than rejected:

```python
for line in lines:                  # more than 12
    client.send_text(line)          # the 13th waits, then goes
```

It is per `Client` instance and thread-safe. Turn it off if you pace requests yourself, or run several processes against one token:

```python
client = Client(token, rate_limit=False)
```

> The limiter only knows about requests **this client** made. With several clients or processes sharing one token, the platform's counter is the sum of all of them — pace them centrally, or leave the automatic 429 retry to catch the overflow.

## Living inside 12 sends a minute

A send every five seconds is the real constraint on a chatty agent. What helps:

* **One message instead of three.** Batch what you were going to send as a sequence into a single body (4096 characters is a lot).
* **A typing indicator costs a `POST /statuses`**, from a separate 12/minute budget — it doesn't eat into sends.
* **Upload once, send many.** A `media_id` can be sent repeatedly; re-uploading the same file spends the media budget for nothing.
* **Poll with `timeout=25`.** Fewer, longer polls: at 25 seconds you use about 2.4 of your 15 polls per minute.

## When you do hit 429

`RateLimitError` is retried automatically with exponential backoff and jitter, honouring `Retry-After` when the API sends one. Without one, the backoff after a 429 starts at 5 seconds (5, 10, 20). Inside the poll loop the prior offset is reused, so nothing is lost.

If you catch it yourself, back off exponentially — do not retry immediately in a tight loop.
