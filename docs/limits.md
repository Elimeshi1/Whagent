# Limits and formats

Everything the platform caps, and everything it accepts. The library checks all of it before a request leaves (`validate=True`, the default).

```python
from whagent import TEXT_BODY_MAX, CAPTION_MAX, SIZE_LIMITS, ACCEPTED_MIME_TYPES
from whagent.limits import size_limit_for, category_for
```

## Text

| | |
|---|---|
| Message body | 4096 characters |
| Caption | 1024 characters |
| Captions available on | `image`, `video`, `document` |
| Filename available on | `document` |

Exceeding either is 400 + code `100`, where `error.message` is just the field name.

## Size limits

| Category | Limit |
|---|---|
| Image | 5 MB |
| Sticker | 500 KB |
| Video, audio, document, generic binary | 16 MB |

Over the limit is 400 + code `131053`; `error_data.details` reports the actual size against the limit.

## Accepted MIME types

Anything outside this list is rejected at upload with 400 + code `131053`.

### Image — 5 MB

| Format | Extension | MIME type | Notes |
|---|---|---|---|
| JPEG | `.jpg`, `.jpeg` | `image/jpeg` | preferred for photographs |
| PNG | `.png` | `image/png` | preferred for graphics with transparency |

8-bit, RGB or RGBA. Keep the total pixel count at or below **25 megapixels** (5000 × 5000, or an equivalent area).

### Video — 16 MB

| Format | Extension | MIME type |
|---|---|---|
| MP4 | `.mp4` | `video/mp4` (preferred container) |
| 3GPP | `.3gp` | `video/3gpp` |

**H.264** video and **AAC** audio, with one audio stream or none. For the widest playback compatibility target the H.264 **Baseline** profile, or **Main** without B-frames. Write the `moov` atom ahead of `mdat` so playback can start before the download finishes:

```bash
ffmpeg -i in.mov -c:v libx264 -profile:v baseline -c:a aac -movflags +faststart out.mp4
```

### Audio — 16 MB

| Format | Extension | MIME type | Notes |
|---|---|---|---|
| AAC | `.aac` | `audio/aac` | ADTS stream |
| MP4 audio | `.m4a` | `audio/mp4` | AAC in an MPEG-4 container |
| MP3 | `.mp3` | `audio/mpeg` | |
| AMR-NB | `.amr` | `audio/amr` | AMR-NB only |
| Opus in Ogg | `.ogg` | `audio/ogg` | mono input only |
| Opus | `.opus` | `audio/opus` | stored as `audio/ogg; codecs=opus` |

Only Opus is supported in Ogg. Audio you send is delivered as a plain attachment — voice notes are something you receive, not something you send.

### Document — 16 MB

| Format | Extension | MIME type |
|---|---|---|
| PDF | `.pdf` | `application/pdf` |
| Plain text | `.txt` | `text/plain` |
| Word | `.doc` | `application/msword` |
| Word | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| Excel | `.xls` | `application/vnd.ms-excel` |
| Excel | `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| PowerPoint | `.ppt` | `application/vnd.ms-powerpoint` |
| PowerPoint | `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |

Set `filename` to the file's name **including its extension**.

### Sticker — 500 KB

| Format | Extension | MIME type |
|---|---|---|
| WebP | `.webp` | `image/webp` |

512 × 512 is the conventional size; the canvas must be at most 4096 × 4096. Static or animated when sending; stickers you receive are static. Captions are not available on stickers.

### Generic binary — 16 MB

`application/octet-stream`, for a file that fits none of the above.

## Message types

| | |
|---|---|
| Send | `text`, `image`, `audio`, `video`, `document`, `sticker` |
| Receive | those, plus `reaction` |

Reactions are **receive-only**; sending one raises `ValidationError` locally and is a 400 from the API.

## Retention

| | |
|---|---|
| Buffered updates | 30 days from when they are stored |
| Uploaded and received media | 30 days |

A message you mark as read is removed before that: it is no longer returned by a poll at an earlier offset. Receipts are kept for the full 30 days.

## Polling

| | Default | Range |
|---|---|---|
| `limit` | 50 | ≤ 100 |
| `timeout` | 15 s | 0–25 s |
| `offset` | head at request time | ≥ 0 |

Out-of-range values are adjusted, not rejected. Only a non-integer is a 400.

## Other

| | |
|---|---|
| Typing indicator | clears on reply, or after 25 seconds |
| Rate limits | [see Rate limits](rate-limits.md) |
