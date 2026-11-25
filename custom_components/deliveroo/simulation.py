"""Demo order: replay a full delivery without contacting Deliveroo.

The payload has the same shape as a real ``consumer_order_statuses`` document
(modelled on a real order), so it goes through the normal parser and drives
the same sensors and events. This module must not import Home Assistant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

DEMO_ORDER_ID = "demo"

# Progress percentage at which each of Deliveroo's five steps ends.
STEP_ENDS = (10, 30, 70, 90, 100)

_TEXT: dict[str, dict[str, Any]] = {
    "it": {
        "restaurant": "Trattoria Demo",
        "steps": (
            "Ordine inviato",
            "Attesa conferma",
            "In preparazione",
            "In transito",
            "Il tuo rider è vicino!",
        ),
        "messages": (
            "Abbiamo inviato il tuo ordine a Trattoria Demo",
            "Trattoria Demo sta confermando il tuo ordine",
            "Trattoria Demo sta preparando il tuo ordine",
            "Il tuo ordine è stato ritirato",
            "Il rider sta arrivando da te",
        ),
        "advisory": "Il rider ha un altro ordine da consegnare lungo il tragitto e sarà presto da te.",
        "done": "Il tuo ordine è arrivato. Buon appetito!",
        "eta_status": "In orario",
    },
    "en": {
        "restaurant": "Demo Kitchen",
        "steps": (
            "Order sent",
            "Awaiting confirmation",
            "Preparing",
            "In transit",
            "Your rider is nearby!",
        ),
        "messages": (
            "We've sent your order to Demo Kitchen",
            "Demo Kitchen is confirming your order",
            "Demo Kitchen is preparing your order",
            "Your order has been picked up",
            "Your rider is arriving",
        ),
        "advisory": "Your rider has another order to deliver on the way and will be with you soon.",
        "done": "Your order has arrived. Enjoy!",
        "eta_status": "On time",
    },
}


def build_demo_payload(
    elapsed: float,
    duration: float,
    *,
    lang: str,
    start_local: datetime,
    home: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Return the status document of the demo order ``elapsed`` seconds in.

    The five steps get an equal share of ``duration``; once it is over the
    order is completed. With ``home`` (latitude, longitude) the demo also has
    map points: the restaurant about 1.5 km away, the delivery address at home
    and a rider who rides to the restaurant, then home.
    """
    text = _TEXT.get(lang, _TEXT["en"])
    fraction = max(0.0, elapsed / duration) if duration > 0 else 1.0
    completed = fraction >= 1.0

    position = min(fraction, 0.999999) * len(STEP_ENDS)
    step = int(position)
    step_start = STEP_ENDS[step - 1] if step else 0
    progress = round(step_start + (position - step) * (STEP_ENDS[step] - step_start))

    delivery = start_local + timedelta(seconds=duration)
    window_end = delivery + timedelta(minutes=10)

    attributes: dict[str, Any] = {
        "ui_status": "COMPLETED" if completed else "PROCESSING",
        "message": text["done"] if completed else text["messages"][step],
        "eta_message": f"{delivery:%H:%M}–{window_end:%H:%M}",
        "eta_status": text["eta_status"],
        "eta_status_code": "ON_TIME",
        "current_progress_percentage": 100 if completed else progress,
        "rider_route": "TO_CUSTOMER" if completed or step >= 3 else "TO_RESTAURANT",
        "rider_validation_code_s": "12",
        "is_completed": completed,
        "is_failed": False,
        "processing_steps": [
            {
                "title": title,
                "ends_at_progress_percentage": STEP_ENDS[index],
                "is_current": not completed and index == step,
            }
            for index, title in enumerate(text["steps"])
        ],
        "analytics": {
            "estimated_delivery_time": delivery.astimezone(UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "rider_status": "en-route",
        },
        "updated_at": f"{start_local + timedelta(seconds=elapsed):%Y-%m-%d %H:%M:%S %z}",
    }
    if not completed and step == 3:
        attributes["advisory"] = text["advisory"]

    included: list[dict[str, Any]] = [
        {
            "type": "order",
            "attributes": {
                "order_number": "0000",
                "restaurant_name": text["restaurant"],
            },
        }
    ]
    if home is not None:
        included.extend(_demo_map(home, fraction, completed))

    return {
        "data": {"type": "consumer_order_status", "attributes": attributes},
        "included": included,
    }


# The restaurant is this far (degrees) north-east of home, the rider starts
# this far south-east of the restaurant.
_RESTAURANT_OFFSET = (0.010, 0.012)
_RIDER_START_OFFSET = (-0.004, 0.006)


def _point(lat: float, lon: float) -> dict[str, float]:
    return {"lat": round(lat, 6), "lng": round(lon, 6)}


def _between(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    t = min(max(t, 0.0), 1.0)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _demo_map(
    home: tuple[float, float], fraction: float, completed: bool
) -> list[dict[str, Any]]:
    """Map points of the demo order at ``fraction`` of its duration."""
    restaurant = (home[0] + _RESTAURANT_OFFSET[0], home[1] + _RESTAURANT_OFFSET[1])
    start = (restaurant[0] + _RIDER_START_OFFSET[0], restaurant[1] + _RIDER_START_OFFSET[1])
    # Steps 1-3 (60 %): the rider rides to the restaurant; 4-5: to the customer.
    if completed:
        rider = home
    elif fraction < 0.6:
        rider = _between(start, restaurant, fraction / 0.6)
    else:
        rider = _between(restaurant, home, (fraction - 0.6) / 0.4)
    return [
        {"type": "restaurant", "attributes": {"location": _point(*restaurant)}},
        {"type": "customer", "attributes": {"location": _point(*home)}},
        {"type": "rider", "attributes": {"location": _point(*rider)}},
    ]
