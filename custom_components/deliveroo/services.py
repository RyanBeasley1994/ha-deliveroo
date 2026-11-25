"""Actions for Deliveroo."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, SERVICE_GET_ORDER_MAP
from .coordinator import DeliverooConfigEntry
from .simulation import DEMO_ORDER_ID

SCHEMA_GET_ORDER_MAP = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


def _entry(hass: HomeAssistant, call: ServiceCall) -> DeliverooConfigEntry:
    """The entry named in the call, or the only loaded one."""
    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id:
        for entry in loaded:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )
    if len(loaded) == 1:
        return loaded[0]
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="entry_required" if loaded else "no_entries",
    )


def _osm_link(lat: float, lon: float) -> str:
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"


async def _async_get_order_map(call: ServiceCall) -> ServiceResponse:
    """Return where the current order is: map points and tracking page."""
    data = _entry(call.hass, call).runtime_data.data
    status = data.status if data else None
    if status is None:
        return {"active": False, "order_id": None, "has_location": False}

    def point(location: Any) -> dict[str, float] | None:
        return location.as_dict() if location else None

    focus = status.rider_location or status.delivery_location or status.restaurant_location
    return {
        "active": data.active_order_id is not None,
        "order_id": status.order_id,
        "simulated": status.order_id == DEMO_ORDER_ID,
        "restaurant": status.restaurant_name,
        "step": status.step_title,
        "eta": status.eta,
        "rider_route": status.rider_route,
        "tracking_url": status.tracking_url,
        "has_location": status.has_location,
        "rider_location": point(status.rider_location),
        "delivery_location": point(status.delivery_location),
        "restaurant_location": point(status.restaurant_location),
        "map_url": _osm_link(focus.latitude, focus.longitude) if focus else None,
    }


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ORDER_MAP,
        _async_get_order_map,
        schema=SCHEMA_GET_ORDER_MAP,
        supports_response=SupportsResponse.ONLY,
    )
