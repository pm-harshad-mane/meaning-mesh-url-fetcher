from __future__ import annotations

import json
import logging
from typing import Any

from app.adapters.dynamodb import DynamoStorage
from app.adapters.queue import SqsQueuePublisher
from app.config import Settings
from app.logging import configure_logging
from app.models import FetchQueueMessage
from app.services.fetch_service import FetchService

LOGGER = logging.getLogger(__name__)
SETTINGS = Settings.from_env()
configure_logging(SETTINGS.log_level)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    service = FetchService(
        settings=SETTINGS,
        storage=DynamoStorage(
            SETTINGS.url_categorization_table,
            SETTINGS.url_wip_table,
            region_name=SETTINGS.aws_region,
        ),
        queue_publisher=SqsQueuePublisher(
            SETTINGS.url_categorizer_queue_url,
            region_name=SETTINGS.aws_region,
        ),
    )

    records = event.get("Records", [])
    for record in records:
        payload = json.loads(record["body"])
        message = FetchQueueMessage.model_validate(payload)
        service.process_message(message)

    LOGGER.info("fetch_batch_processed", extra={"record_count": len(records)})
    return {"batchItemFailures": []}
