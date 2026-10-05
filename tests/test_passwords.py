from atd_radius.infrastructure.passwords import Argon2PasswordService


def test_argon2_round_trip() -> None:
    service = Argon2PasswordService()
    stored = service.hash("correct horse battery staple")
    assert service.verify("correct horse battery staple", stored)
    assert not service.verify("wrong password", stored)
    assert not service.verify("", stored)
