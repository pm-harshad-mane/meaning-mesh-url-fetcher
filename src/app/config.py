from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    aws_region: str
    url_categorization_table: str
    url_wip_table: str
    url_categorizer_queue_url: str
    fetch_connect_timeout_ms: int
    fetch_read_timeout_ms: int
    fetch_total_timeout_ms: int
    unknown_category_id: str
    unknown_category_name: str
    model_version: str
    max_content_bytes: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            url_categorization_table=os.getenv(
                "URL_CATEGORIZATION_TABLE",
                "url_categorization",
            ),
            url_wip_table=os.getenv("URL_WIP_TABLE", "url_wip"),
            url_categorizer_queue_url=os.getenv("URL_CATEGORIZER_QUEUE_URL", ""),
            fetch_connect_timeout_ms=_get_int("FETCH_CONNECT_TIMEOUT_MS", 2000),
            fetch_read_timeout_ms=_get_int("FETCH_READ_TIMEOUT_MS", 7000),
            fetch_total_timeout_ms=_get_int("FETCH_TOTAL_TIMEOUT_MS", 9000),
            unknown_category_id=os.getenv("UNKNOWN_CATEGORY_ID", "UNKNOWN"),
            unknown_category_name=os.getenv("UNKNOWN_CATEGORY_NAME", "Unknown"),
            model_version=os.getenv(
                "MODEL_VERSION",
                "bge-base-en-v1.5__bge-reranker-v2-m3",
            ),
            max_content_bytes=150 * 1024,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
