#!/usr/bin/env python3
"""Audit the checked-in IBSng A1.24 source archive without modifying it.

This is an inventory/source-evidence tool, not a claim that ATD has parity.
It verifies the archive hash declared by Source of Truth/README.md, inventories
all archived files, and prints direct source excerpts for RAS side effects and
RADIUS dictionary entries relevant to the modernized implementation.
"""
from __future__ import annotations

import hashlib
import re
import sys
import tarfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "Source of Truth" / "IBSng-A1.24.tar.bz2"
README = ROOT / "Source of Truth" / "README.md"

def main() -> int:
    if not ARCHIVE.is_file():
        print(f"ERROR: canonical archive missing: {ARCHIVE}")
        return 2
    expected_match = re.search(r"Archive SHA-256:\s*[^0-9a-fA-F]*([0-9a-fA-F]{64})", README.read_text())
    if not expected_match:
        print("ERROR: README does not declare a valid 64-character archive SHA-256")
        return 2
    expected = expected_match.group(1).lower()
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    print("== Canonical archive integrity ==")
    print(f"expected_sha256={expected}")
    print(f"actual_sha256={digest}")
    print(f"sha256_match={digest == expected}")
    if digest != expected:
        print("ERROR: canonical archive checksum mismatch; source-derived claims must be treated as unverified.")
        return 1

    with tarfile.open(ARCHIVE, "r:bz2") as archive:
        members = [m for m in archive.getmembers() if m.isfile()]
        ext_counts = Counter(Path(m.name).suffix.lower() or "[no extension]" for m in members)
        print("\n== Full archive inventory ==")
        print(f"file_count={len(members)}")
        for ext, count in ext_counts.most_common():
            print(f"extension {ext}: {count}")
        ras_members = [m for m in members if "/core/ras/rases/" in "/" + m.name]
        print("\n== RAS provider source files ==")
        for member in ras_members:
            print(member.name)

        targets = {
            "RAS side-effect definitions": re.compile(
                r"def\s+(?:killUser|kill_user|disconnectUser|disconnect_user|getOnlineUsers|listUsers)\s*\("
            ),
            "SNMP/RSH/launcher source references": re.compile(
                r"snmp|rsh|portslave_kill_port_command|pppd_kill_port_command|killUser|interface_index|ifAdminStatus",
                re.IGNORECASE
            ),
            "dictionary target attributes": re.compile(
                r"^\s*(?:23\s+Framed-IPX-Network|51\s+Acct-Link-Count|52\s+Acct-Input-Gigawords|53\s+Acct-Output-Gigawords|63\s+Login-LAT-Port|40\s+Acct-Status-Type|61\s+NAS-Port-Type)\b",
                re.IGNORECASE
            ),
            "RADIUS attribute type handling": re.compile(
                r"Framed-IPX-Network|Acct-Link-Count|Acct-Input-Gigawords|Acct-Output-Gigawords|Login-LAT-Port|Acct-Status-Type|NAS-Port-Type"
            ),
            "authentication protocol source anchors": re.compile(
                r"MS-CHAP|MSCHAP|CHAP|AuthenticatorResponse|MPPE|Peer-Challenge|NT-Response",
                re.IGNORECASE
            ),
            "multi-login source anchors": re.compile(r"multi_login|MultiLogin|RAS_DOESNT_ALLOW_MULTILOGIN"),
        }
        print("\n== Source evidence excerpts (path:line:text) ==")
        for label, pattern in targets.items():
            print(f"\n-- {label} --")
            matches = 0
            for member in members:
                if member.size > 8_000_000:
                    continue
                if not member.name.endswith((".py", ".sql", ".txt", ".dictionary", ".ser", ".sip", ".usr")):
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    continue
                try:
                    lines = stream.read().decode("utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                for line_no, line in enumerate(lines, 1):
                    if pattern.search(line):
                        print(f"{member.name}:{line_no}:{line[:260]}")
                        matches += 1
                        if matches >= 120:
                            print("... output capped at 120 matches for this category ...")
                            break
                if matches >= 120:
                    break
            if matches == 0:
                print("(no direct matches)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
