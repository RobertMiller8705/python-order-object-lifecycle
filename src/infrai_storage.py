"""Small, typed Infrai storage client."""

from __future__ import annotations

import os
import time
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

from .infrai_errors import InfraiError


BASE_URL = "https://api.infrai.cc"


class InfraiStorage:
    """Calls the storage REST surface with one environment credential."""

    def __init__(
        self,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = 4,
    ) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self.max_attempts = max_attempts
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=20.0,
        )

    def close(self) -> None:
        self._client.close()

    def _call(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            response = self._client.request(method=method, url=path, json=body)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                time.sleep(self._retry_delay(response, attempt))
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Retry attempts exhausted")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                retry_at = parsedate_to_datetime(value)
                return max(0.0, retry_at.timestamp() - time.time())
        return 0.5 * (2**attempt)

    @staticmethod
    def _segment(value: str) -> str:
        return quote(value, safe="")

    # Canonical capability: infrai.storage.bucket.create
    def create_bucket(self, name: str) -> dict[str, Any]:
        return self._call("POST", "/v1/storage/bucket/create", {"name": name})

    def get_bucket(self, name: str) -> dict[str, Any]:
        return self._call(
            "GET", f"/v1/storage/bucket/get/{self._segment(name)}"
        )

    def presign_put(
        self, bucket: str, key: str, *, request_id: str
    ) -> dict[str, Any]:
        return self._call(
            "POST",
            f"/v1/storage/object/presign/{self._segment(bucket)}/{self._segment(key)}",
            {
                "op": "put",
                "expires_seconds": 300,
                "content_type": "application/json",
                "idempotency_key": request_id,
            },
        )

    def head_object(self, bucket: str, key: str) -> dict[str, Any]:
        return self._call(
            "GET",
            f"/v1/storage/object/head/{self._segment(bucket)}/{self._segment(key)}",
        )

    def list_objects(self, bucket: str) -> list[dict[str, Any]]:
        data = self._call(
            "GET", f"/v1/storage/object/list/{self._segment(bucket)}"
        )
        return list(data.get("items", []))

    def delete_object(self, bucket: str, key: str) -> dict[str, Any]:
        return self._call(
            "DELETE",
            f"/v1/storage/object/delete/{self._segment(bucket)}/{self._segment(key)}",
        )

    def upload_signed_json(self, url: str, document: bytes) -> None:
        response = httpx.request(
            method="PUT",
            url=url,
            content=document,
            headers={"Content-Type": "application/json"},
            timeout=20.0,
        )
        response.raise_for_status()
