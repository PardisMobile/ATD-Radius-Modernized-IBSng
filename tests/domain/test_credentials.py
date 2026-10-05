import pytest

from atd_radius.domain.credentials import (
    CredentialError,
    CredentialKind,
    CredentialSet,
    find_duplicate_usernames,
    normalize_usernames,
)


def test_normal_user_can_have_multiple_usernames():
    credentials = CredentialSet(
        CredentialKind.NORMAL,
        normalize_usernames("alice alice2"),
        password="secret",
    )
    credentials.validate()
    assert credentials.usernames == ("alice", "alice2")


def test_invalid_username_is_rejected():
    credentials = CredentialSet(CredentialKind.NORMAL, ("bad username",), password="x")
    with pytest.raises(CredentialError):
        credentials.validate()


def test_generated_and_explicit_password_cannot_be_combined():
    credentials = CredentialSet(
        CredentialKind.VOIP,
        ("1001",),
        password="secret",
        generate_password=True,
    )
    with pytest.raises(CredentialError):
        credentials.validate()


def test_duplicate_username_detection_spans_credentials():
    credentials = [
        CredentialSet(CredentialKind.NORMAL, ("alice",)),
        CredentialSet(CredentialKind.NORMAL, ("bob", "alice")),
    ]
    assert find_duplicate_usernames(credentials) == {"alice"}
