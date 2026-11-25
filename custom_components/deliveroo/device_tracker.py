"""Map entities for Deliveroo: rider, delivery address and restaurant.

They have coordinates only while an order is tracked and Deliveroo sends them,
so a map card (or a popup with one) can show where the order is.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DeliverooLocation, DeliverooOrderStatus
from .coordinator import DeliverooConfigEntry, DeliverooCoordinator
from .entity import DeliverooEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DeliverooTrackerDescription(EntityDescription):
    """Describes a point of the order on the map."""

    location_fn: Callable[[DeliverooOrderStatus], DeliverooLocation | None]


TRACKERS: tuple[DeliverooTrackerDescription, ...] = (
    DeliverooTrackerDescription(
        key="rider_location",
        translation_key="rider_location",
        icon="mdi:moped",
        location_fn=lambda s: s.rider_location,
    ),
    DeliverooTrackerDescription(
        key="delivery_location",
        translation_key="delivery_location",
        icon="mdi:home-map-marker",
        location_fn=lambda s: s.delivery_location,
    ),
    DeliverooTrackerDescription(
        key="restaurant_location",
        translation_key="restaurant_location",
        icon="mdi:silverware-fork-knife",
        location_fn=lambda s: s.restaurant_location,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeliverooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Deliveroo map entities."""
    coordinator = entry.runtime_data
    async_add_entities(DeliverooTracker(coordinator, desc) for desc in TRACKERS)


class DeliverooTracker(DeliverooEntity, TrackerEntity):
    """One point of the current order on the map."""

    entity_description: DeliverooTrackerDescription
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: DeliverooCoordinator,
        description: DeliverooTrackerDescription,
    ) -> None:
        """Initialise the tracker."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def _location(self) -> DeliverooLocation | None:
        status = self.coordinator.data.status
        return None if status is None else self.entity_description.location_fn(status)

    @property
    def latitude(self) -> float | None:
        """Latitude of the point, if Deliveroo sent one."""
        location = self._location
        return location.latitude if location else None

    @property
    def longitude(self) -> float | None:
        """Longitude of the point, if Deliveroo sent one."""
        location = self._location
        return location.longitude if location else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Link to Deliveroo's own tracking page, when known."""
        status = self.coordinator.data.status
        if status is None:
            return None
        return {"order_id": status.order_id, "tracking_url": status.tracking_url}
