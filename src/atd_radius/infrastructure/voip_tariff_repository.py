"""Native IBSng A1.24 PostgreSQL persistence for VoIP tariffs and prefixes."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from atd_radius.domain.voip_tariff import VoipPrefix, VoipTariff


class VoipTariffConnection(Protocol):
    def execute(self, sql: str, params=()): ...


class TariffNotFound(LookupError):
    pass


class TariffAlreadyExists(ValueError):
    pass


class TariffInUseError(ValueError):
    pass


class PrefixNotFound(LookupError):
    pass


class PrefixConflictError(ValueError):
    pass


class PrefixInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PrefixInput:
    code: str
    name: str
    cpm: Decimal
    free_seconds: int
    min_duration: int
    round_to: int
    min_chargeable_duration: int


@dataclass(frozen=True, slots=True)
class PostgresVoipTariffRepository:
    """Map source-defined tables and source spelling; callers own transaction commits."""

    conn: VoipTariffConnection

    def get(self, tariff_id: int) -> VoipTariff | None:
        rows = self.conn.execute(
            "SELECT tariff_id, tariff_name, comment FROM voip_charge_rule_tariff WHERE tariff_id = %s",
            (tariff_id,),
        ).fetchall()
        return self._build(rows[0]) if rows else None

    def get_by_name(self, tariff_name: str) -> VoipTariff | None:
        rows = self.conn.execute(
            "SELECT tariff_id, tariff_name, comment FROM voip_charge_rule_tariff WHERE tariff_name = %s",
            (tariff_name,),
        ).fetchall()
        return self._build(rows[0]) if rows else None

    def list(self) -> list[VoipTariff]:
        rows = self.conn.execute(
            "SELECT tariff_id, tariff_name, comment FROM voip_charge_rule_tariff ORDER BY tariff_id"
        ).fetchall()
        return [self._build(row) for row in rows]

    def create_tariff(self, tariff_name: str, comment: str) -> int:
        self.conn.execute("LOCK TABLE voip_charge_rule_tariff IN SHARE ROW EXCLUSIVE MODE")
        duplicate = self.conn.execute(
            "SELECT tariff_id FROM voip_charge_rule_tariff WHERE tariff_name = %s",
            (tariff_name,),
        ).fetchone()
        if duplicate is not None:
            raise TariffAlreadyExists(tariff_name)
        tariff_id = int(
            self.conn.execute(
                "SELECT nextval('voip_charge_rule_tariff_tariff_id_seq')"
            ).fetchone()[0]
        )
        self.conn.execute(
            "INSERT INTO voip_charge_rule_tariff (tariff_id, tariff_name, comment) VALUES (%s, %s, %s)",
            (tariff_id, tariff_name, comment),
        )
        return tariff_id

    def update_tariff(self, tariff_id: int, tariff_name: str, comment: str) -> None:
        self.conn.execute("LOCK TABLE voip_charge_rule_tariff IN SHARE ROW EXCLUSIVE MODE")
        current = self.conn.execute(
            "SELECT tariff_id FROM voip_charge_rule_tariff WHERE tariff_id = %s FOR UPDATE",
            (tariff_id,),
        ).fetchone()
        if current is None:
            raise TariffNotFound(str(tariff_id))
        duplicate = self.conn.execute(
            "SELECT tariff_id FROM voip_charge_rule_tariff WHERE tariff_name = %s AND tariff_id <> %s",
            (tariff_name, tariff_id),
        ).fetchone()
        if duplicate is not None:
            raise TariffAlreadyExists(tariff_name)
        self.conn.execute(
            "UPDATE voip_charge_rule_tariff SET tariff_name = %s, comment = %s WHERE tariff_id = %s",
            (tariff_name, comment, tariff_id),
        )

    def delete_tariff(self, tariff_name: str) -> int:
        self.conn.execute("LOCK TABLE voip_charge_rule_tariff IN SHARE ROW EXCLUSIVE MODE")
        row = self.conn.execute(
            "SELECT tariff_id FROM voip_charge_rule_tariff WHERE tariff_name = %s FOR UPDATE",
            (tariff_name,),
        ).fetchone()
        if row is None:
            raise TariffNotFound(tariff_name)
        tariff_id = int(row[0])
        used = self.conn.execute(
            "SELECT charge_rule_id FROM voip_charge_rules WHERE tariff_id = %s LIMIT 1",
            (tariff_id,),
        ).fetchone()
        if used is not None:
            raise TariffInUseError(tariff_name)
        self.conn.execute("DELETE FROM tariff_prefix_list WHERE tariff_id = %s", (tariff_id,))
        self.conn.execute("DELETE FROM voip_charge_rule_tariff WHERE tariff_id = %s", (tariff_id,))
        return tariff_id

    def add_prefixes(self, tariff_name: str, prefixes: list[PrefixInput]) -> list[int]:
        if not prefixes:
            raise PrefixInputError("at least one prefix is required")
        tariff_id = self._lock_tariff(tariff_name)
        existing_rows = self.conn.execute(
            "SELECT prefix_code FROM tariff_prefix_list WHERE tariff_id = %s",
            (tariff_id,),
        ).fetchall()
        seen = {str(row[0]) for row in existing_rows}
        new_codes: set[str] = set()
        for prefix in prefixes:
            self._validate_prefix(prefix)
            if prefix.code in seen or prefix.code in new_codes:
                raise PrefixConflictError(prefix.code)
            new_codes.add(prefix.code)

        prefix_ids: list[int] = []
        for prefix in prefixes:
            prefix_id = int(
                self.conn.execute(
                    "SELECT nextval('tariff_prefix_list_tariff_id_seq')"
                ).fetchone()[0]
            )
            self.conn.execute(
                """
                INSERT INTO tariff_prefix_list
                    (tariff_id, prefix_id, prefix_code, prefix_name, cpm, free_seconds,
                     min_duration, round_to, min_chargable_duration)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tariff_id, prefix_id, prefix.code, prefix.name, prefix.cpm,
                    prefix.free_seconds, prefix.min_duration, prefix.round_to,
                    prefix.min_chargeable_duration,
                ),
            )
            prefix_ids.append(prefix_id)
        return prefix_ids

    def update_prefix(
        self, tariff_name: str, prefix_id: int, prefix: PrefixInput
    ) -> None:
        self._validate_prefix(prefix)
        tariff_id = self._lock_tariff(tariff_name)
        current = self.conn.execute(
            "SELECT tariff_id, prefix_code FROM tariff_prefix_list WHERE prefix_id = %s FOR UPDATE",
            (prefix_id,),
        ).fetchone()
        if current is None or int(current[0]) != tariff_id:
            raise PrefixNotFound(str(prefix_id))
        duplicate = self.conn.execute(
            """
            SELECT prefix_id FROM tariff_prefix_list
            WHERE tariff_id = %s AND prefix_code = %s AND prefix_id <> %s
            """,
            (tariff_id, prefix.code, prefix_id),
        ).fetchone()
        if duplicate is not None:
            raise PrefixConflictError(prefix.code)
        self.conn.execute(
            """
            UPDATE tariff_prefix_list
            SET prefix_code = %s, prefix_name = %s, cpm = %s, free_seconds = %s,
                min_duration = %s, round_to = %s, min_chargable_duration = %s
            WHERE tariff_id = %s AND prefix_id = %s
            """,
            (
                prefix.code, prefix.name, prefix.cpm, prefix.free_seconds,
                prefix.min_duration, prefix.round_to, prefix.min_chargeable_duration,
                tariff_id, prefix_id,
            ),
        )

    def delete_prefixes(self, tariff_name: str, prefix_codes: list[str]) -> int:
        if not prefix_codes:
            raise PrefixInputError("at least one prefix code is required")
        tariff_id = self._lock_tariff(tariff_name)
        rows = self.conn.execute(
            "SELECT prefix_code FROM tariff_prefix_list WHERE tariff_id = %s",
            (tariff_id,),
        ).fetchall()
        existing = {str(row[0]) for row in rows}
        if any(code not in existing for code in prefix_codes):
            raise PrefixNotFound("one or more prefix codes are not assigned to this tariff")
        if len(set(prefix_codes)) != len(prefix_codes):
            raise PrefixInputError("duplicate prefix codes are not allowed")
        self.conn.execute(
            "DELETE FROM tariff_prefix_list WHERE tariff_id = %s AND prefix_code = ANY(%s)",
            (tariff_id, prefix_codes),
        )
        return len(prefix_codes)

    def _lock_tariff(self, tariff_name: str) -> int:
        row = self.conn.execute(
            "SELECT tariff_id FROM voip_charge_rule_tariff WHERE tariff_name = %s FOR UPDATE",
            (tariff_name,),
        ).fetchone()
        if row is None:
            raise TariffNotFound(tariff_name)
        return int(row[0])

    @staticmethod
    def _validate_prefix(prefix: PrefixInput) -> None:
        if not prefix.code or not prefix.code.isdigit():
            raise PrefixInputError("prefix code must contain digits only")
        if prefix.cpm < 0:
            raise PrefixInputError("cpm cannot be negative")
        if min(
            prefix.free_seconds, prefix.min_duration, prefix.round_to,
            prefix.min_chargeable_duration,
        ) < 0:
            raise PrefixInputError("prefix duration values cannot be negative")

    def _build(self, row) -> VoipTariff:
        tariff_id = int(row[0])
        prefix_rows = self.conn.execute(
            """
            SELECT prefix_id, prefix_code, prefix_name, cpm, free_seconds,
                   min_duration, round_to, min_chargable_duration
            FROM tariff_prefix_list
            WHERE tariff_id = %s
            """,
            (tariff_id,),
        ).fetchall()
        prefixes = tuple(
            VoipPrefix(
                prefix_id=int(prefix[0]),
                code=str(prefix[1]),
                name=str(prefix[2]),
                cpm=Decimal(str(prefix[3])),
                free_seconds=int(prefix[4]),
                min_duration=int(prefix[5]),
                round_to=int(prefix[6]),
                min_chargeable_duration=int(prefix[7]),
            )
            for prefix in prefix_rows
        )
        return VoipTariff(
            tariff_id=tariff_id,
            name=str(row[1]),
            comment=str(row[2] or ""),
            prefixes=prefixes,
        )
