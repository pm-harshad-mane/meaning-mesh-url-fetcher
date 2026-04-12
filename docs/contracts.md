# Fetcher Contracts

Input queue: `url_fetcher_service_queue`

```json
{
  "url_hash": "sha256:...",
  "normalized_url": "https://example.com/page",
  "trace_id": "trace-...",
  "queued_at": 1775862000,
  "requested_ttl_seconds": 2592000
}
```

Successful output queue: `url_categorizer_service_queue`

```json
{
  "url_hash": "sha256:...",
  "normalized_url": "https://example.com/page",
  "trace_id": "trace-...",
  "fetched_at": 1775862008,
  "http_status": 200,
  "content_type": "text/html",
  "title": "Page title",
  "content": "Extracted text content",
  "content_fingerprint": "xxh3:..."
}
```

The `content` field is capped at 150 KB encoded as UTF-8.
