import pytest
from atd_radius.domain.radius import RadiusCode, RadiusPacket, response_for_access
def test_access_response_preserves_identifier_and_authenticator():
    req=RadiusPacket(RadiusCode.ACCESS_REQUEST,7,{"User-Name":"alice"},b"abc")
    res=response_for_access(req,"accept",{"Service-Type":"Framed-User"})
    assert res.code is RadiusCode.ACCESS_ACCEPT
    assert res.identifier==7
    assert res.authenticator==b"abc"
def test_access_response_rejects_wrong_packet_type():
    with pytest.raises(ValueError): response_for_access(RadiusPacket(RadiusCode.ACCOUNTING_REQUEST,1),"accept")
