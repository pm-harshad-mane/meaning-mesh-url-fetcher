from __future__ import annotations

from typing import Any

import boto3

from app.models import CategorizationRecord


class DynamoStorage:
    def __init__(
        self,
        categorization_table_name: str,
        wip_table_name: str,
        *,
        region_name: str,
    ) -> None:
        dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self._categorization_table = dynamodb.Table(categorization_table_name)
        self._wip_table = dynamodb.Table(wip_table_name)

    def update_wip_state(self, url_hash: str, state: str, updated_at: int) -> None:
        self._wip_table.update_item(
            Key={"url_hash": url_hash},
            UpdateExpression="SET #state = :state, updated_at = :updated_at",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={":state": state, ":updated_at": updated_at},
        )

    def put_categorization(self, record: CategorizationRecord) -> None:
        self._categorization_table.put_item(Item=record.model_dump())

    def delete_wip(self, url_hash: str) -> None:
        self._wip_table.delete_item(Key={"url_hash": url_hash})
