from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.fetching.beautiful_soup_fetcher import FetchFailure
from app.models import CategorizerQueueMessage, FetchQueueMessage, PageContent
from app.services.fetch_service import FetchService


class FakeStorage:
    def __init__(self) -> None:
        self.state_updates: list[tuple[str, str]] = []
        self.records = []
        self.deleted = []

    def update_wip_state(self, url_hash: str, state: str, updated_at: int) -> None:
        self.state_updates.append((url_hash, state))

    def put_categorization(self, record) -> None:
        self.records.append(record)

    def delete_wip(self, url_hash: str) -> None:
        self.deleted.append(url_hash)


@dataclass
class FakePublisher:
    messages: list[CategorizerQueueMessage]

    def send_categorizer_job(self, message: CategorizerQueueMessage) -> None:
        self.messages.append(message)


def _settings() -> Settings:
    return Settings(
        aws_region="us-east-1",
        url_categorization_table="url_categorization",
        url_wip_table="url_wip",
        url_categorizer_queue_url="https://example.com/queue",
        fetch_connect_timeout_ms=2000,
        fetch_read_timeout_ms=7000,
        fetch_total_timeout_ms=9000,
        unknown_category_id="UNKNOWN",
        unknown_category_name="Unknown",
        model_version="bge-base-en-v1.5__bge-reranker-v2-m3",
        max_content_bytes=64,
        log_level="INFO",
    )


def test_process_message_writes_unknown_on_fetch_failure() -> None:
    storage = FakeStorage()
    publisher = FakePublisher(messages=[])
    service = FetchService(
        settings=_settings(),
        storage=storage,
        queue_publisher=publisher,
        page_fetcher=_raising_fetcher,
    )

    service.process_message(_message())

    assert storage.state_updates[0][1] == "fetching"
    assert len(storage.records) == 1
    assert storage.records[0].status == "unknown"
    assert storage.deleted == ["sha256:test"]
    assert publisher.messages == []


def test_process_message_enqueues_categorizer_job_on_success() -> None:
    storage = FakeStorage()
    publisher = FakePublisher(messages=[])
    service = FetchService(
        settings=_settings(),
        storage=storage,
        queue_publisher=publisher,
        page_fetcher=_successful_fetcher,
    )

    service.process_message(_message())

    assert storage.state_updates[0][1] == "fetching"
    assert storage.state_updates[1][1] == "categorizing"
    assert storage.records == []
    assert storage.deleted == []
    assert len(publisher.messages) == 1
    assert publisher.messages[0].content


def _message() -> FetchQueueMessage:
    return FetchQueueMessage(
        url_hash="sha256:test",
        normalized_url="https://example.com/article",
        trace_id="trace-123",
        queued_at=100,
        requested_ttl_seconds=2_592_000,
    )


def _raising_fetcher(url: str, *, timeout: int) -> PageContent:
    raise FetchFailure(
        error_code="FETCH_TIMEOUT",
        message="timed out",
        retryable=True,
    )


def _successful_fetcher(url: str, *, timeout: int) -> PageContent:
    return PageContent(
        url=url,
        domain="example.com",
        title="Example title",
        meta_description="Example meta description",
        headings=["Heading 1", "Heading 2"],
        body_text="A" * 200,
        http_status=200,
        content_type="text/html",
    )
