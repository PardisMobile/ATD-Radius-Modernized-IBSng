from decimal import Decimal
from atd_radius.domain.voip_tariff import VoipPrefix, VoipTariff, chargeable_duration, calculate_voip_charge

def p(code="98", **kw):
    return VoipPrefix(1, code, "Iran", Decimal("60"), 10, 3, 30, 20, **kw)

def test_longest_prefix_wins():
    tariff=VoipTariff(1,"t","", (p("9"),p("98"),p("989")))
    assert tariff.find_prefix("9891212").code=="989"

def test_min_duration_makes_missed_call_free():
    assert chargeable_duration(2,p(min_duration=3))==0

def test_free_seconds_are_excluded():
    assert chargeable_duration(40,p(free_seconds=10))==30

def test_min_chargeable_then_rounding():
    assert chargeable_duration(15,p(free_seconds=0,min_chargeable_duration=20,round_to=30))==30

def test_charge_uses_cpm_per_minute():
    assert calculate_voip_charge(60,p(free_seconds=0,round_to=0,min_chargeable_duration=0))==Decimal("60")
