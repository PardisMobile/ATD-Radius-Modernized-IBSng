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
