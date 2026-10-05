from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

import psycopg

from atd_radius.config import settings


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """Open a short-lived application connection.

    A pool will replace this adapter when deployment wiring is introduced; the
    application and protocol layers must remain independent of that choice.
    """
    with psycopg.connect(settings.database_url) as conn:
        yield conn
