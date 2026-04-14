from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings
from app.fetching.beautiful_soup_fetcher import FetchFailure, fetch_page_content
from app.models import (
    CategorizationRecord,
    CategorizerQueueMessage,
    Category,
    FetchedPage,
    FetchQueueMessage,
)
from app.utils.content import build_content_text, fingerprint_text, truncate_utf8
from app.utils.time import unix_timestamp, unix_timestamp_ms

LOGGER = logging.getLogger(__name__)


class StorageProtocol(Protocol):
    def update_wip_state(self, url_hash: str, state: str, updated_at: int) -> None: ...

    def put_categorization(self, record: CategorizationRecord) -> None: ...

    def delete_wip(self, url_hash: str) -> None: ...


class QueuePublisherProtocol(Protocol):
    def send_categorizer_job(self, message: CategorizerQueueMessage) -> None: ...


class PageFetcherProtocol(Protocol):
    def __call__(self, url: str, *, timeout: int) -> FetchedPage: ...


@dataclass
class FetchService:
    settings: Settings
    storage: StorageProtocol
    queue_publisher: QueuePublisherProtocol
    page_fetcher: PageFetcherProtocol = fetch_page_content

    def process_message(self, message: FetchQueueMessage) -> None:
        process_start = time.perf_counter()
        now = unix_timestamp()
        update_fetching_start = time.perf_counter()
        self.storage.update_wip_state(message.url_hash, "fetching", now)
        dynamodb_mark_fetching_ms = _elapsed_ms(update_fetching_start)

        try:
            fetched_page = self.page_fetcher(
                message.normalized_url,
                timeout=max(1, self.settings.fetch_total_timeout_ms // 1000),
            )
        except FetchFailure as exc:
            put_unknown_start = time.perf_counter()
            LOGGER.info(
                "fetch_failed",
                extra={
                    "url_hash": message.url_hash,
                    "trace_id": message.trace_id,
                    "error_code": exc.error_code,
                },
            )
            self.storage.put_categorization(
                self._build_unknown_record(
                    message=message,
                    now=now,
                    error_code=exc.error_code,
                    error_message=exc.message,
                    http_status=exc.status_code,
                )
            )
            dynamodb_put_unknown_ms = _elapsed_ms(put_unknown_start)

            delete_wip_start = time.perf_counter()
            self.storage.delete_wip(message.url_hash)
            dynamodb_delete_wip_ms = _elapsed_ms(delete_wip_start)

            LOGGER.info(
                "fetch_timing",
                extra={
                    "url_hash": message.url_hash,
                    "trace_id": message.trace_id,
                    "result": "fetch_failed",
                    "http_fetch_ms": 0,
                    "html_parse_ms": 0,
                    "html_extract_ms": 0,
                    "dynamodb_mark_fetching_ms": dynamodb_mark_fetching_ms,
                    "dynamodb_mark_categorizing_ms": 0,
                    "dynamodb_put_unknown_ms": dynamodb_put_unknown_ms,
                    "dynamodb_delete_wip_ms": dynamodb_delete_wip_ms,
                    "sqs_send_ms": 0,
                    "total_process_ms": _elapsed_ms(process_start),
                },
            )
            return

        page = fetched_page.page
        content = build_content_text(
            page.title,
            page.meta_description,
            page.headings,
            page.body_text,
        )
        bounded_content = truncate_utf8(content, max_bytes=self.settings.max_content_bytes)
        fingerprint = fingerprint_text(bounded_content)

        fetched_at_ms = unix_timestamp_ms()

        update_categorizing_start = time.perf_counter()
        self.storage.update_wip_state(message.url_hash, "categorizing", unix_timestamp())
        dynamodb_mark_categorizing_ms = _elapsed_ms(update_categorizing_start)

        sqs_send_start = time.perf_counter()
        self.queue_publisher.send_categorizer_job(
            CategorizerQueueMessage(
                url_hash=message.url_hash,
                normalized_url=message.normalized_url,
                trace_id=message.trace_id,
                fetched_at=fetched_at_ms // 1000,
                fetched_at_ms=fetched_at_ms,
                http_status=page.http_status,
                content_type=page.content_type,
                title=page.title,
                content=bounded_content,
                content_fingerprint=fingerprint,
            )
        )
        sqs_send_ms = _elapsed_ms(sqs_send_start)
        LOGGER.info(
            "fetch_completed",
            extra={
                "url_hash": message.url_hash,
                "trace_id": message.trace_id,
                "content_fingerprint": fingerprint,
                "fetched_at_ms": fetched_at_ms,
            },
        )
        LOGGER.info(
            "fetch_timing",
            extra={
                "url_hash": message.url_hash,
                "trace_id": message.trace_id,
                "result": "fetch_completed",
                "http_fetch_ms": fetched_page.http_fetch_ms,
                "html_parse_ms": fetched_page.html_parse_ms,
                "html_extract_ms": fetched_page.html_extract_ms,
                "dynamodb_mark_fetching_ms": dynamodb_mark_fetching_ms,
                "dynamodb_mark_categorizing_ms": dynamodb_mark_categorizing_ms,
                "dynamodb_put_unknown_ms": 0,
                "dynamodb_delete_wip_ms": 0,
                "sqs_send_ms": sqs_send_ms,
                "total_process_ms": _elapsed_ms(process_start),
            },
        )

    def _build_unknown_record(
        self,
        *,
        message: FetchQueueMessage,
        now: int,
        error_code: str,
        error_message: str,
        http_status: int | None,
    ) -> CategorizationRecord:
        return CategorizationRecord(
            url_hash=message.url_hash,
            normalized_url=message.normalized_url,
            status="unknown",
            categories=[
                Category(
                    id=self.settings.unknown_category_id,
                    name=self.settings.unknown_category_name,
                    score=1.0,
                    rank=1,
                )
            ],
            model_version=self.settings.model_version,
            first_seen_at=now,
            last_updated_at=now,
            expires_at=now + message.requested_ttl_seconds,
            trace_id=message.trace_id,
            error_code=error_code,
            error_message=error_message,
            source_http_status=http_status,
        )


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
