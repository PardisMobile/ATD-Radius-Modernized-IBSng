from datetime import datetime, timezone
from unittest.mock import Mock
from decimal import Decimal
from atd_radius.domain.accounting_charge import InternetChargeSettlement, VoipChargeSettlement, UserChargeSettlement
from atd_radius.domain.billing_rules import ALL, InternetChargeRule, VoipChargeRule
from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry
from atd_radius.domain.voip_tariff import VoipPrefix, VoipTariff

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
    rule=InternetChargeRule(1,frozenset({0}),0,86399,ports=frozenset({ALL}),cpm=Decimal("60"),cpk=Decimal("1"))
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
    first=InternetChargeRule(1,frozenset({0}),0,39600,ports=frozenset({ALL}),cpm=Decimal("60"),cpk=Decimal("1"))
    second=InternetChargeRule(2,frozenset({0}),39600,86399,ports=frozenset({ALL}),cpm=Decimal("120"),cpk=Decimal("1"))
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
    rule=InternetChargeRule(1,frozenset({0}),0,86399,ports=frozenset({ALL}),cpm=Decimal("60"),cpk=Decimal("1"))
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
    rule=InternetChargeRule(1,frozenset({0}),0,86399,ports=frozenset({ALL}),cpm=Decimal("0"),cpk=Decimal("1"))
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
    rule=InternetChargeRule(1,frozenset({0}),0,86399,ports=frozenset({ALL}),cpm=Decimal("0"),cpk=Decimal("0"))
    credits=Credits()
    settlement=InternetChargeSettlement(Rules(rule),Policies(),credits)
    registry=SessionRegistry()
    start=datetime(2026,1,5,10,0,tzinfo=timezone.utc)
    state=registry.start(SessionKey(7,3,"zero"),input_octets=10,output_octets=20,started_at=start)
    settlement.start(state,start,3,None)
    used=settlement.settle(state,start.replace(minute=1),3,None)
    assert used==Decimal("0")
    assert credits.changes==[(7,Decimal("0"))]


class VoipRules:
    def __init__(self, rules): self.rules = rules
    def list(self, charge_id=None): return [r for r in self.rules if charge_id is None or r.charge_id == charge_id]

class VoipPolicies:
    def policy_attributes(self, user_id): return [("voip_charge", "12")]

class Tariffs:
    def __init__(self, tariffs): self.tariffs = tariffs
    def get(self, tariff_id): return self.tariffs.get(tariff_id)

class UserKinds:
    def __init__(self, normal): self.normal = normal
    def is_normal_user(self, user_id): return self.normal

def _voip_rule(rule_id, tariff_id, start, end):
    return VoipChargeRule(rule_id, frozenset({0}), start, end, ports=frozenset({ALL}), charge_id=12, tariff_id=tariff_id)

def _voip_tariff(tariff_id, cpm, *, free=0, round_to=0, minimum=0, min_duration=0):
    prefix = VoipPrefix(tariff_id, "98", "Iran", Decimal(cpm), free, min_duration, round_to, minimum)
    return VoipTariff(tariff_id, f"tariff-{tariff_id}", "", (prefix,))

def test_voip_charge_settlement_applies_call_free_seconds_and_rounding():
    rule = _voip_rule(1, 5, 0, 86399)
    credits = Credits()
    settlement = VoipChargeSettlement(VoipRules([rule]), VoipPolicies(), Tariffs({5: _voip_tariff(5, "60", free=10, round_to=30)}), credits)
    registry = SessionRegistry()
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    state = registry.start(SessionKey(7, 3, "voip-free"), {"Called-Station-Id": "98912"}, started_at=start)
    settlement.start(state, start, 3, None)
    total = settlement.settle(state, start.replace(second=20), 3, None)
    assert total == Decimal("20")
    assert credits.changes == [(7, Decimal("-20"))]

def test_voip_rule_transition_accrues_old_tariff_and_uses_final_rule_rounding():
    first = _voip_rule(1, 5, 0, 39600)
    second = _voip_rule(2, 6, 39600, 86399)
    credits = Credits()
    tariffs = Tariffs({5: _voip_tariff(5, "60"), 6: _voip_tariff(6, "120", round_to=60)})
    settlement = VoipChargeSettlement(VoipRules([first, second]), VoipPolicies(), tariffs, credits)
    registry = SessionRegistry()
    start = datetime(2026, 1, 5, 10, 59, 30, tzinfo=timezone.utc)
    state = registry.start(SessionKey(7, 3, "voip-transition"), {"Called-Station-Id": "98912"}, started_at=start)
    settlement.start(state, start, 3, None)
    transition = start.replace(hour=11, minute=0, second=0)
    assert settlement.update(state, transition, 3, None) == Decimal("30")
    assert state.charge_rule_id == 2
    stop = transition.replace(minute=0, second=30)
    total = settlement.settle(state, stop, 3, None)
    assert total == Decimal("210")
    assert credits.changes == [(7, Decimal("-210"))]

def test_native_charge_settlement_routes_by_source_user_type():
    internet, voip = Mock(), Mock()
    router = UserChargeSettlement(UserKinds(normal=False), internet, voip)
    state = SessionRegistry().start(SessionKey(7, 3, "route"))
    router.start(state, datetime(2026, 1, 5, tzinfo=timezone.utc), 3, None)
    voip.start.assert_called_once()
    internet.start.assert_not_called()


def test_voip_initial_prefix_publishes_native_min_duration_and_prefix_name():
    rule = _voip_rule(1, 5, 0, 86399)
    tariff = _voip_tariff(5, "60", free=15, min_duration=8)
    registry = SessionRegistry()
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    state = registry.start(SessionKey(7, 3, "voip-metadata"), {"Called-Station-Id": "98912"}, started_at=start)
    settlement = VoipChargeSettlement(VoipRules([rule]), VoipPolicies(), Tariffs({5: tariff}), Credits())
    settlement.start(state, start, 3, None)
    assert state.attributes["min_duration"] == "8"
    assert state.attributes["prefix_name"] == "Iran"
    assert state.voip_free_seconds_remaining == 15


def test_voip_free_seconds_are_consumed_before_called_number_arrives():
    rule = _voip_rule(1, 5, 0, 86399)
    tariff = _voip_tariff(5, "60", free=15, min_duration=8)
    registry = SessionRegistry()
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    state = registry.start(SessionKey(7, 3, "voip-late-called"), {}, started_at=start)
    settlement = VoipChargeSettlement(VoipRules([rule]), VoipPolicies(), Tariffs({5: tariff}), Credits())
    settlement.start(state, start, 3, None)
    when = start.replace(second=10)
    state.attributes = {**state.attributes, "Called-Station-Id": "98912"}
    settlement.update(state, when, 3, None)
    assert state.voip_free_seconds_remaining == 5
    assert state.attributes["min_duration"] == "8"

 
def test_voip_call_shorter_than_native_min_duration_is_missed_and_not_charged():
    rule = _voip_rule(1, 5, 0, 86399)
    credits = Credits()
    settlement = VoipChargeSettlement(
        VoipRules([rule]), VoipPolicies(),
        Tariffs({5: _voip_tariff(5, "60", min_duration=8)}), credits,
    )
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    state = SessionRegistry().start(
        SessionKey(7, 3, "voip-missed"), {"Called-Station-Id": "98912"},
        started_at=start,
    )
    settlement.start(state, start, 3, None)

    used = settlement.settle(state, start.replace(second=7), 3, None)

    assert used == Decimal("0")
    assert state.voip_missed_call is True
    assert credits.changes == [(7, Decimal("0"))]


def test_voip_call_at_native_min_duration_is_not_marked_missed():
    rule = _voip_rule(1, 5, 0, 86399)
    credits = Credits()
    settlement = VoipChargeSettlement(
        VoipRules([rule]), VoipPolicies(),
        Tariffs({5: _voip_tariff(5, "60", min_duration=8)}), credits,
    )
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    state = SessionRegistry().start(
        SessionKey(7, 3, "voip-min-duration"), {"Called-Station-Id": "98912"},
        started_at=start,
    )
    settlement.start(state, start, 3, None)

    used = settlement.settle(state, start.replace(second=8), 3, None)

    assert used == Decimal("8")
    assert state.voip_missed_call is False
    assert credits.changes == [(7, Decimal("-8"))]

 
def test_voip_missed_call_uses_authoritative_ras_connect_and_disconnect_times():
    rule = _voip_rule(1, 5, 0, 86399)
    credits = Credits()
    settlement = VoipChargeSettlement(
        VoipRules([rule]), VoipPolicies(),
        Tariffs({5: _voip_tariff(5, "60", min_duration=8)}), credits,
    )
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    connect = start.replace(second=10).timestamp()
    disconnect = start.replace(second=17).timestamp()
    state = SessionRegistry().start(
        SessionKey(7, 3, "voip-ras-times"),
        {"Called-Station-Id": "98912", "connect_time": str(connect)},
        started_at=start,
    )
    settlement.start(state, start, 3, None)
    state.attributes = {**state.attributes, "disconnect_time": str(disconnect)}

    used = settlement.settle(state, start.replace(second=30), 3, None)

    assert used == Decimal("0")
    assert state.voip_missed_call is True
    assert credits.changes == [(7, Decimal("0"))]

 
def test_voip_settlement_recalculates_full_call_across_rule_boundary_from_ras_times():
    first = _voip_rule(1, 5, 0, 39600)
    second = _voip_rule(2, 6, 39600, 86399)
    credits = Credits()
    settlement = VoipChargeSettlement(
        VoipRules([first, second]), VoipPolicies(),
        Tariffs({
            5: _voip_tariff(5, "60"),
            6: _voip_tariff(6, "120"),
        }), credits,
    )
    start = datetime(2026, 1, 5, 10, 59, 50, tzinfo=timezone.utc)
    end = datetime(2026, 1, 5, 11, 0, 10, tzinfo=timezone.utc)
    state = SessionRegistry().start(
        SessionKey(7, 3, "voip-non-lazy-boundary"),
        {
            "Called-Station-Id": "98912",
            "connect_time": str(start.timestamp()),
            "disconnect_time": str(end.timestamp()),
        },
        started_at=start,
    )
    settlement.start(state, start, 3, None)

    # A late Accounting-Stop timestamp must not make the second rule's rate
    # apply to the entire call: 10s at CPM 60 + 10s at CPM 120 = 30.
    used = settlement.settle(state, end.replace(hour=11, minute=5), 3, None)

    assert used == Decimal("30")
    assert credits.changes == [(7, Decimal("-30"))]

 
def test_voip_ras_recalculation_uses_first_prefix_min_duration_after_rule_transition():
    first = _voip_rule(1, 5, 0, 39600)
    second = _voip_rule(2, 6, 39600, 86399)
    credits = Credits()
    settlement = VoipChargeSettlement(
        VoipRules([first, second]), VoipPolicies(),
        Tariffs({
            5: _voip_tariff(5, "60", min_duration=5),
            6: _voip_tariff(6, "120", min_duration=60),
        }), credits,
    )
    call_start = datetime(2026, 1, 5, 10, 59, 50, tzinfo=timezone.utc)
    call_end = datetime(2026, 1, 5, 11, 0, 10, tzinfo=timezone.utc)
    accounting_start = datetime(2026, 1, 5, 11, 0, 5, tzinfo=timezone.utc)
    state = SessionRegistry().start(
        SessionKey(7, 3, "voip-first-prefix-metadata"),
        {
            "Called-Station-Id": "98912",
            "connect_time": str(call_start.timestamp()),
            "disconnect_time": str(call_end.timestamp()),
        },
        started_at=accounting_start,
    )
    settlement.start(state, accounting_start, 3, None)

    used = settlement.settle(state, accounting_start.replace(minute=5), 3, None)

    assert used == Decimal("30")
    assert state.attributes["min_duration"] == "5"
    assert state.attributes["prefix_name"] == "Iran"
    assert state.voip_missed_call is False
    assert credits.changes == [(7, Decimal("-30"))]


def test_voip_limit_planner_uses_rule_end_as_next_event():
    rule = _voip_rule(1, 5, 0, 39600)
    settlement = VoipChargeSettlement(
        VoipRules([rule]), VoipPolicies(), Tariffs({5: _voip_tariff(5, "60")}), Credits()
    )
    start = datetime(2026, 1, 5, 10, 59, 30, tzinfo=timezone.utc)
    state = SessionRegistry().start(
        SessionKey(7, 3, "limit-rule-end"), {"Called-Station-Id": "98912"}, started_at=start
    )
    settlement.start(state, start, 3, None)
    assert settlement.next_limit_event_seconds(state, start, 3, None, Decimal("100")) == Decimal("31")


def test_voip_limit_planner_prioritizes_remaining_initial_free_seconds():
    rule = _voip_rule(1, 5, 0, 86399)
    settlement = VoipChargeSettlement(
        VoipRules([rule]), VoipPolicies(), Tariffs({5: _voip_tariff(5, "60", free=20)}), Credits()
    )
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    state = SessionRegistry().start(
        SessionKey(7, 3, "limit-free-seconds"), {"Called-Station-Id": "98912"}, started_at=start
    )
    settlement.start(state, start, 3, None)
    assert state.voip_free_seconds_remaining == 20
    assert settlement.next_limit_event_seconds(state, start, 3, None, Decimal("100")) == Decimal("20")


def test_voip_limit_planner_calculates_credit_exhaustion_deadline():
    rule = _voip_rule(1, 5, 0, 86399)
    settlement = VoipChargeSettlement(
        VoipRules([rule]), VoipPolicies(), Tariffs({5: _voip_tariff(5, "60")}), Credits()
    )
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    state = SessionRegistry().start(
        SessionKey(7, 3, "limit-credit"), {"Called-Station-Id": "98912"}, started_at=start
    )
    settlement.start(state, start, 3, None)
    assert settlement.next_limit_event_seconds(state, start, 3, None, Decimal("5")) == Decimal("5")


def test_voip_limit_planner_aggregates_credit_rate_across_concurrent_calls():
    rule = _voip_rule(1, 5, 0, 86399)
    settlement = VoipChargeSettlement(
        VoipRules([rule]), VoipPolicies(), Tariffs({5: _voip_tariff(5, "60")}), Credits()
    )
    start = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    registry = SessionRegistry()
    first = registry.start(SessionKey(7, 3, "limit-multi-a"), {"Called-Station-Id": "98912"}, started_at=start)
    second = registry.start(SessionKey(7, 3, "limit-multi-b"), {"Called-Station-Id": "98912"}, started_at=start)
    settlement.start(first, start, 3, None)
    settlement.start(second, start, 3, None)

    # Each call consumes one credit unit/second; A1.24 combines both rates.
    assert settlement.next_limit_event_seconds_for_sessions(
        [first, second], start, 3, None, Decimal("10")
    ) == Decimal("5")


def test_voip_limit_planner_detects_future_more_applicable_rule():
    general = VoipChargeRule(
        1, frozenset({0}), 0, 86399, ports=frozenset({ALL}), charge_id=12, tariff_id=5
    )
    ras_specific = VoipChargeRule(
        2, frozenset({0}), 39600, 43200, ras_id=3, ports=frozenset({ALL}), charge_id=12, tariff_id=5
    )
    settlement = VoipChargeSettlement(
        VoipRules([general, ras_specific]), VoipPolicies(),
        Tariffs({5: _voip_tariff(5, "60")}), Credits()
    )
    start = datetime(2026, 1, 5, 10, 59, 30, tzinfo=timezone.utc)
    state = SessionRegistry().start(
        SessionKey(7, 3, "limit-more-specific"), {"Called-Station-Id": "98912"}, started_at=start
    )
    settlement.start(state, start, 3, None)

    assert state.charge_rule_id == general.rule_id
    assert settlement.next_limit_event_seconds(state, start, 3, None, Decimal("100")) == Decimal("30")
