"""A1.24 source-traced Internet charge settlement state."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from .billing import BillingUsage
from .billing_rules import InternetChargeRule, select_effective_rule
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
        if state.charge_id is not None and total:
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
