from atd_radius.protocols.eap import EAPPacket, join_eap_message, split_eap_message


def test_eap_roundtrip():
    original = EAPPacket(code=2, identifier=7, data=b"\x13\x01")
    assert EAPPacket.decode(original.encode()) == original


def test_eap_message_fragmentation_round_trip():
    payload = b"x" * 700
    assert join_eap_message(split_eap_message(payload)) == payload
