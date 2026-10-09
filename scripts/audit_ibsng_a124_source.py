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
    "Cisco SNMP configuration": ("IBSng/core/ras/rases/cisco.py", r"type_attrs|cisco_snmp_version|cisco_snmp_timeout|cisco_snmp_retries|cisco_kill_use_snmp|snmp_client"),
    "Cisco SNMP/RSH kill branches": ("IBSng/core/ras/rases/cisco.py", r"def killUser|def __killUserOnPort|def __killByRSH|def __killBySnmp|def __parseAsyncPort"),
    "Cisco VPDN interface discovery and RSH": ("IBSng/core/ras/rases/cisco_vpdn.py", r"def killUser|def __killUser|def __killUserOnPort|def __killByRSH|def __findUserInterface|def __getUsernameAndRemoteIPFromUserMsg"),
    "MikroTik RSH/SSH wrapper kill": ("IBSng/core/ras/rases/mikrotik.py", r"def __init__|def killUser|mikrotik_ssh_wrapper|def __getUserIP|def __getNasPortType"),
    "PPPD command defaults": ("IBSng/core/ras/rases/pppd.py", r"type_attrs|pppd_kill_port_command|def killUser|def __killUserOnPort"),
    "PortSlave command defaults": ("IBSng/core/ras/rases/portslave.py", r"type_attrs|portslave_kill_port_command|def killUser"),
    "Quintum Tenor behavior": ("IBSng/core/ras/rases/tenor.py", r"killUser|class\s+"),
    "SNMP transport wrapper": ("IBSng/core/lib/snmp.py", r"class Snmp|def "),
    "RSH wrapper": ("IBSng/core/lib/rsh.py", r"class RSHClient|def "),
    "MultiLogin plugin": ("IBSng/core/user/plugins/multilogin.py", r"class MultiLogin|def "),
    "MS-CHAP implementation": ("IBSng/core/lib/mschap/mschap.py", r"def generate_nt_response_mschap|def generate_nt_response_mschap2|def challenge_hash|def generate_authenticator_response|def GenerateAuthenticatorResponse"),
    "MS-CHAP packet integration": ("IBSng/radius_server/pyrad/packet.py", r"def verifyMSChap2|def checkMSChapPassword|def checkMSChap2Password|def generateMSChap2AuthenticatorResponse|def addMSChapMPPEkeys|def addMSChap2MPPEkeys"),
    "MS-CHAP user plugin": ("IBSng/core/user/plugins/mschap_end.py", r"generateMSChap2AuthenticatorResponse|checkMSChap2Password|user_obj|username"),
    "MS-CHAP password plugin": ("IBSng/core/user/plugins/password.py", r"^class |^def |checkMSChap2Password|normal_username|username"),
    "MS-CHAP cryptographic utilities": ("IBSng/core/lib/mschap/utils.py", r"^def |^class |ChallengeHash|challenge_hash|NtPasswordHash|nt_password_hash|ChallengeResponse|challenge_response"),
    "MPPE implementation": ("IBSng/core/lib/mschap/mppe.py", r"^def |^class "),
    "A1.24 PyRADIUS dictionary parser": ("IBSng/radius_server/pyrad/dictionary.py", r"^class |^    def |ipaddr|integer|VALUE"),
    "A1.24 PyRADIUS packet codec": ("IBSng/radius_server/pyrad/packet.py", r"^class |^        def _DecodeValue|^        def _EncodeValue|^        def DecodePacket|^        def EncodePacket"),
    "A1.24 attribute type encoder/decoder": ("IBSng/radius_server/pyrad/tools.py", r"^def EncodeAttr|^def DecodeAttr|integer|ipaddr|struct\.pack|struct\.unpack"),
    "A1.24 bidirectional dictionary semantics": ("IBSng/radius_server/pyrad/bidict.py", r"^class |^    def |^        def "),
    "Administrator permission checks": ("IBSng/core/admin/admin.py", r"def checkPerm|def hasPerm|def canDo|def isGod|def getPerms|def isLocked"),
    "Permission value semantics": ("IBSng/core/admin/admin_perm.py", r"^class |^    def |def check|def get"),
    "Permission loader": ("IBSng/core/admin/perm_loader.py", r"^class |^    def |getPermsOfAdmin|checkPermName"),
    "Admin loading and locks": ("IBSng/core/admin/admin_loader.py", r"def getAdmin|setPerms|setLocks|__getAdminLocks|admin_locks"),
    "Permission mutation and dependencies": ("IBSng/core/admin/perm_actions.py", r"def changePermission|def __checkPermDependencies|def __checkDependenciesOfPerm|def __addPermQuery|def __changePermValueQuery|def __deletePermissionQuery"),
    "Kill-user permission definition": ("IBSng/core/admin/perms/KILL_USER.py", r"^class |^    def |dependencies|check"),
    "Change-RAS permission definition": ("IBSng/core/admin/perms/CHANGE_RAS.py", r"^class |^    def |dependencies|check"),
    "Admin web session/auth boundary": ("IBSng/interface/IBSng/inc/admin.php", r"session|admin_id|username|login|password|perm|check"),
    "Admin audit and lock mutations": ("IBSng/core/admin/admin_actions.py", r"user_audit_log|admin_locks|createInsertQuery|createUpdateQuery|createDeleteQuery"),
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
        print("\n== All archive members in MS-CHAP package, including bytecode ==")
        for member in sorted(members, key=lambda m: m.name):
            if "/core/lib/mschap/" in "/" + member.name:
                print(f"{member.name} size={member.size}")

        print("\n== RADIUS parser, launcher and MS-CHAP source file inventory ==")
        for member in sorted(source_py, key=lambda m: m.name):
            if (
                "/radius_server/" in "/" + member.name
                or "/core/lib/mschap/" in "/" + member.name
                or re.search(r"launcher|snmp|rsh", Path(member.name).name, re.I)
            ):
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
            context_after = 60 if label in {
                "MS-CHAP implementation", "MS-CHAP packet integration", "MS-CHAP user plugin", "MS-CHAP password plugin", "MS-CHAP cryptographic utilities", "MPPE implementation"
            } else 35 if label in {
                "Administrator permission checks", "Permission value semantics", "Permission loader",
                "Admin loading and locks", "Permission mutation and dependencies",
                "Kill-user permission definition", "Change-RAS permission definition",
                "Admin web session/auth boundary", "Admin audit and lock mutations",
            } else 18
            print_context(path, member_text(archive, member), re.compile(expr), after=context_after)

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
        print("\n== Complete RADIUS dictionary declarations: ATTRIBUTE / VALUE / VENDOR / INCLUDE ==")
        dictionary_members = [
            member for member in members
            if "/radius_server/" in "/" + member.name
            and Path(member.name).name.lower().startswith("dictionary")
        ]
        declaration = re.compile(r"^\s*(?:ATTRIBUTE|VALUE|VENDOR|BEGIN-VENDOR|END-VENDOR|INCLUDE)\b")
        for member in sorted(dictionary_members, key=lambda m: m.name):
            source = member_text(archive, member)
            counts = Counter(
                line.strip().split()[0]
                for line in source.splitlines()
                if declaration.search(line) and line.strip().split()
            )
            print(f"\n### {member.name} declarations={dict(counts)}")
            for number, line in enumerate(source.splitlines(), 1):
                if declaration.search(line):
                    print(f"{member.name}:{number}:{line.strip()[:300]}")

        print("\n== Automated core dictionary-to-codec parity comparison ==")
        sys.path.insert(0, str(ROOT / "src"))
        from atd_radius.domain import radius_codec as codec

        core_member = next(
            (member for member in dictionary_members if Path(member.name).name == "dictionary"),
            None,
        )
        if core_member is None:
            raise RuntimeError("canonical core RADIUS dictionary is missing")
        core_source = member_text(archive, core_member)
        core_attributes = {}
        core_values = {}
        vendor_ids = {}
        vendor_attributes = []
        current_vendor = None
        for line_number, line in enumerate(core_source.splitlines(), 1):
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            if parts[0] == "VENDOR" and len(parts) >= 3:
                try:
                    vendor_ids[parts[1]] = int(parts[2], 0)
                except ValueError:
                    pass
            elif parts[0] == "BEGIN-VENDOR" and len(parts) >= 2:
                current_vendor = parts[1]
            elif parts[0] == "END-VENDOR":
                current_vendor = None
            elif parts[0] == "ATTRIBUTE" and len(parts) >= 4:
                try:
                    number = int(parts[2], 0)
                except ValueError:
                    continue
                explicit_vendor = (
                    parts[4] if len(parts) >= 5 and parts[4] in vendor_ids else None
                )
                attribute_vendor = explicit_vendor or current_vendor
                attribute_kind = parts[3] if explicit_vendor or current_vendor else parts[-1]
                if attribute_vendor is None:
                    core_attributes[parts[1]] = (number, attribute_kind, line_number)
                else:
                    vendor_attributes.append(
                        (
                            attribute_vendor, vendor_ids.get(attribute_vendor),
                            parts[1], number, attribute_kind, line_number,
                        )
                    )
            elif parts[0] == "VALUE" and len(parts) >= 4:
                try:
                    value_number = int(parts[-1], 0)
                except ValueError:
                    continue
                core_values.setdefault(parts[1], {})[parts[2]] = value_number

        mapped_names = set(codec._ATTR_NAMES.values()) | set(codec._SIP_ATTR_NAMES.values())
        wire_core_attributes = {
            name: metadata for name, metadata in core_attributes.items()
            if 1 <= metadata[0] <= 255
        }
        vendor_names = {item[2] for item in vendor_attributes}
        integer_expected = {
            name for name, (_, kind, _) in wire_core_attributes.items()
            if kind in {"integer", "date"}
        }
        ip_expected = {
            name for name, (_, kind, _) in wire_core_attributes.items()
            if kind == "ipaddr"
        }
        ipv6_expected = {
            (name, kind) for name, (_, kind, _) in wire_core_attributes.items()
            if kind in {"ipv6addr", "ipv6prefix"}
        }
        missing_numbers = sorted(set(wire_core_attributes) - mapped_names)
        missing_integer = sorted(integer_expected - codec._INTEGER_ATTRS)
        missing_ip = sorted(ip_expected - codec._IP_ATTRS)
        wrong_integer = sorted(
            name for name in codec._INTEGER_ATTRS
            if name in wire_core_attributes and wire_core_attributes[name][1] not in {"integer", "date"}
        )
        wrong_ip = sorted(
            name for name in codec._IP_ATTRS
            if name in wire_core_attributes and wire_core_attributes[name][1] != "ipaddr"
        )
        octets_without_explicit_hex = sorted(
            name for name, (_, kind, _) in core_attributes.items()
            if kind == "octets"
            and name in wire_core_attributes
            and name not in codec._HEX_ATTRS
            and name != "Vendor-Specific"
        )

        enum_numbers = {
            name: {label: number for number, label in values.items()}
            for name, values in codec._ENUM_VALUES.items()
        }
        enum_numbers.setdefault("Acct-Status-Type", {})["Interim-Update"] = 3
        enum_numbers["Framed-Routing"] = {
            "None": 0, "Broadcast": 1, "Listen": 2, "Broadcast-Listen": 3
        }
        enum_numbers["Acct-Authentic"] = {"RADIUS": 1, "Local": 2}
        missing_enum_values = []
        enum_relevant_names = set(wire_core_attributes) | vendor_names
        for name, values in core_values.items():
            if name not in enum_relevant_names:
                continue
            for label, number in values.items():
                if enum_numbers.get(name, {}).get(label) != number:
                    missing_enum_values.append((name, label, number))

        unsupported_vendor_attributes = []
        for vendor_name, vendor_id, name, number, kind, line_number in vendor_attributes:
            provider = codec._PROVIDER_VSAS.get(name)
            microsoft_type = codec._MICROSOFT_VSA_TYPES.get(name)
            if provider is not None and provider[0] == vendor_id and provider[1] == number:
                continue
            if (
                vendor_id == codec._MICROSOFT_VENDOR_ID
                and microsoft_type == number
            ):
                continue
            unsupported_vendor_attributes.append(
                (vendor_name, vendor_id, name, number, kind, line_number)
            )

        print(f"core attributes declared={len(core_attributes)}; codec names mapped={len(mapped_names)}")
        print(f"core attributes without numeric codec mapping ({len(missing_numbers)}): {missing_numbers}")
        print(f"integer/date attributes missing integer wire handling ({len(missing_integer)}): {missing_integer}")
        print(f"ipaddr attributes missing IPv4 wire handling ({len(missing_ip)}): {missing_ip}")
        print(f"attributes incorrectly classified as integer ({len(wrong_integer)}): {wrong_integer}")
        print(f"attributes incorrectly classified as IPv4 ({len(wrong_ip)}): {wrong_ip}")
        print(f"IPv6 wire types needing dedicated review ({len(ipv6_expected)}): {sorted(ipv6_expected)}")
        print(f"octets without explicit hex/raw handling marker ({len(octets_without_explicit_hex)}): {octets_without_explicit_hex}")
        print(f"source enum labels not covered by codec ({len(missing_enum_values)}): {missing_enum_values[:100]}")
        print(f"source vendor attributes not mapped to a codec family ({len(unsupported_vendor_attributes)}): {unsupported_vendor_attributes[:100]}")

        print("\n== MS-CHAPv2 call sites across all archived text sources ==")
        mschap_calls = re.compile(
            r"generate_nt_response_mschap2|challenge_hash|MS-CHAP2-Response|AuthenticatorResponse|checkMSChap2Password|checkMSChapPassword|mppe_chap1_gen_keys|mppe_chap2_gen_keys|addMSChapMPPEkeys|addMSChap2MPPEkeys|MS-CHAP-MPPE-Keys|MS-MPPE-Send-Key|MS-MPPE-Recv-Key",
            re.IGNORECASE
        )
        call_count = 0
        for member in members:
            if member.size > 8_000_000 or not member.name.endswith((".py", ".txt", ".xml", ".sql")):
                continue
            source = member_text(archive, member)
            for number, line in enumerate(source.splitlines(), 1):
                if mschap_calls.search(line):
                    print(f"{member.name}:{number}:{line[:260]}")
                    call_count += 1
                    if call_count >= 160:
                        print("... output capped at 160 source references ...")
                        break
            if call_count >= 160:
                break

        print("\n== Native administrator permission and audit source references ==")
        admin_related = [
            member for member in members
            if member.name.endswith((".py", ".sql", ".tpl", ".php", ".xml"))
            and (
                "/core/admin/" in "/" + member.name
                or "admin" in Path(member.name).name.lower()
                or member.name.endswith(".sql")
            )
            and member.size <= 8_000_000
        ]
        for member in sorted(admin_related, key=lambda item: item.name):
            if "/core/admin/" in "/" + member.name or "admin" in Path(member.name).name.lower():
                print(f"admin source candidate: {member.name}")

        admin_permission_refs = re.compile(
            r"admin_perms|admin_perm_templates_detail|admin_perm_templates|"
            r"perm_name|checkPerm|hasPerm|isPermitted|check_permission|"
            r"checkPermission|admin_locks|user_audit_log|USER_AUDIT_LOG",
            re.IGNORECASE,
        )
        admin_hit_count = 0
        for member in sorted(admin_related, key=lambda item: item.name):
            source = member_text(archive, member)
            for number, line in enumerate(source.splitlines(), 1):
                if not admin_permission_refs.search(line):
                    continue
                print(f"{member.name}:{number}:{line[:260]}")
                admin_hit_count += 1
                if admin_hit_count >= 180:
                    print("... output capped at 180 administrator permission/audit references ...")
                    break
            if admin_hit_count >= 180:
                break

        print("\n== Administrator web authentication/session bootstrap search ==")
        auth_patterns = re.compile(
            r"session_start|session_regenerate_id|\$_SESSION|admin_id|admin_login|"
            r"login_admin|checkAdmin|isLoggedIn|isAuthenticated|authenticate|"
            r"password_verify|md5\(|sha1\(|admin_locks|isLocked",
            re.IGNORECASE,
        )
        auth_candidates = [
            member for member in members
            if member.name.startswith("IBSng/interface/")
            and member.name.endswith((".php", ".tpl", ".py", ".xml"))
            and member.size <= 2_000_000
        ]
        auth_hits = 0
        for member in sorted(auth_candidates, key=lambda item: item.name):
            source = member_text(archive, member)
            lines = source.splitlines()
            matching = [i for i, line in enumerate(lines) if auth_patterns.search(line)]
            if not matching:
                continue
            print(f"\n### AUTH FILE {member.name} hits={len(matching)}")
            for index in matching[:12]:
                lo, hi = max(0, index - 2), min(len(lines), index + 4)
                for line_no in range(lo, hi):
                    print(f"{line_no + 1}: {lines[line_no][:260]}")
                print("---")
                auth_hits += 1
                if auth_hits >= 100:
                    print("... authentication/session output capped at 100 hit contexts ...")
                    break
            if auth_hits >= 100:
                break

        print("\n== Native admin lock behavior and enforcement references ==")
        lock_patterns = re.compile(
            r"def\s+isLocked|\.isLocked\(|admin_locks|setLocks"
            r"__getAdminLocks|lockAdmin|unlockAdmin|locker_admin_id",
            re.IGNORECASE,
        )
        lock_hits = 0
        for member in sorted(members, key=lambda item: item.name):
            if not member.name.endswith((".py", ".php", ".sql", ".tpl")) or member.size > 2_000_000:
                continue
            source = member_text(archive, member)
            lines = source.splitlines()
            for index, line in enumerate(lines):
                if not lock_patterns.search(line):
                    continue
                print(f"{member.name}:{index + 1}:{line[:260]}")
                lock_hits += 1
                if lock_hits >= 160:
                    print("... lock-reference output capped at 160 lines ...")
                    break
            if lock_hits >= 160:
                break

if __name__ == "__main__":
    sys.exit(main())
