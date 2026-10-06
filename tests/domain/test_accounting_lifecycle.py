import pytest
from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus, SessionUsage, event_from_attributes
def test_start_and_interim_return_only_new_octets():
    usage=SessionUsage()
    usage.start(AccountingEvent(AccountingStatus.START,"u",input_octets=100,output_octets=200))
    assert usage.interim(AccountingEvent(AccountingStatus.INTERIM,"u",input_octets=160,output_octets=260))==(60,60)
    assert usage.stop(AccountingEvent(AccountingStatus.STOP,"u",input_octets=180,output_octets=300))==(20,40)
def test_event_mapping_accepts_alive_alias():
    e=event_from_attributes({"Acct-Status-Type":"Alive","User-Name":"u","Acct-Input-Octets":"12"})
    assert e.status is AccountingStatus.ALIVE and e.input_octets==12
def test_unknown_status_rejected():
    with pytest.raises(ValueError): event_from_attributes({"Acct-Status-Type":"Bogus","User-Name":"u"})


def test_event_from_attributes_preserves_native_packet_details():
    event = event_from_attributes({
        "Acct-Status-Type": "Start",
        "User-Name": "alice",
        "Acct-Session-Id": "sid-1",
        "NAS-Port": "7",
        "NAS-IP-Address": "192.0.2.1",
    })
    assert event.attributes["NAS-Port"] == "7"
    assert event.attributes["NAS-IP-Address"] == "192.0.2.1"
