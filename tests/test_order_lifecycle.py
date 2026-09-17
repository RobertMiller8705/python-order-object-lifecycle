from datetime import UTC, datetime

from src.order_lifecycle import ObjectKind, OrderLifecycle, expiry_key


class RecordingStorage:
    def __init__(self, items: list[dict[str, str]], missing: set[str]) -> None:
        self.items = items
        self.missing = missing
        self.deleted: list[str] = []

    def get_bucket(self, bucket: str) -> dict[str, bool]:
        return {"found": True}

    def create_bucket(self, name: str) -> dict[str, bool]:
        return {"created": True}

    def list_objects(self, bucket: str) -> list[dict[str, str]]:
        return self.items

    def head_object(self, bucket: str, key: str) -> dict[str, bool]:
        return {"found": key not in self.missing}

    def delete_object(self, bucket: str, key: str) -> dict[str, bool]:
        self.deleted.append(key)
        return {"deleted": True}


def test_cleanup_deletes_only_expired_objects_that_still_exist() -> None:
    now = datetime(2026, 9, 3, 12, tzinfo=UTC)
    expired = expiry_key(ObjectKind.CHECKOUT, "ord-7", datetime(2026, 9, 3, 11, tzinfo=UTC))
    missing = expiry_key(ObjectKind.RECEIPT, "ord-7", datetime(2026, 9, 3, 10, tzinfo=UTC))
    active = expiry_key(ObjectKind.FULFILLMENT, "ord-7", datetime(2026, 9, 3, 13, tzinfo=UTC))
    permanent = "orders/ord-7/audit.json"
    storage = RecordingStorage(
        [{"key": expired}, {"key": missing}, {"key": active}, {"key": permanent}],
        {missing},
    )

    result = OrderLifecycle(storage, "orders", clock=lambda: now).expire_objects()

    assert result.examined == 4
    assert result.deleted == [expired]
    assert storage.deleted == [expired]
