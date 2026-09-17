# Files and media

`POST` / `GET` / `DELETE /agent/v1/media`

Media never travels inside a message. You upload bytes and get an id; a message references that id. Inbound media is the same in reverse.

```python
media_id = client.upload_media("invoice.pdf")
client.send_document(to, media_id=media_id, filename="invoice.pdf")
```

Uploaded media expires after **30 days**.

## Uploading

```python
client.upload_media(file, mime_type=None, filename=None) -> str
```

`file` can be a path, raw `bytes`, or an open binary file object:

```python
client.upload_media("photo.jpg")                                    # type guessed from the name
client.upload_media(Path("report.pdf"))
client.upload_media(png_bytes, mime_type="image/png", filename="chart.png")
client.upload_media(open("clip.mp4", "rb"))
```

The MIME type is guessed from the filename when you don't pass one. When it can't be guessed, the library raises `ValidationError` rather than letting the API reject the upload — pass `mime_type=` explicitly.

Before uploading it also checks the type is [accepted](limits.md#accepted-mime-types) and the file is within [the size cap for its category](limits.md#size-limits). Both are 400 + code `131053` from the API, with `error_data.details` reporting the actual size against the limit.

### Sending in one step

Every media send accepts `file=` and does the upload for you:

```python
client.send_image(to, file="cat.jpg", caption="look at this")
ctx.reply_document(file="report.pdf", caption="Today's report")
```

Upload once and reuse the id when you send the same file repeatedly — each upload counts against the media rate limit, and each one stores a new object.

## Downloading

An inbound media message carries an id, not bytes:

```python
@agent.on_media
def save(ctx):
    media = ctx.message.media
    media.id            # "998a7c17-..."
    media.mime_type     # "image/jpeg"
    media.sha256        # Base64 of the SHA-256 digest
    media.filename      # documents only
    media.caption       # image / video / document
    media.voice         # True on a voice note
```

Fetch the bytes in one call:

```python
data = ctx.download()                     # bytes
path = ctx.download("/tmp/photo.jpg")     # writes, returns the path
ctx.download(open("/tmp/photo.jpg", "wb"))  # any writable binary file object
```

`Client.download_media(media_id, dest=None)` is the same thing outside a handler. It is two HTTP requests: `GET /media/<id>` for metadata, then a fetch of the returned `url` with your token in the `Authorization` header. Streaming to a path keeps a 16 MB video out of memory.

### Metadata only

```python
media = client.get_media(media_id)
media.url         # https://lookaside.fbsbx.com/agent/v1/media/<id>/content
media.mime_type   # application/pdf
media.sha256      # hex digest — the inbound payload has Base64 of the same digest
media.file_size   # 232145
```

Use it to check a size before downloading. To fetch a URL you already hold, `client.download_url(url, dest)`.

> The two digests describe the same bytes in different encodings. To compare them:
> ```python
> import base64
> base64.b64decode(message.media.sha256).hex() == client.get_media(media.id).sha256
> ```

## Deleting

```python
client.delete_media(media_id)   # -> True
```

Works on media you uploaded and on media that was sent to you. An unknown, expired or already-deleted id — or one belonging to another agent — is 400 + code `100`.

Deleting what you no longer need is good hygiene when you handle a lot of files; everything expires after 30 days regardless.

## What can go wrong

| Code | Meaning |
|---|---|
| 400 + `131009` | `messaging_product` or `file` missing from the upload |
| 400 + `131053` | Over the size limit for its type, or a MIME type that is not accepted |
| 400 + `100` | Unknown, expired, deleted, malformed, or another agent's id (on `GET`/`DELETE`) |
| 404 + `100` | The id is unknown or expired when fetching the `url` → `MediaNotFoundError` |
| 429 | More than 12 requests per minute **to a single media method** — each has its own counter |

An expired media id is not recoverable: ask the sender to send the file again, or upload it again yourself.
