from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Category(BaseModel):
    id: str
    name: str
    score: float
    rank: int


class FetchQueueMessage(BaseModel):
    url_hash: str
    normalized_url: str
    trace_id: str
    queued_at: int
    requested_ttl_seconds: int


class CategorizerQueueMessage(BaseModel):
    url_hash: str
    normalized_url: str
    trace_id: str
    fetched_at: int
    fetched_at_ms: int | None = None
    http_status: int
    content_type: str
    title: str
    content: str
    content_fingerprint: str


class CategorizationRecord(BaseModel):
    url_hash: str
    normalized_url: str
    status: Literal["ready", "unknown", "fetch_failed"]
    categories: list[Category]
    model_version: str
    first_seen_at: int
    last_updated_at: int
    expires_at: int
    trace_id: str
    error_code: str | None = None
    error_message: str | None = None
    source_http_status: int | None = None
    source_content_type: str | None = None
    title: str | None = None
    categorizer_dequeued_at_ms: int | None = None
    categorizer_started_at_ms: int | None = None
    categorizer_finished_at_ms: int | None = None
    categorizer_queue_wait_ms: int | None = None
    categorization_compute_ms: int | None = None


class PageContent(BaseModel):
    url: str
    domain: str
    title: str
    meta_description: str
    headings: list[str]
    body_text: str
    http_status: int
    content_type: str


class FetchedPage(BaseModel):
    page: PageContent
    http_fetch_ms: int
    html_parse_ms: int
    html_extract_ms: int


class WipStateUpdate(BaseModel):
    url_hash: str
    normalized_url: str
    trace_id: str
    state: Literal["fetching", "categorizing"]
    updated_at: int
