"""Checkout object creation and deterministic expiry decisions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

class ObjectKind(str, Enum):
    CHECKOUT = "checkout"
    FULFILLMENT = "fulfillment"
    RECEIPT = "receipt"
    CUSTOMER_UPDATE = "customer-update"


class CheckoutRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=80)
    customer_reference: str = Field(min_length=1, max_length=80)
    item_skus: list[str] = Field(min_length=1, max_length=50)
    ttl_hours: int = Field(default=24, ge=1, le=168)


class StoredObject(BaseModel):
    kind: ObjectKind
    key: str
    expires_at: datetime


class CheckoutResult(BaseModel):
    order_id: str
    objects: list[StoredObject]


class CleanupResult(BaseModel):
    examined: int
    deleted: list[str]


def expiry_key(kind: ObjectKind, order_id: str, expires_at: datetime) -> str:
    stamp = int(expires_at.timestamp())
    return f"orders/{order_id}/expires-{stamp}/{kind.value}.json"


def expiry_from_key(key: str) -> datetime | None:
    for part in key.split("/"):
        if part.startswith("expires-"):
            value = part.removeprefix("expires-")
            if value.isdigit():
                return datetime.fromtimestamp(int(value), tz=UTC)
    return None


class OrderLifecycle:
    def __init__(
        self,
        storage: Any,
        bucket: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.storage = storage
        self.bucket = bucket
        self.clock = clock
        self._bucket_ready = False

    def ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        self.storage.get_bucket(self.bucket)
        self._bucket_ready = True

    def record_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        self.ensure_bucket()
        expires_at = self.clock() + timedelta(hours=request.ttl_hours)
        stored: list[StoredObject] = []
        for kind in ObjectKind:
            key = expiry_key(kind, request.order_id, expires_at)
            document = {
                "kind": kind.value,
                "order_id": request.order_id,
                "customer_reference": request.customer_reference,
                "item_skus": request.item_skus,
                "expires_at": expires_at.isoformat(),
            }
            signed = self.storage.presign_put(
                self.bucket, key, request_id=f"{request.order_id}:{kind.value}"
            )
            self.storage.upload_signed_json(
                signed["url"],
                json.dumps(document, separators=(",", ":")).encode("utf-8"),
            )
            stored.append(StoredObject(kind=kind, key=key, expires_at=expires_at))
        return CheckoutResult(order_id=request.order_id, objects=stored)

    def expire_objects(self) -> CleanupResult:
        self.ensure_bucket()
        now = self.clock()
        items = self.storage.list_objects(self.bucket)
        deleted: list[str] = []
        for item in items:
            key = str(item["key"])
            expires_at = expiry_from_key(key)
            if expires_at is None or expires_at > now:
                continue
            head = self.storage.head_object(self.bucket, key)
            if head.get("found"):
                self.storage.delete_object(self.bucket, key)
                deleted.append(key)
        return CleanupResult(examined=len(items), deleted=deleted)
