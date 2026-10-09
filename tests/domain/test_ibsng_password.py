from atd_radius.domain.ibsng_password import verify_ibsng_password


def test_a124_md5crypt_known_vector():
    assert verify_ibsng_password("password", "$1$salt$qJH7.N4xYta3aEG/dfqo/0")


def test_a124_md5crypt_rejects_wrong_password():
    assert not verify_ibsng_password("wrong", "$1$salt$qJH7.N4xYta3aEG/dfqo/0")


def test_a124_plaintext_compatibility():
    assert verify_ibsng_password("legacy-plain", "legacy-plain")
    assert not verify_ibsng_password("wrong", "legacy-plain")


def test_a124_source_accepts_hash_on_either_side():
    encoded = "$1$salt$qJH7.N4xYta3aEG/dfqo/0"
    assert verify_ibsng_password(encoded, "password")
    assert verify_ibsng_password("password", encoded)


def test_database_char_padding_is_ignored_on_stored_value_only():
    assert verify_ibsng_password("password", "$1$salt$qJH7.N4xYta3aEG/dfqo/0  ")
    assert not verify_ibsng_password(" password", "password")
