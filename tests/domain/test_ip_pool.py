import pytest

from atd_radius.domain.ip_pool import IPAllocator, IPPool, IPPoolError


def test_allocator_starts_at_first_usable_host():
    pool = IPPool.from_cidr("test", "10.20.30.0/30")
    assert str(IPAllocator(pool).allocate([])) == "10.20.30.1"


def test_allocator_skips_used_addresses():
    pool = IPPool.from_cidr("test", "10.20.30.0/29")
    assert str(IPAllocator(pool).allocate(["10.20.30.1", "10.20.30.2"])) == "10.20.30.3"


def test_allocator_reports_exhaustion():
    pool = IPPool.from_cidr("test", "10.20.30.0/30")
    with pytest.raises(IPPoolError):
        IPAllocator(pool).allocate(["10.20.30.1", "10.20.30.2"])


def test_disabled_pool_cannot_allocate():
    pool = IPPool.from_cidr("test", "10.20.30.0/29", enabled=False)
    with pytest.raises(IPPoolError):
        IPAllocator(pool).allocate([])
