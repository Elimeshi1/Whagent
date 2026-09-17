# Errors

Every failure raises a subclass of `WhagentError`.

```
WhagentError
├── ValidationError        the library stopped the request locally (also a ValueError)
├── TransportError         no HTTP response at all — network failure, timeout
└── APIError               an error response from the API
    ├── AuthenticationError    401 / 190
    ├── InvalidRequestError    400 / 100, 131009
    │   └── MediaUploadError   400 / 131053
    ├── ForbiddenError         403 / 131005
    ├── NotFoundError          404
    │   └── MediaNotFoundError 404 / 100
    ├── RateLimitError         429 / 130429
    ├── NotDeliveredError      503 / 131016
    ├── PollReplacedError      409 / 1752041
    └── ServerError            5xx / 2
```

```python
from whagent import ForbiddenError, RateLimitError, ValidationError

try:
    client.send_text(to, body)
except ValidationError as exc:
    ...          # never left the process: bad recipient, over a length cap, bad MIME type
except ForbiddenError:
    ...          # an agent may only message its creator
except RateLimitError as exc:
    ...          # already retried; exc.retry_after is set when the API sent one
```

## What an APIError carries

| Attribute | |
|---|---|
| `status` | HTTP status |
| `code` | `error.code` — the value to branch on |
| `message` | human-readable summary; usually begins with `(#code)`, but the format is not guaranteed |
| `details` | `error.error_data.details`, when the API supplied one; wording is not guaranteed |
| `fbtrace_id` | include it in support requests |
| `error_type` | always `OAuthException`, even for errors unrelated to authentication |
| `raw` | the full error body |

Branch on `code`, never on the text of `message`.

```python
except APIError as exc:
    logger.error("send failed: code=%s status=%s trace=%s", exc.code, exc.status, exc.fbtrace_id)
```

## Error code reference

| `error.code` | HTTP | Meaning | Exception |
|---|---|---|---|
| `2` | 500 | Internal server error | `ServerError` |
| `100` | 400 | Token present but not valid; unknown media id; a length cap exceeded (then `message` is just the field name) | `InvalidRequestError` |
| `100` | 404 | Media id unknown or expired when fetching its URL | `MediaNotFoundError` |
| `190` | 401 | `Authorization` header absent or malformed | `AuthenticationError` |
| `130429` | 429 | Too many requests | `RateLimitError` |
| `131005` | 403 | Recipient is not the agent's creator, or the message being marked read was not sent by them | `ForbiddenError` |
| `131009` | 400 | Required field missing or malformed; recipient not a WhatsApp user; media type cannot be sent; media id unknown or expired | `InvalidRequestError` |
| `131016` | 503 | Not accepted for delivery | `NotDeliveredError` |
| `131053` | 400 | Media rejected at upload — over the size limit, or an unaccepted MIME type | `MediaUploadError` |
| `1752041` | 409 | A newer poll replaced this one | `PollReplacedError` |

An unknown code falls back to a class chosen by the HTTP status, so a code the platform adds later still raises something sensible.

## Two traps worth knowing

**A 401 and a 400 both mean "token".** An absent or malformed `Authorization` header is 401 + code `190`; a token that is present but *invalid* — rotated, revoked — is **400** + code `100`. If sends suddenly fail with `InvalidRequestError`, check the token before the payload.

**Code `100` is overloaded.** It covers an invalid token, an unknown media id, and a length cap. `details` — or the field name in `message` — tells them apart.

## Retries

The library retries automatically, with exponential backoff and jitter, up to `max_retries` (default 3):

| Failure | Retried? | Why |
|---|---|---|
| `429` | ✅ | Nothing was sent |
| `503` code `131016` | ✅ | Explicitly "not accepted for delivery", so not sent |
| `500` on a read or delete | ✅ | No side effect to duplicate |
| `500` on `POST /messages` | ❌ by default | **Unknown** whether the message was sent |
| Connection reset / read timeout on a send | ❌ by default | Same |
| `4xx` | ❌ | A repeat fails identically |
| `409` | ❌ | Means a second poller exists; retrying fights it |

```python
client = Client(token, retry_send_on_server_error=True)   # when a duplicate beats a loss
client = Client(token, max_retries=0)                     # do it all yourself
```

`RateLimitError.retry_after` carries the `Retry-After` header when the API sends one; the library honours it.

See [Sending messages → retrying a send](sending.md#retrying-a-send) for the full decision table.

## Local validation

`ValidationError` means the request never left the process. It fires on a recipient that isn't `user:<id>`, a text body over 4096 characters, a caption over 1024 or on a type that doesn't take one, a `reaction` send, an unaccepted MIME type, a file over its size limit, an empty file, or a media send given both `media_id=` and `file=`.

Turn it off to see exactly what the API says:

```python
client = Client(token, validate=False)
```
