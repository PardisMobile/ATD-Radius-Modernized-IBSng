import re

import pytest

from atd_radius.domain.ibsng_password import hash_ibsng_password, verify_ibsng_password


def test_hash_ibsng_password_creates_random_source_compatible_hash():
    first = hash_ibsng_password("Abc_123-")
    second = hash_ibsng_password("Abc_123-")
    assert re.fullmatch(r"\$1\$[0-9A-Za-z]{8}\$[./0-9A-Za-z]{22}", first)
    assert first != second
    assert verify_ibsng_password("Abc_123-", first)
    assert not verify_ibsng_password("wrong", first)


@pytest.mark.parametrize("password", ["", "contains space", "dollar$", "nonascii-é"])
def test_hash_ibsng_password_rejects_characters_a124_rejects(password):
    with pytest.raises(ValueError):
        hash_ibsng_password(password)
