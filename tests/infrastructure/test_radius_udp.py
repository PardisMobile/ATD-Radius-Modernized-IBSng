from unittest.mock import Mock

import pytest

from atd_radius.infrastructure.radius_udp import RadiusUDPServer


def test_udp_server_rejects_negative_duplicate_cache_age():
    with pytest.raises(ValueError, match="duplicate_cache_max_age"):
        RadiusUDPServer(Mock(), Mock(), duplicate_cache_max_age=-1)
