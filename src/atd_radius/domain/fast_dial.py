"""Source-shaped runtime helper for the IBSng A1.24 fast-dial VoIP plugin.

This module models only the plugin's called-number rewrite and redirect side
effects. It is intentionally independent of RADIUS Access-Accept attributes:
A1.24 mutates the VoIP/RAS message and asks the RAS implementation to set the
redirect-number reply.
"""
from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from typing import Callable


class FastDialRuntimeError(ValueError):
    """A1.24-compatible invalid fast-dial index failure."""


def apply_fast_dial(
    *,
    called_number: str | None,
    prefix: str,
    destinations: Sequence[str],
    instance_attributes: MutableMapping[str, object],
    set_redirect_number: Callable[[str], None],
) -> str | None:
    """Apply the A1.24 fast-dial plugin to one VoIP login/update message.

    Returns the selected destination when a redirect occurs, otherwise None.
    Deliberately preserves the source's integer/list-index behavior: negative
    indices are accepted by Python list indexing, while positive out-of-range
    indices raise FastDialRuntimeError. Do not add a 0..9 guard here; the
    native actions-manager write operation has a separate 0..9 validation.
    """
    if not prefix or called_number is None or not called_number.startswith(prefix):
        return None

    try:
        index = int(called_number[len(prefix) :])
    except ValueError as exc:
        raise FastDialRuntimeError(
            f"INVALID_FAST_DIAL_INDEX: {called_number}"
        ) from exc

    try:
        destination = destinations[index]
    except IndexError as exc:
        raise FastDialRuntimeError(f"INVALID_FAST_DIAL_INDEX: {index}") from exc

    instance_attributes["fast_dial_index"] = index
    set_redirect_number(destination)
    return destination


def replace_fast_dial_destination(
    destinations: Sequence[str], index: int, destination: str
) -> tuple[str, ...]:
    """Return the updated ten-slot list used by A1.24's actions manager."""
    if len(destinations) != 10:
        raise ValueError("INVALID_FAST_DIAL: expected exactly 10 entries")
    if not destination.isdigit():
        raise ValueError(f"INVALID_DESTINATION: {destination}")
    if not 0 <= index <= 9:
        raise ValueError(f"INVALID_FAST_DIAL_INDEX: {index}")
    updated = list(destinations)
    updated[index] = destination
    return tuple(updated)
