#!/usr/bin/env python3
"""Reproducible source-first audit of the canonical IBSng A1.24 archive.

This tool inventories the complete archive and emits direct source excerpts
for high-risk behavior. It does not claim ATD parity merely because source
files or matching symbol names exist.
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

TARGET_FILES = {
    "PortMaster SNMP kill": ("IBSng/core/ras/rases/portmaster.py", r"killUser"),
    "Total Control SNMP kill": ("IBSng/core/ras/rases/total_control.py", r"killUser"),
    "PPPD launcher kill": ("IBSng/core/ras/rases/pppd.py", r"killUser"),
    "PortSlave launcher kill": ("IBSng/core/ras/rases/portslave.py", r"killUser"),
    "Cisco SNMP/RSH kill branches": ("IBSng/core/ras/rases/cisco.py", r"def killUser|def __killUserOnPort|def __killByRSH|def __killBySnmp|def __parseAsyncPort"),
    "Cisco VPDN interface discovery and RSH": ("IBSng/core/ras/rases/cisco_vpdn.py", r"def killUser|def __killUser|def __killUserOnPort|def __killByRSH|def __findUserInterface|def __getUsernameAndRemoteIPFromUserMsg"),
    "MikroTik RSH/SSH wrapper kill": ("IBSng/core/ras/rases/mikrotik.py", r"def __init__|def killUser|mikrotik_ssh_wrapper|def __getUserIP|def __getNasPortType"),
    "PPPD command defaults": ("IBSng/core/ras/rases/pppd.py", r"type_attrs|pppd_kill_port_command|def killUser|def __killUserOnPort"),
    "PortSlave command defaults": ("IBSng/core/ras/rases/portslave.py", r"type_attrs|portslave_kill_port_command|def killUser"),
    "Quintum Tenor behavior": ("IBSng/core/ras/rases/tenor.py", r"killUser|class\s+"),
    "SNMP transport wrapper": ("IBSng/core/lib/snmp.py", r"class Snmp|def "),
    "RSH wrapper": ("IBSng/core/lib/rsh.py", r"class RSHClient|def "),
    "MultiLogin plugin": ("IBSng/core/user/plugins/multilogin.py", r"class MultiLogin|def "),
    "MS-CHAP implementation": ("IBSng/core/lib/mschap/mschap.py", r"def generate_nt_response_mschap|def generate_nt_response_mschap2|def GenerateAuthenticatorResponse"),
    "MPPE implementation": ("IBSng/core/lib/mschap/mppe.py", r"^def |^class "),
    "A1.24 PyRADIUS dictionary parser": ("IBSng/radius_server/pyrad/dictionary.py", r"^class |^    def |ipaddr|integer|VALUE"),
    "A1.24 PyRADIUS packet codec": ("IBSng/radius_server/pyrad/packet.py", r"^class |^        def _DecodeValue|^        def _EncodeValue|^        def DecodePacket|^        def EncodePacket"),
    "A1.24 attribute type encoder/decoder": ("IBSng/radius_server/pyrad/tools.py", r"^def EncodeAttr|^def DecodeAttr|integer|ipaddr|struct\.pack|struct\.unpack"),
    "A1.24 bidirectional dictionary semantics": ("IBSng/radius_server/pyrad/bidict.py", r"^class |^    def |^        def "),
}

DICT_NAMES = re.compile(
    r"Framed-IPX-Network|Framed-Routing|Acct-Authentic|Acct-Link-Count|"
    r"Acct-Input-Gigawords|Acct-Output-Gigawords|ARAP-Zone-Access|"
    r"ARAP-Security|Login-LAT-Port|Acct-Status-Type|NAS-Port-Type",
    re.IGNORECASE,
)
KILL_DEF = re.compile(r"^\s*def\s+killUser\s*\(")

def member_text(archive: tarfile.TarFile, member: tarfile.TarInfo) -> str:
    stream = archive.extractfile(member)
    if stream is None:
        return ""
    return stream.read().decode("utf-8", errors="replace")

def print_context(path: str, source: str, pattern: re.Pattern[str], before: int = 4, after: int = 18) -> None:
    lines = source.splitlines()
    hits = [i for i, line in enumerate(lines) if pattern.search(line)]
    if not hits:
        print(f"{path}: no matching source definition")
        return
    for hit in hits:
        lo, hi = max(0, hit - before), min(len(lines), hit + after + 1)
        print(f"\n### {path}:{hit + 1}")
        for i in range(lo, hi):
            print(f"{i + 1}: {lines[i][:300]}")

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
        source_py = [m for m in members if m.name.endswith(".py")]
        source_sql = [m for m in members if m.name.endswith(".sql")]
        templates = [m for m in members if m.name.endswith(".tpl")]
        print("\n== Full archive inventory ==")
        print(f"all_files={len(members)} python_source={len(source_py)} sql_files={len(source_sql)} smarty_templates={len(templates)}")
        for ext, count in Counter(Path(m.name).suffix.lower() or "[no extension]" for m in members).most_common():
            print(f"extension {ext}: {count}")

        print("\n== Concrete RAS providers (source .py only) ==")
        provider_files = [m for m in source_py if "/core/ras/rases/" in "/" + m.name]
        for member in sorted(provider_files, key=lambda m: m.name):
            print(member.name)
        print("\n== RADIUS parser and launcher source file inventory ==")
        for member in sorted(source_py, key=lambda m: m.name):
            if "/radius_server/" in "/" + member.name or re.search(r"launcher|snmp|rsh", Path(member.name).name, re.I):
                print(member.name)

        print("\n== Launcher implementation source anchors ==")
        for member in sorted(source_py, key=lambda m: m.name):
            if not ("/launcher" in member.name.lower() or "launcher" in Path(member.name).name.lower()):
                continue
            source = member_text(archive, member)
            if re.search(r"def\s+(?:system|popen3)|IBS_ADDONS|def\s+getLauncher", source):
                print_context(member.name, source, re.compile(r"def\s+(?:system|popen3)|IBS_ADDONS|def\s+getLauncher"), before=2, after=10)

        print("\n== Direct source excerpts: provider side effects and protocol invariants ==")
        by_name = {m.name: m for m in members}
        for label, (path, expr) in TARGET_FILES.items():
            member = by_name.get(path)
            print(f"\n## {label}")
            if member is None:
                print(f"ERROR: expected source file missing: {path}")
                continue
            print_context(path, member_text(archive, member), re.compile(expr))

        print("\n== Canonical dictionary declarations for changed attribute typing ==")
        dict_files = [m for m in members if m.name in {
            "IBSng/radius_server/dictionary",
            "IBSng/radius_server/dictionary.ser",
            "IBSng/radius_server/dictionary.sip",
            "IBSng/radius_server/dictionary.usr",
        }]
        for member in dict_files:
            source = member_text(archive, member)
            for number, line in enumerate(source.splitlines(), 1):
                if DICT_NAMES.search(line):
                    print(f"{member.name}:{number}:{line[:300]}")

        print("\n== All source killUser implementations ==")
        for member in sorted(provider_files, key=lambda m: m.name):
            source = member_text(archive, member)
            for number, line in enumerate(source.splitlines(), 1):
                if KILL_DEF.search(line):
                    print(f"{member.name}:{number}:{line.strip()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
