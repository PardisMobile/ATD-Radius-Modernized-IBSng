from atd_radius.protocols.radius import RadiusPacket


def test_radius_roundtrip():
    original = RadiusPacket(1, 4, b"0123456789abcdef", b"\x01\x06hello")
    assert RadiusPacket.decode(original.encode()) == original
