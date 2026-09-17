"""Errors shared by the HTTP client and service boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"

