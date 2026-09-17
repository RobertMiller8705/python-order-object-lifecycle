"""HTTP boundary for creating and expiring short-lived order objects."""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException

from .infrai_errors import InfraiError
from .infrai_storage import InfraiStorage
from .order_lifecycle import CheckoutRequest, CheckoutResult, CleanupResult, OrderLifecycle


app = FastAPI(title="Order object lifecycle")


@lru_cache(maxsize=1)
def lifecycle() -> OrderLifecycle:
    storage = InfraiStorage()
    bucket = os.environ.get("ORDER_OBJECT_BUCKET", "private-order-transients")
    return OrderLifecycle(storage, bucket)


@app.post("/checkouts", response_model=CheckoutResult, status_code=201)
def create_checkout(
    request: CheckoutRequest, manager: OrderLifecycle = Depends(lifecycle)
) -> CheckoutResult:
    try:
        return manager.record_checkout(request)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc.detail.get("message", "rejected"))},
        ) from exc


@app.post("/maintenance/expire", response_model=CleanupResult)
def expire_order_objects(
    manager: OrderLifecycle = Depends(lifecycle),
) -> CleanupResult:
    try:
        return manager.expire_objects()
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc.detail.get("message", "rejected"))},
        ) from exc
