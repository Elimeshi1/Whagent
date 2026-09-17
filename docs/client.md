# Client

`Client` is one method per endpoint, plus the plumbing: authentication, retries, rate limiting, local validation and typed responses.

```python
from whagent import Client

with Client("<ACCESS_TOKEN>") as client:
    client.send_text("user:50972923564215", "Hello!")
```

## Construction

```python
Client(
    token,
    base_url="https://api.whatsapp.com/agent/v1",
    timeout=30.0,
    max_retries=3,
    backoff_base=0.5,
    backoff_max=30.0,
    rate_limit=True,
    retry_send_on_server_error=False,
    validate=True,
    session=None,
    user_agent=None,
)
```

| Argument | What it does |
|---|---|
| `token` | The agent's API token. Sent as `Authorization: Bearer <token>`. |
| `base_url` | Override the API root — useful for tests and proxies. |
| `timeout` | Read timeout in seconds. Polls extend it past the long-poll window automatically, so an ordinary delay never looks like a failure. |
| `max_retries` | Retries after a *retryable* failure. See [Errors → retries](errors.md#retries). |
| `backoff_base`, `backoff_max` | Exponential backoff bounds, in seconds. Jitter is added. |
| `rate_limit` | Pace requests to stay inside the documented caps instead of collecting 429s. See [Rate limits](rate-limits.md). |
| `retry_send_on_server_error` | Retry a send after a 500 or a dropped connection. **Off by default** — those leave delivery unknown, so a retry may send twice. |
| `validate` | Local checks on recipients, length caps, MIME types and media sizes before a request leaves. |
| `session` | Bring your own `requests.Session` for connection reuse, proxies or custom TLS. |
| `user_agent` | Override the `User-Agent` header. |

## Methods

### Messages — [`POST /messages`](sending.md)

| | |
|---|---|
| `send_text(to, body, preview_url=False, reply_to=None)` | → [`SendResult`](models.md#sendresult) |
| `send_image(to, media_id=\| file=, mime_type=None, caption=None, reply_to=None)` | |
| `send_video(...)`, `send_audio(...)`, `send_sticker(...)` | |
| `send_document(..., filename=None)` | |
| `send_message(to, type, payload, reply_to=None)` | any payload shape |
| `reply(message, body, **kwargs)` | text back to a `Message`'s sender, quoting it |

### Updates — [`GET /updates`](receiving.md)

| | |
|---|---|
| `get_updates(offset=None, limit=50, timeout=15)` | → [`Update`](models.md#update) or `None` on a 204 |
| `poll_updates(offset=None, limit=50, timeout=15, on_offset=None, max_polls=None, stop=None)` | generator of non-empty `Update`s, tracking the offset |

### Receipts — [`POST /statuses`](receipts.md)

| | |
|---|---|
| `mark_read(message_id, typing=False)` | → `bool` |
| `send_typing(message_id)` | mark read **and** show the indicator |

### Media — [`POST` / `GET` / `DELETE /media`](media.md)

| | |
|---|---|
| `upload_media(file, mime_type=None, filename=None)` | → media id |
| `get_media(media_id)` | → [`Media`](models.md#media) metadata |
| `download_media(media_id, dest=None)` | → `bytes`, or the destination it wrote to |
| `download_url(url, dest=None)` | fetch a media URL directly, authenticated |
| `delete_media(media_id)` | → `bool` |

## Lifecycle

`Client` opens a `requests.Session` and reuses the connection. Close it when you're done — or use the context manager, which closes only a session the client created:

```python
with Client(token) as client:
    ...
```

A session you passed in is left open for you to manage.

## Threads

A `Client` is safe to share across threads: `requests.Session` is thread-safe for this usage, and the rate limiter takes a lock. Two rules from the platform still apply:

* **One poll at a time per agent** — a second concurrent `get_updates` makes the first fail with [`PollReplacedError`](errors.md).
* **No concurrent sends to the same recipient** — ordering between them is not guaranteed.

See [Recipes → handling messages in a worker thread](recipes.md#handling-messages-off-the-poll-loop).

## Turning the helpers off

The library validates before sending because a round trip to learn that a caption is 1025 characters is a slow way to find out. If you would rather see exactly what the API says:

```python
client = Client(token, validate=False, rate_limit=False, max_retries=0)
```
