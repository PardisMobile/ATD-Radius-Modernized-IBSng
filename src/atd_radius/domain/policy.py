from collections.abc import Mapping
from typing import Any


ATTRIBUTE_PRECEDENCE = ("ras", "group", "service", "user")


def effective_attributes(*layers: Mapping[str, Any]) -> dict[str, Any]:
    """Merge attributes in IBSng-style layered policy order.

    Later layers override earlier layers. The explicit order is kept in one
    place so RADIUS, REST, XML-RPC and the UI use identical policy semantics.
    """
    result: dict[str, Any] = {}
    for layer in layers:
        result.update(layer)
    return result
