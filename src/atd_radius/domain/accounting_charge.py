"""A1.24 source-traced Internet charge settlement state."""
from __future__ import annotations
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Protocol
from .billing import BillingError, BillingUsage
from .billing_rules import InternetChargeRule, VoipChargeRule, select_effective_rule, select_effective_voip_rule
from .radius_runtime import SessionState

class ChargeRuleSource(Protocol):
    def list(self, charge_id: int | None = None) -> list[InternetChargeRule]: ...

class PolicySource(Protocol):
    def policy_attributes(self, user_id: int) -> list[tuple[str, str]]: ...

class CreditSink(Protocol):
    def change(self, user_id: int, delta: Decimal) -> Decimal: ...

def _charge_id(source: PolicySource, user_id: int) -> int | None:
    for name, value in source.policy_attributes(user_id):
        if name == "normal_charge":
            try:
                return int(value)
            except ValueError:
                return None
    return None

class InternetChargeSettlement:
    def __init__(self, rules: ChargeRuleSource, policies: PolicySource, credits: CreditSink):
        self.rules, self.policies, self.credits = rules, policies, credits

    def start(self, state: SessionState, when: datetime, ras_id: int, port: str | None) -> None:
        charge_id = _charge_id(self.policies, state.key.user_id)
        state.charge_id = charge_id
        if charge_id is None:
            return
        rule = select_effective_rule(self.rules.list(charge_id), when, ras_id, port)
        self._begin(rule, state, when)

    def update(self, state: SessionState, when: datetime, ras_id: int, port: str | None) -> Decimal:
        if state.charge_id is None:
            return Decimal("0")
        rules = self.rules.list(state.charge_id)
        rule = select_effective_rule(rules, when, ras_id, port)
        if state.charge_rule_id is None:
            self._begin(rule, state, when)
            return state.charge_accrued
        current = next((r for r in rules if r.rule_id == state.charge_rule_id), None)
        if current is None:
            raise ValueError("active charge rule disappeared")
        if rule.rule_id != current.rule_id:
            state.charge_accrued += self._calculate(current, state, when)
            self._begin(rule, state, when)
        return state.charge_accrued + self._calculate(rule, state, when)

    def settle(self, state: SessionState, when: datetime, ras_id: int, port: str | None) -> Decimal:
        total = self.update(state, when, ras_id, port)
        if state.charge_id is not None:
            self.credits.change(state.key.user_id, -total)
        return total

    @staticmethod
    def _begin(rule: InternetChargeRule, state: SessionState, when: datetime) -> None:
        state.charge_rule_id = rule.rule_id
        state.charge_rule_started_at = when
        state.charge_rule_input_octets = state.input_octets
        state.charge_rule_output_octets = state.output_octets

    @staticmethod
    def _calculate(rule: InternetChargeRule, state: SessionState, when: datetime) -> Decimal:
        started = state.charge_rule_started_at
        if started is None:
            return Decimal("0")
        elapsed = max(0, int((when - started).total_seconds()))
        octets = max(0, state.input_octets - state.charge_rule_input_octets) + max(
            0, state.output_octets - state.charge_rule_output_octets
        )
        return rule.calculate(BillingUsage(seconds=elapsed, octets=octets))


class VoipChargeRuleSource(Protocol):
    def list(self, charge_id: int | None = None) -> list[VoipChargeRule]: ...

class VoipTariffSource(Protocol):
    def get(self, tariff_id: int): ...

class VoipChargeSettlement:
    """A1.24 VoIP call usage settlement across effective-rule transitions.

    Free seconds belong to the call's initial prefix. Rule transitions accrue
    the outgoing rule without rounding; only the final active rule applies the
    native min-chargeable-duration/round-to adjustment.
    """
    def __init__(self, rules: VoipChargeRuleSource, policies: PolicySource,
                 tariffs: VoipTariffSource, credits: CreditSink):
        self.rules, self.policies, self.tariffs, self.credits = rules, policies, tariffs, credits

    def start(self, state: SessionState, when: datetime, ras_id: int, port: str | None) -> None:
        charge_id = _policy_charge_id(self.policies, state.key.user_id, "voip_charge")
        state.charge_id = charge_id
        if charge_id is None:
            return
        self._select_and_begin(state, when, ras_id, port)

    def update(self, state: SessionState, when: datetime, ras_id: int, port: str | None) -> Decimal:
        if state.charge_id is None:
            return Decimal("0")
        rules = self.rules.list(state.charge_id)
        called_number = _called_number(state.attributes)
        tariffs = self._tariffs_for(rules)
        rule = select_effective_voip_rule(rules, when, ras_id, port, called_number, tariffs)
        current = next((item for item in rules if item.rule_id == state.charge_rule_id), None)
        prefix = tariffs[rule.tariff_id].find_prefix(called_number) if called_number else None
        if current is None:
            self._begin(rule, state, when, prefix)
        elif rule.rule_id != current.rule_id:
            state.charge_accrued += self._accrue_current(state, when)
            self._begin(rule, state, when, prefix)
        elif state.voip_current_prefix is None and prefix is not None:
            self._begin(rule, state, when, prefix)
        return state.charge_accrued + self._current_usage(state, when, rounded=False)

    def settle(self, state: SessionState, when: datetime, ras_id: int, port: str | None) -> Decimal:
        call_started = _ras_epoch_time(state.attributes.get("connect_time"))
        call_ended = _ras_epoch_time(state.attributes.get("disconnect_time"))
        called_number = _called_number(state.attributes)
        # A1.24's non-lazy path recalculates the entire call from RAS connect
        # time, walking effective-rule intervals rather than trusting when
        # Accounting packets happened to arrive.
        if state.charge_id is not None and call_started and call_ended and called_number:
            total = self._calculate_from_call_times(state, call_started, call_ended, ras_id, port)
        else:
            self.update(state, when, ras_id, port)
            total = state.charge_accrued + self._current_usage(state, when, rounded=True)

        # A1.24 VoipUser.logout treats calls shorter than the first prefix's
        # min_duration as missed calls; this differs from billing rounding.
        min_duration = int(state.attributes.get("min_duration", "0") or "0")
        effective_start = call_started or state.voip_call_started_at or state.started_at
        effective_end = call_ended or when
        duration = max(0, int((effective_end - effective_start).total_seconds())) if effective_start else 0
        if min_duration > 0 and duration < min_duration:
            state.voip_missed_call = True
            total = Decimal("0")
        if state.charge_id is not None:
            self.credits.change(state.key.user_id, -total)
        return total

    def next_limit_event_seconds(
        self, state: SessionState, when: datetime, ras_id: int, port: str | None,
        available_credit: Decimal,
    ) -> Decimal | None:
        """Return the next A1.24 VoIP limit boundary for one active call.

        Computes the next event used by VoipCharge.checkLimits: rule end, start
        of a more-applicable rule, end of initial free seconds, or credit
        exhaustion. Runtime timer/provider kill integration remains separate.
        """
        if state.charge_id is None:
            return None
        if available_credit <= 0:
            return Decimal("0")

        rules = self.rules.list(state.charge_id)
        called_number = _called_number(state.attributes)
        tariffs = self._tariffs_for(rules)
        try:
            rule = select_effective_voip_rule(rules, when, ras_id, port, called_number, tariffs)
        except BillingError:
            return Decimal("0")

        prefix = tariffs[rule.tariff_id].find_prefix(called_number) if called_number else None
        if prefix is None:
            return None

        seconds_today = when.hour * 3600 + when.minute * 60 + when.second
        events = [Decimal(max(1, rule.end_second - seconds_today + 1))]
        if rule.priority < 3:
            for candidate in rules:
                if candidate.priority <= rule.priority or when.weekday() not in candidate.days:
                    continue
                if candidate.start_second <= seconds_today:
                    continue
                if candidate.ras_id is not None and candidate.ras_id != ras_id:
                    continue
                if port not in candidate.ports and "_ALL_" not in candidate.ports:
                    continue
                if called_number and tariffs[candidate.tariff_id].find_prefix(called_number) is None:
                    continue
                events.append(Decimal(candidate.start_second - seconds_today))

        free_seconds = max(0, int(state.voip_free_seconds_remaining))
        if free_seconds:
            events.append(Decimal(free_seconds))
        else:
            rate_per_second = prefix.cpm / Decimal(60)
            if rate_per_second > 0:
                events.append(available_credit / rate_per_second)
        return min(max(Decimal(1), min(events)), Decimal(7 * 24 * 3600))

    def _calculate_from_call_times(
        self, state: SessionState, start: datetime, end: datetime, ras_id: int, port: str | None
    ) -> Decimal:
        if end <= start:
            return Decimal("0")
        rules = self.rules.list(state.charge_id)
        called_number = _called_number(state.attributes)
        tariffs = self._tariffs_for(rules)
        initial_rule = select_effective_voip_rule(rules, start, ras_id, port, called_number, tariffs)
        initial_prefix = tariffs[initial_rule.tariff_id].find_prefix(called_number)
        if initial_prefix is None:
            return Decimal("0")
        # Accounting can arrive after a tariff transition. Native min_duration
        # and prefix metadata belong to the call's first effective prefix, not
        # whichever rule happened to be active when Accounting-Start arrived.
        state.attributes = {
            **state.attributes,
            "min_duration": str(initial_prefix.min_duration),
            "prefix_name": initial_prefix.name,
        }

        # The native non-lazy path starts charging after the first prefix's
        # free seconds, then walks each active rule until its interval ends.
        cursor = start + timedelta(seconds=initial_prefix.free_seconds)
        duration = max(0, int((end - start).total_seconds()))
        usage = Decimal("0")
        final_prefix = initial_prefix
        final_cpm = Decimal("0")
        while cursor < end:
            local_cursor = cursor.astimezone()
            try:
                rule = select_effective_voip_rule(
                    rules, local_cursor, ras_id, port, called_number, tariffs
                )
            except BillingError:
                break
            prefix = tariffs[rule.tariff_id].find_prefix(called_number)
            if prefix is None:
                break
            rule_end = datetime.combine(
                local_cursor.date(), time.min, tzinfo=local_cursor.tzinfo
            ) + timedelta(seconds=rule.end_second)
            next_event = min(rule_end, end)
            if next_event <= cursor:
                # A1.24 advances at least one second if a rule end resolves
                # to the current instant (notably at the end-of-day boundary).
                next_event = min(cursor + timedelta(seconds=1), end)
            elapsed = max(0, int((next_event - cursor).total_seconds()))
            usage += prefix.cpm * Decimal(elapsed) / Decimal(60)
            final_prefix, final_cpm = prefix, prefix.cpm
            cursor = next_event

        # The legacy calculation rounds with the last effective prefix and
        # whole-call duration, but only if there was chargeable interval usage.
        if final_cpm > 0 and duration > 0:
            if final_prefix.min_chargeable_duration and duration < final_prefix.min_chargeable_duration:
                usage += final_cpm * Decimal(final_prefix.min_chargeable_duration - duration) / Decimal(60)
            elif final_prefix.round_to:
                usage += final_cpm * Decimal(final_prefix.round_to - duration % final_prefix.round_to) / Decimal(60)
        return usage

    def _select_and_begin(self, state: SessionState, when: datetime, ras_id: int, port: str | None) -> None:
        rules = self.rules.list(state.charge_id)
        called_number = _called_number(state.attributes)
        tariffs = self._tariffs_for(rules)
        rule = select_effective_voip_rule(rules, when, ras_id, port, called_number, tariffs)
        prefix = tariffs[rule.tariff_id].find_prefix(called_number) if called_number else None
        self._begin(rule, state, when, prefix)

    def _tariffs_for(self, rules) -> dict[int, object]:
        result = {}
        for tariff_id in sorted({rule.tariff_id for rule in rules}):
            tariff = self.tariffs.get(tariff_id)
            if tariff is None:
                raise ValueError(f"VoIP tariff {tariff_id} is missing")
            result[tariff_id] = tariff
        return result

    @staticmethod
    def _begin(rule, state: SessionState, when: datetime, prefix) -> None:
        state.charge_rule_id = rule.rule_id
        state.charge_rule_started_at = when
        state.charge_rule_input_octets = state.input_octets
        state.charge_rule_output_octets = state.output_octets
        state.voip_current_prefix = prefix
        if prefix is not None and state.voip_call_started_at is None:
            # A1.24 VoipChargeRule.start initializes free seconds and publishes
            # prefix metadata only for the first prefix of the call. If the
            # called number arrives after Accounting-Start, consume elapsed
            # time against that original call start rather than resetting it.
            state.voip_call_started_at = (
                _ras_epoch_time(state.attributes.get("connect_time")) or state.started_at or when
            )
            elapsed_before_prefix = max(0, int((when - state.voip_call_started_at).total_seconds()))
            state.voip_free_seconds_remaining = max(0, prefix.free_seconds - elapsed_before_prefix)
            state.attributes = {
                **state.attributes,
                "min_duration": str(prefix.min_duration),
                "prefix_name": prefix.name,
            }

    @staticmethod
    def _accrue_current(state: SessionState, when: datetime) -> Decimal:
        started = state.charge_rule_started_at
        prefix = state.voip_current_prefix
        if started is None or prefix is None:
            return Decimal("0")
        elapsed = max(0, int((when - started).total_seconds()))
        chargeable = max(0, elapsed - state.voip_free_seconds_remaining)
        state.voip_free_seconds_remaining = max(0, state.voip_free_seconds_remaining - elapsed)
        return prefix.cpm * Decimal(chargeable) / Decimal(60)

    @staticmethod
    def _current_usage(state: SessionState, when: datetime, *, rounded: bool) -> Decimal:
        started = state.charge_rule_started_at
        prefix = state.voip_current_prefix
        if started is None or prefix is None:
            return Decimal("0")
        elapsed = max(0, int((when - started).total_seconds()))
        chargeable = max(0, elapsed - state.voip_free_seconds_remaining)
        usage = prefix.cpm * Decimal(chargeable) / Decimal(60)
        if not rounded or chargeable <= 0:
            return usage
        call_started = state.voip_call_started_at or state.started_at or started
        duration = max(0, int((when - call_started).total_seconds()))
        if prefix.min_chargeable_duration and duration < prefix.min_chargeable_duration:
            usage += prefix.cpm * Decimal(prefix.min_chargeable_duration - duration) / Decimal(60)
        elif prefix.round_to:
            usage += prefix.cpm * Decimal(prefix.round_to - duration % prefix.round_to) / Decimal(60)
        return usage


def _policy_charge_id(source: PolicySource, user_id: int, attr_name: str) -> int | None:
    for name, value in source.policy_attributes(user_id):
        if name == attr_name:
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _ras_epoch_time(value) -> datetime | None:
    """Convert the epoch-second values used by A1.24 RAS call-time attributes."""
    if value is None or value == "":
        return None
    try:
        return datetime.fromtimestamp(float(value)).astimezone()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _called_number(attributes) -> str:
    return str(attributes.get("Called-Station-Id", attributes.get("Called-Station-ID", "")) or "")

class UserChargeSettlement:
    """Route normal and VoIP sessions to their native charge lifecycle."""
    def __init__(self, users, internet: InternetChargeSettlement, voip: VoipChargeSettlement):
        self.users, self.internet, self.voip = users, internet, voip

    def _for(self, state):
        return self.internet if self.users.is_normal_user(state.key.user_id) else self.voip

    def start(self, state, when, ras_id, port):
        return self._for(state).start(state, when, ras_id, port)

    def update(self, state, when, ras_id, port):
        return self._for(state).update(state, when, ras_id, port)

    def settle(self, state, when, ras_id, port):
        return self._for(state).settle(state, when, ras_id, port)
