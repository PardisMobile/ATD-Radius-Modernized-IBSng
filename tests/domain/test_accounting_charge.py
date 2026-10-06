from datetime import datetime, timezone
from decimal import Decimal
from atd_radius.domain.accounting_charge import InternetChargeSettlement
from atd_radius.domain.billing_rules import InternetChargeRule
from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry

class Rules:
    def __init__(self, rule): self.rule=rule
    def list(self, charge_id=None): return [self.rule]

class Policies:
    def policy_attributes(self, user_id): return [("normal_charge","9")]

class Credits:
    def __init__(self): self.changes=[]
    def change(self,user_id,delta):
        self.changes.append((user_id,delta)); return Decimal("0")

def test_internet_charge_settlement_uses_rule_start_counters_and_time():
    rule=InternetChargeRule(1,frozenset({0}),0,86399,cpm=Decimal("60"),cpk=Decimal("1"))
    credits=Credits()
    settlement=InternetChargeSettlement(Rules(rule),Policies(),credits)
    registry=SessionRegistry()
    start=datetime(2026,1,5,10,0,tzinfo=timezone.utc)
    state=registry.start(SessionKey(7,3,"s"),input_octets=100,output_octets=200,started_at=start)
    settlement.start(state,start,3,None)
    state.input_octets=1124
    state.output_octets=1224
    stop=start.replace(minute=2)
    used=settlement.settle(state,stop,3,None)
    assert used==Decimal("122")
    assert credits.changes==[(7,Decimal("-122"))]


def test_rule_transition_accumulates_previous_rule_before_resetting_baseline():
    first=InternetChargeRule(1,frozenset({0}),0,39600,cpm=Decimal("60"),cpk=Decimal("1"))
    second=InternetChargeRule(2,frozenset({0}),39600,86399,cpm=Decimal("120"),cpk=Decimal("1"))
    class TwoRules:
        def list(self, charge_id=None): return [first,second]
    settlement=InternetChargeSettlement(TwoRules(),Policies(),Credits())
    registry=SessionRegistry()
    start=datetime(2026,1,5,10,0,tzinfo=timezone.utc)
    state=registry.start(SessionKey(7,3,"transition"),input_octets=100,output_octets=200,started_at=start)
    settlement.start(state,start,3,None)
    state.input_octets=1100
    state.output_octets=1200
    transition=start.replace(hour=11)
    settlement.update(state,transition,3,None)
    assert state.charge_accrued==Decimal("3601.953125")
    assert state.charge_rule_id==2
    assert state.charge_rule_input_octets==1100
    assert state.charge_rule_output_octets==1200
    state.input_octets=2124
    state.output_octets=2224
    stop=transition.replace(minute=2)
    used=settlement.settle(state,stop,3,None)
    assert used==Decimal("3843.953125")

def test_multiple_instances_keep_independent_charge_baselines():
    rule=InternetChargeRule(1,frozenset({0}),0,86399,cpm=Decimal("60"),cpk=Decimal("1"))
    settlement=InternetChargeSettlement(Rules(rule),Policies(),Credits())
    registry=SessionRegistry()
    start=datetime(2026,1,5,10,0,tzinfo=timezone.utc)
    a=registry.start(SessionKey(7,3,"a"),input_octets=100,output_octets=100,started_at=start)
    b=registry.start(SessionKey(7,3,"b"),input_octets=5000,output_octets=9000,started_at=start)
    settlement.start(a,start,3,None)
    settlement.start(b,start,3,None)
    a.input_octets=1124; a.output_octets=1124
    b.input_octets=6024; b.output_octets=10024
    stop=start.replace(minute=1)
    assert settlement.settle(a,stop,3,None)==Decimal("62")
    assert settlement.settle(b,stop,3,None)==Decimal("62")


def test_counter_reset_never_creates_negative_transfer_usage():
    rule=InternetChargeRule(1,frozenset({0}),0,86399,cpm=Decimal("0"),cpk=Decimal("1"))
    settlement=InternetChargeSettlement(Rules(rule),Policies(),Credits())
    registry=SessionRegistry()
    start=datetime(2026,1,5,10,0,tzinfo=timezone.utc)
    state=registry.start(SessionKey(7,3,"reset"),input_octets=1000,output_octets=2000,started_at=start)
    settlement.start(state,start,3,None)
    state.input_octets=100
    state.output_octets=200
    stop=start.replace(minute=1)
    assert settlement.settle(state,stop,3,None)==Decimal("0")

def test_zero_credit_settlement_is_still_committed_as_zero():
    rule=InternetChargeRule(1,frozenset({0}),0,86399,cpm=Decimal("0"),cpk=Decimal("0"))
    credits=Credits()
    settlement=InternetChargeSettlement(Rules(rule),Policies(),credits)
    registry=SessionRegistry()
    start=datetime(2026,1,5,10,0,tzinfo=timezone.utc)
    state=registry.start(SessionKey(7,3,"zero"),input_octets=10,output_octets=20,started_at=start)
    settlement.start(state,start,3,None)
    used=settlement.settle(state,start.replace(minute=1),3,None)
    assert used==Decimal("0")
    assert credits.changes==[(7,Decimal("0"))]
