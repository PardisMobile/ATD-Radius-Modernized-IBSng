from atd_radius.protocols.eap import EAPPacket


def test_eap_roundtrip():
    original = EAPPacket(code=2, identifier=7, data=b"\x13\x01")
    assert EAPPacket.decode(original.encode()) == original
