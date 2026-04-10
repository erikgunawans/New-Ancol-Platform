"""Base integration adapter interface.

All external system integrations implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class IntegrationAdapter(ABC):
    """Abstract base class for external system integrations."""

    @abstractmethod
    async def health_check(self) -> dict:
        """Check if the external system is reachable."""

    @abstractmethod
    async def sync(self, since: datetime | None = None) -> dict:
        """Pull data from the external system."""

    @abstractmethod
    async def push(self, data: Any) -> dict:
        """Push data to the external system."""
