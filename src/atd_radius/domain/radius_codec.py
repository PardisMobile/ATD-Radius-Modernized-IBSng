"""RADIUS wire codec for the ATD transport boundary."""
from __future__ import annotations

from hashlib import md5
import hmac
from ipaddress import IPv4Address
from struct import pack, unpack
import secrets

from .radius import RadiusCode, RadiusPacket

_CODE_TO_BYTE = {
    RadiusCode.ACCESS_REQUEST: 1,
    RadiusCode.ACCESS_ACCEPT: 2,
    RadiusCode.ACCESS_REJECT: 3,
    RadiusCode.ACCOUNTING_REQUEST: 4,
    RadiusCode.ACCOUNTING_RESPONSE: 5,
    RadiusCode.ACCESS_CHALLENGE: 11,
    RadiusCode.DISCONNECT_REQUEST: 40,
    RadiusCode.DISCONNECT_ACK: 41,
    RadiusCode.DISCONNECT_NAK: 42,
    RadiusCode.COA_REQUEST: 43,
    RadiusCode.COA_ACK: 44,
    RadiusCode.COA_NAK: 45,
}
_BYTE_TO_CODE = {value: key for key, value in _CODE_TO_BYTE.items()}

_ATTR_NAMES = {
    1: "User-Name",
    2: "User-Password",
    3: "CHAP-Password",
    4: "NAS-IP-Address",
    5: "NAS-Port",
    6: "Service-Type",
    7: "Framed-Protocol",
    8: "Framed-IP-Address",
    9: "Framed-IP-Netmask",
    10: "Framed-Routing",
    11: "Filter-Id",
    12: "Framed-MTU",
    13: "Framed-Compression",
    14: "Login-IP-Host",
    15: "Login-Service",
    16: "Login-TCP-Port",
    18: "Reply-Message",
    19: "Callback-Number",
    20: "Callback-Id",
    22: "Framed-Route",
    23: "Framed-IPX-Network",
    24: "State",
    25: "Class",
    26: "Vendor-Specific",
    27: "Session-Timeout",
    28: "Idle-Timeout",
    29: "Termination-Action",
    30: "Called-Station-Id",
    31: "Calling-Station-Id",
    32: "NAS-Identifier",
    33: "Proxy-State",
    34: "Login-LAT-Service",
    35: "Login-LAT-Node",
    36: "Login-LAT-Group",
    37: "Framed-AppleTalk-Link",
    38: "Framed-AppleTalk-Network",
    39: "Framed-AppleTalk-Zone",
    40: "Acct-Status-Type",
    41: "Acct-Delay-Time",
    42: "Acct-Input-Octets",
    43: "Acct-Output-Octets",
    44: "Acct-Session-Id",
    45: "Acct-Authentic",
    46: "Acct-Session-Time",
    47: "Acct-Input-Packets",
    48: "Acct-Output-Packets",
    49: "Acct-Terminate-Cause",
    50: "Acct-Multi-Session-Id",
    51: "Acct-Link-Count",
    52: "Acct-Input-Gigawords",
    53: "Acct-Output-Gigawords",
    55: "Event-Timestamp",
    60: "CHAP-Challenge",
    61: "NAS-Port-Type",
    62: "Port-Limit",
    63: "Login-LAT-Port",
    68: "Acct-Tunnel-Connection",
    70: "ARAP-Password",
    71: "ARAP-Features",
    72: "ARAP-Zone-Access",
    73: "ARAP-Security",
    74: "ARAP-Security-Data",
    75: "Password-Retry",
    76: "Prompt",
    77: "Connect-Info",
    78: "Configuration-Token",
    79: "EAP-Message",
    80: "Message-Authenticator",
    84: "ARAP-Challenge-Response",
    85: "Acct-Interim-Interval",
    87: "NAS-Port-Id",
    88: "Framed-Pool",
    89: "Chargeable-User-Identity",
    95: "NAS-IPv6-Address",
    96: "Framed-Interface-Id",
    97: "Framed-IPv6-Prefix",
    98: "Login-IPv6-Host",
    99: "Framed-IPv6-Route",
    100: "Framed-IPv6-Pool",
    101: "Error-Cause",
    206: "Digest-Response",
    207: "Digest-Attributes",
}
_ATTR_NUMBERS = {name: number for number, name in _ATTR_NAMES.items()}

_INTEGER_ATTRS = {
    "NAS-Port",
    "Service-Type",
    "Framed-Protocol",
    "Framed-MTU",
    "Framed-Compression",
    "Login-Service",
    "Login-TCP-Port",
    "Framed-IPX-Network",
    "Termination-Action",
    "Framed-AppleTalk-Link",
    "Framed-AppleTalk-Network",
    "Password-Retry",
    "Prompt",
    "Acct-Interim-Interval",
    "Port-Limit",
    "Login-LAT-Port",
    "Session-Timeout",
    "Idle-Timeout",
    "Error-Cause",
    "Acct-Status-Type",
    "Acct-Delay-Time",
    "Acct-Input-Octets",
    "Acct-Output-Octets",
    "Acct-Session-Time",
    "Acct-Input-Packets",
    "Acct-Output-Packets",
    "Event-Timestamp",
    "Acct-Terminate-Cause",
    "NAS-Port-Type",
}
_IP_ATTRS = {"NAS-IP-Address", "Framed-IP-Address", "Framed-IP-Netmask", "Login-IP-Host", "Framed-IPX-Network"}
_ENUM_VALUES = {
    "Acct-Status-Type": {1: "Start", 2: "Stop", 3: "Interim-Update", 7: "Accounting-On", 8: "Accounting-Off", 15: "Failed"},
    "NAS-Port-Type": {5: "Virtual", 15: "Ethernet", 19: "Wireless-802.11"},
}
_HEX_ATTRS = {"CHAP-Password", "CHAP-Challenge", "Message-Authenticator", "State", "Class", "Proxy-State", "EAP-Message", "ARAP-Challenge-Response", "Framed-Interface-Id", "Framed-IPv6-Prefix", "Login-IPv6-Host", "Digest-Attributes"}

_MICROSOFT_VENDOR_ID = 311
_MICROSOFT_VSA_NAMES = {
    1: "MS-CHAP-Response",
    2: "MS-CHAP-Error",
    10: "MS-CHAP-Domain",
    11: "MS-CHAP-Challenge",
    25: "MS-CHAP2-Response",
    26: "MS-CHAP2-Success",
    27: "MS-CHAP2-CPW",
    16: "MS-MPPE-Send-Key",
    7: "MS-MPPE-Encryption-Policy",
    8: "MS-MPPE-Encryption-Types",
    12: "MS-CHAP-MPPE-Keys",
    17: "MS-MPPE-Recv-Key",
    18: "MS-RAS-Version",
    19: "MS-Old-ARAP-Password",
    20: "MS-New-ARAP-Password",
    21: "MS-ARAP-PW-Change-Reason",
    22: "MS-Filter",
    23: "MS-Acct-Auth-Type",
    24: "MS-Acct-EAP-Type",
    28: "MS-Primary-DNS-Server",
    29: "MS-Secondary-DNS-Server",
    30: "MS-Primary-NBNS-Server",
    31: "MS-Secondary-NBNS-Server",
}
_MICROSOFT_VSA_TYPES = {name: vendor_type for vendor_type, name in _MICROSOFT_VSA_NAMES.items()}
_MICROSOFT_VSA_TEXT_NAMES = {"MS-CHAP-Domain", "MS-CHAP2-Success", "MS-CHAP-Error", "MS-RAS-Version"}
_MICROSOFT_VSA_IP_NAMES = {"MS-Primary-DNS-Server", "MS-Secondary-DNS-Server", "MS-Primary-NBNS-Server", "MS-Secondary-NBNS-Server"}
_PROVIDER_VSAS = {
    "Cisco-AVPair": (9, 1, "string"),
    "Cisco-NAS-Port": (9, 2, "string"),
    "H323-remote-address": (9, 23, "string"),
    "H323-conf-id": (9, 24, "string"),
    "H323-disconnect-cause": (9, 30, "string"),
    "H323-incoming-conf-id": (9, 35, "string"),
    "Quintum-AVPair": (6618, 1, "string"),
    "Quintum-NAS-Port": (6618, 2, "string"),
    "Quintum-h323-conf-id": (6618, 24, "string"),
    "Quintum-h323-disconnect-cause": (6618, 30, "string"),
    "Recv-Limit": (14988, 1, "integer"),
    "Xmit-Limit": (14988, 2, "integer"),
    "Group": (14988, 3, "string"),
    "Rate-Limit": (14988, 8, "string"),
    "Host-IP": (14988, 10, "ipaddr"),
    "USR-Interface-Index": (429, 0x9843, "integer"),
}
_PROVIDER_VSA_REVERSE = {(vendor, typ): (name, kind) for name, (vendor, typ, kind) in _PROVIDER_VSAS.items()}
_USR_VENDOR_ID = 429
_USR_VSA_NAMES = {0x9843: "USR-Interface-Index"}
_USR_VSA_TYPES = {"USR-Interface-Index": 0x9843}


_SIP_ATTR_NAMES = {
    101: "Sip-Method",
    102: "Sip-Response-Code",
    103: "Sip-CSeq",
    104: "Sip-To-Tag",
    105: "Sip-From-Tag",
    106: "Sip-Branch-ID",
    107: "Sip-Translated-Request-URI",
    108: "Sip-Source-IP-Address",
    109: "Sip-Source-Port",
    110: "Sip-User-ID",
    111: "Sip-User-Realm",
    112: "Sip-User-Nonce",
    113: "Sip-User-Method",
    114: "Sip-User-Digest-URI",
    115: "Sip-User-Nonce-Count",
    116: "Sip-User-QOP",
    117: "Sip-User-Opaque",
    118: "Sip-User-Response",
    119: "Sip-User-CNonce",
    206: "Digest-Response",
    207: "Digest-Attributes",
    208: "Sip-URI-User",
    210: "Sip-Req-URI",
    211: "Sip-Group",
    212: "Sip-CC",
    213: "Sip-RPId",
    225: "SIP-AVP",
}
_SIP_ATTR_NUMBERS = {name: number for number, name in _SIP_ATTR_NAMES.items()}
_SIP_INTEGER_ATTRS = {"Sip-Method", "Sip-Response-Code", "Sip-Source-Port"}
_SIP_IP_ATTRS = {"Sip-Source-IP-Address"}

class RadiusCodecError(ValueError):
    pass


def _octets(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        text = value.strip()
        if len(text) % 2 == 0:
            try:
                return bytes.fromhex(text)
            except ValueError:
                pass
        return text.encode("utf-8")
    return str(value).encode("utf-8")


def _crypt_password(value: bytes, secret: bytes, authenticator: bytes) -> bytes:
    padded = value + bytes((-len(value)) % 16)
    result = bytearray()
    previous = authenticator
    for offset in range(0, len(padded), 16):
        previous = md5(secret + previous).digest()
        result.extend(a ^ b for a, b in zip(padded[offset : offset + 16], previous))
    return bytes(result)


def encrypt_user_password(password: str, secret: str, authenticator: bytes) -> bytes:
    if len(authenticator) != 16:
        raise RadiusCodecError("authenticator must be 16 bytes")
    value = password.encode("utf-8")
    if len(value) > 128:
        raise RadiusCodecError("User-Password exceeds 128 bytes")
    return _crypt_password(value, secret.encode("utf-8"), authenticator)


def decrypt_user_password(value: bytes, secret: str, authenticator: bytes) -> str:
    if not value or len(value) % 16:
        raise RadiusCodecError("invalid encrypted User-Password length")
    return _crypt_password(value, secret.encode("utf-8"), authenticator).rstrip(b"\x00").decode("utf-8")


def _encode_value(name: str, value: object, secret: str | None, authenticator: bytes) -> bytes:
    if name in _HEX_ATTRS:
        raw = _octets(value)
        if isinstance(value, str) and raw == value.encode("utf-8"):
            try:
                raw = bytes.fromhex(value)
            except ValueError as exc:
                raise RadiusCodecError(f"invalid hex attribute {name}") from exc
        return raw
    if name == "User-Password":
        if secret is None:
            raise RadiusCodecError("secret is required for User-Password")
        return encrypt_user_password(str(value), secret, authenticator)
    if name in _IP_ATTRS:
        try:
            return IPv4Address(str(value)).packed
        except ValueError as exc:
            raise RadiusCodecError(f"invalid IPv4 attribute {name}") from exc
    if name in _INTEGER_ATTRS:
        try:
            return pack("!I", int(value))
        except ValueError as exc:
            raise RadiusCodecError(f"invalid integer attribute {name}") from exc
    return _octets(value)


def _encrypt_ms_mppe_key(
    key: bytes,
    secret: str,
    authenticator: bytes,
    salt: bytes,
) -> bytes:
    if len(authenticator) != 16:
        raise RadiusCodecError("MS-MPPE key encryption requires a 16-byte request authenticator")
    if len(salt) != 2 or not (salt[0] & 0x80):
        raise RadiusCodecError("MS-MPPE key salt must be two bytes with the high bit set")
    if not 1 <= len(key) <= 255:
        raise RadiusCodecError("MS-MPPE key length must fit in one octet")
    plaintext = bytes((len(key),)) + key
    plaintext += bytes((-len(plaintext)) % 16)
    secret_bytes = secret.encode("utf-8")
    previous = md5(secret_bytes + authenticator + salt).digest()
    encrypted = bytearray(a ^ b for a, b in zip(plaintext[:16], previous))
    for offset in range(16, len(plaintext), 16):
        previous = md5(secret_bytes + bytes(encrypted[offset - 16 : offset])).digest()
        encrypted.extend(
            a ^ b
            for a, b in zip(plaintext[offset : offset + 16], previous)
        )
    return salt + bytes(encrypted)


def _encode_provider_vsa(name: str, value: object) -> bytes | None:
    definition = _PROVIDER_VSAS.get(name)
    if definition is None:
        return None
    vendor, vendor_type, kind = definition
    if vendor == _USR_VENDOR_ID:
        if vendor_type > 0xFFFFFFFF:
            raise RadiusCodecError(f"invalid USR VSA type: {name}")
        if kind == "integer":
            raw = pack("!I", int(value))
        elif kind == "ipaddr":
            raw = IPv4Address(str(value)).packed
        else:
            raw = _octets(value)
        return pack("!II", vendor, vendor_type) + raw
    if kind == "integer":
        raw = pack("!I", int(value))
    elif kind == "ipaddr":
        raw = IPv4Address(str(value)).packed
    else:
        raw = _octets(value)
    length = len(raw) + 2
    if length > 255:
        raise RadiusCodecError(f"VSA is too long: {name}")
    return pack("!I", vendor) + bytes((vendor_type, length)) + raw

def _encode_microsoft_vsa(
    name: str,
    value: object,
    *,
    secret: str | None,
    authenticator: bytes,
    salt: bytes | None = None,
) -> bytes:
    vendor_type = _MICROSOFT_VSA_TYPES[name]
    if name in _MICROSOFT_VSA_IP_NAMES:
        try:
            raw = IPv4Address(str(value)).packed
        except ValueError as exc:
            raise RadiusCodecError(f"invalid IPv4 attribute {name}") from exc
    else:
        raw = _octets(value)
    if name == "MS-CHAP2-Response" and len(raw) != 50:
        raise RadiusCodecError("MS-CHAP2-Response must be 50 bytes")
    if name == "MS-CHAP-MPPE-Keys":
        if secret is None:
            raise RadiusCodecError("secret is required for MS-CHAP-MPPE-Keys")
        raw = _crypt_password(raw, secret.encode("utf-8"), authenticator)
    if name in {"MS-MPPE-Send-Key", "MS-MPPE-Recv-Key"}:
        if secret is None:
            raise RadiusCodecError(f"secret is required for {name}")
        raw = _encrypt_ms_mppe_key(raw, secret, authenticator, salt or b"\x80\x01")
    vendor_length = len(raw) + 2
    if vendor_length > 255:
        raise RadiusCodecError(f"Microsoft VSA is too long: {name}")
    return pack("!I", _MICROSOFT_VENDOR_ID) + bytes((vendor_type, vendor_length)) + raw


def _decode_value(name: str, value: bytes, secret: str | None, authenticator: bytes) -> str:
    if name in _HEX_ATTRS:
        return value.hex()
    if name == "User-Password" and secret is not None:
        return decrypt_user_password(value, secret, authenticator)
    if name in _IP_ATTRS:
        if len(value) != 4:
            raise RadiusCodecError(f"invalid IPv4 length for {name}")
        return str(IPv4Address(value))
    if name in _INTEGER_ATTRS:
        if len(value) != 4:
            raise RadiusCodecError(f"invalid integer length for {name}")
        number = unpack("!I", value)[0]
        return _ENUM_VALUES.get(name, {}).get(number, str(number))
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.hex()


def _decode_vendor_specific(value: bytes) -> tuple[str, str]:
    if len(value) < 6:
        raise RadiusCodecError("Vendor-Specific attribute is too short")
    vendor_id = unpack("!I", value[:4])[0]
    if vendor_id == _USR_VENDOR_ID:
        if len(value) < 8:
            raise RadiusCodecError("USR Vendor-Specific attribute is too short")
        vendor_type = unpack("!I", value[4:8])[0]
        vendor_value = value[8:]
        name = _USR_VSA_NAMES.get(vendor_type)
        if name is not None:
            if name == "USR-Interface-Index":
                if len(vendor_value) != 4:
                    raise RadiusCodecError("invalid integer VSA length for USR-Interface-Index")
                return name, str(unpack("!I", vendor_value)[0])
            try:
                return name, vendor_value.decode("utf-8")
            except UnicodeDecodeError:
                return name, vendor_value.hex()
        return f"VSA-{vendor_id}-{vendor_type}", vendor_value.hex()
    vendor_type = value[4]
    vendor_length = value[5]
    if vendor_length < 2 or 4 + vendor_length > len(value):
        raise RadiusCodecError("invalid Vendor-Specific sub-attribute length")
    vendor_value = value[6 : 4 + vendor_length]
    known_provider = _PROVIDER_VSA_REVERSE.get((vendor_id, vendor_type))
    if known_provider is not None:
        name, kind = known_provider
        if kind == "integer":
            if len(vendor_value) != 4:
                raise RadiusCodecError(f"invalid integer VSA length for {name}")
            return name, str(unpack("!I", vendor_value)[0])
        if kind == "ipaddr":
            if len(vendor_value) != 4:
                raise RadiusCodecError(f"invalid IPv4 VSA length for {name}")
            return name, str(IPv4Address(vendor_value))
        try:
            return name, vendor_value.decode("utf-8")
        except UnicodeDecodeError:
            return name, vendor_value.hex()
    if vendor_id == _MICROSOFT_VENDOR_ID:
        name = _MICROSOFT_VSA_NAMES.get(vendor_type, f"Microsoft-{vendor_type}")
        if name in {"MS-CHAP-Response", "MS-CHAP-Challenge", "MS-CHAP2-Response", "MS-CHAP-MPPE-Keys", "MS-MPPE-Send-Key", "MS-MPPE-Recv-Key", "MS-MPPE-Encryption-Policy", "MS-MPPE-Encryption-Types"}:
            return name, vendor_value.hex()
        if name in _MICROSOFT_VSA_IP_NAMES:
            if len(vendor_value) != 4:
                raise RadiusCodecError(f"invalid IPv4 length for {name}")
            return name, str(IPv4Address(vendor_value))
        if name in _MICROSOFT_VSA_TEXT_NAMES:
            try:
                return name, vendor_value.decode("ascii")
            except UnicodeDecodeError:
                return name, vendor_value.hex()
        return name, _decode_value(name, vendor_value, None, b"")
    return f"VSA-{vendor_id}-{vendor_type}", vendor_value.hex()


def encode_sip(packet: RadiusPacket) -> bytes:
    """Encode a SIP/SER-context RADIUS packet using the canonical A1.24 SIP dictionary.

    This context is deliberately separate from the core dictionary because A1.24
    reuses attribute numbers such as 101-119 with different meanings.
    """
    if packet.code not in _CODE_TO_BYTE:
        raise RadiusCodecError(f"unsupported RADIUS code: {packet.code}")
    if len(packet.authenticator) not in (0, 16):
        raise RadiusCodecError("authenticator must be empty or 16 bytes")
    authenticator = packet.authenticator or bytes(16)
    body = bytearray()
    for name, value in packet.attributes.items():
        number = _SIP_ATTR_NUMBERS.get(name)
        if number is None:
            raise RadiusCodecError(f"unsupported SIP/SER attribute: {name}")
        if name in _SIP_INTEGER_ATTRS:
            raw = pack("!I", int(value))
        elif name in _SIP_IP_ATTRS:
            raw = IPv4Address(str(value)).packed
        else:
            raw = _octets(value)
        if len(raw) > 253:
            raise RadiusCodecError(f"attribute too long: {name}")
        body.extend(bytes((number, len(raw) + 2)))
        body.extend(raw)
    length = 20 + len(body)
    if length > 4096:
        raise RadiusCodecError("RADIUS packet exceeds 4096 bytes")
    return pack("!BBH", _CODE_TO_BYTE[packet.code], packet.identifier, length) + authenticator + body


def decode_sip(data: bytes) -> RadiusPacket:
    """Decode a RADIUS packet using the canonical A1.24 SIP/SER dictionary context."""
    if len(data) < 20:
        raise RadiusCodecError("RADIUS packet is shorter than 20 bytes")
    code_byte, identifier, length = unpack("!BBH", data[:4])
    if length < 20 or length > len(data):
        raise RadiusCodecError("invalid RADIUS packet length")
    try:
        code = _BYTE_TO_CODE[code_byte]
    except KeyError as exc:
        raise RadiusCodecError(f"unsupported RADIUS code: {code_byte}") from exc
    authenticator = data[4:20]
    attrs = {}
    offset = 20
    while offset < length:
        if offset + 2 > length:
            raise RadiusCodecError("truncated attribute header")
        number, attr_length = data[offset], data[offset + 1]
        if attr_length < 2 or offset + attr_length > length:
            raise RadiusCodecError("invalid attribute length")
        raw = data[offset + 2 : offset + attr_length]
        name = _SIP_ATTR_NAMES.get(number, f"Attr-{number}")
        if name in _SIP_INTEGER_ATTRS:
            if len(raw) != 4:
                raise RadiusCodecError(f"invalid integer length for {name}")
            value = str(unpack("!I", raw)[0])
        elif name in _SIP_IP_ATTRS:
            if len(raw) != 4:
                raise RadiusCodecError(f"invalid IPv4 length for {name}")
            value = str(IPv4Address(raw))
        else:
            try:
                value = raw.decode("utf-8")
            except UnicodeDecodeError:
                value = raw.hex()
        attrs[name] = value
        offset += attr_length
    return RadiusPacket(code, identifier, attrs, authenticator)


def encode(packet: RadiusPacket, secret: str | None = None) -> bytes:
    if packet.code not in _CODE_TO_BYTE:
        raise RadiusCodecError(f"unsupported RADIUS code: {packet.code}")
    if len(packet.authenticator) not in (0, 16):
        raise RadiusCodecError("authenticator must be empty or 16 bytes")
    authenticator = packet.authenticator or bytes(16)
    body = bytearray()
    used_mppe_salts: set[bytes] = set()
    for name, value in packet.attributes.items():
        if name in _MICROSOFT_VSA_TYPES:
            number = 26
            salt = None
            if name in {"MS-MPPE-Send-Key", "MS-MPPE-Recv-Key"}:
                while True:
                    candidate = bytes((0x80 | secrets.randbelow(0x80), secrets.randbelow(0x100)))
                    if candidate not in used_mppe_salts:
                        used_mppe_salts.add(candidate)
                        salt = candidate
                        break
            raw = _encode_microsoft_vsa(
                name,
                value,
                secret=secret,
                authenticator=authenticator,
                salt=salt,
            )
        else:
            provider_vsa = _encode_provider_vsa(name, value)
            if provider_vsa is not None:
                number = 26
                raw = provider_vsa
            else:
                number = _ATTR_NUMBERS.get(name)
            if number is None and name.startswith("Attr-"):
                try:
                    number = int(name[5:])
                except ValueError:
                    number = None
            if number is None or not 1 <= number <= 255:
                raise RadiusCodecError(f"unsupported RADIUS attribute: {name}")
            if provider_vsa is None:
                raw = _encode_value(name, value, secret, authenticator)
        if len(raw) > 253:
            raise RadiusCodecError(f"attribute too long: {name}")
        body.extend(bytes((number, len(raw) + 2)))
        body.extend(raw)
    length = 20 + len(body)
    if length > 4096:
        raise RadiusCodecError("RADIUS packet exceeds 4096 bytes")
    return pack("!BBH", _CODE_TO_BYTE[packet.code], packet.identifier, length) + authenticator + body


def decode(data: bytes, secret: str | None = None) -> RadiusPacket:
    if len(data) < 20:
        raise RadiusCodecError("RADIUS packet is shorter than 20 bytes")
    code_byte, identifier, length = unpack("!BBH", data[:4])
    if length < 20 or length > len(data):
        raise RadiusCodecError("invalid RADIUS packet length")
    try:
        code = _BYTE_TO_CODE[code_byte]
    except KeyError as exc:
        raise RadiusCodecError(f"unsupported RADIUS code: {code_byte}") from exc
    authenticator = data[4:20]
    attrs = {}
    offset = 20
    while offset < length:
        if offset + 2 > length:
            raise RadiusCodecError("truncated attribute header")
        number, attr_length = data[offset], data[offset + 1]
        if attr_length < 2 or offset + attr_length > length:
            raise RadiusCodecError("invalid attribute length")
        raw = data[offset + 2 : offset + attr_length]
        if number == 26:
            name, value = _decode_vendor_specific(raw)
        else:
            name = _ATTR_NAMES.get(number, f"Attr-{number}")
            value = _decode_value(name, raw, secret, authenticator)
        attrs[name] = value
        offset += attr_length
    return RadiusPacket(code, identifier, attrs, authenticator)


def _message_authenticator_offset(data: bytes) -> int | None:
    """Return the value offset of the unique Message-Authenticator attribute."""
    if len(data) < 20:
        raise RadiusCodecError("RADIUS packet is shorter than 20 bytes")
    length = unpack("!H", data[2:4])[0]
    if length < 20 or length > len(data):
        raise RadiusCodecError("invalid RADIUS packet length")
    offset = 20
    found = None
    while offset < length:
        if offset + 2 > length:
            raise RadiusCodecError("truncated attribute header")
        attr_length = data[offset + 1]
        if attr_length < 2 or offset + attr_length > length:
            raise RadiusCodecError("invalid attribute length")
        if data[offset] == 80:
            if attr_length != 18 or found is not None:
                raise RadiusCodecError("invalid or duplicate Message-Authenticator")
            found = offset + 2
        offset += attr_length
    return found


def verify_message_authenticator(data: bytes, secret: str) -> bool:
    """Verify RFC 2869/3579 Message-Authenticator when present."""
    try:
        offset = _message_authenticator_offset(data)
    except RadiusCodecError:
        return False
    if offset is None:
        return True
    length = unpack("!H", data[2:4])[0]
    supplied = data[offset : offset + 16]
    mutable = bytearray(data[:length])
    mutable[offset : offset + 16] = bytes(16)
    expected = hmac.new(secret.encode("utf-8"), bytes(mutable), "md5").digest()
    return hmac.compare_digest(supplied, expected)

def encode_response(response: RadiusPacket, request: RadiusPacket, secret: str) -> bytes:
    """Encode a RADIUS response, Message-Authenticator, and response authenticator."""
    if len(request.authenticator) != 16:
        raise RadiusCodecError("request authenticator must be 16 bytes")
    attributes = dict(response.attributes)
    needs_message_authenticator = (
        "Message-Authenticator" in request.attributes
        or "Message-Authenticator" in attributes
    )
    if needs_message_authenticator:
        attributes["Message-Authenticator"] = "00" * 16
        unsigned = RadiusPacket(response.code, response.identifier, attributes, request.authenticator)
        wire = encode(unsigned, secret)
        attributes["Message-Authenticator"] = hmac.new(
            secret.encode("utf-8"), wire, "md5"
        ).digest().hex()
    unsigned = RadiusPacket(response.code, response.identifier, attributes, request.authenticator)
    wire = encode(unsigned, secret)
    response_authenticator = md5(
        wire[:4] + request.authenticator + wire[20:] + secret.encode("utf-8")
    ).digest()
    return wire[:4] + response_authenticator + wire[20:]



def encode_control_request(request: RadiusPacket, secret: str) -> bytes:
    """Encode an outbound RFC 5176 Disconnect/CoA request authenticator.

    This is separate from encode_response(): control requests use a request
    authenticator computed with a zeroed authenticator field, not a response
    authenticator tied to a prior request.
    """
    if request.code not in {RadiusCode.DISCONNECT_REQUEST, RadiusCode.COA_REQUEST}:
        raise RadiusCodecError("control request encoding requires Disconnect-Request or CoA-Request")
    zero_authenticator = bytes(16)
    attributes = dict(request.attributes)
    if "Message-Authenticator" in attributes:
        attributes["Message-Authenticator"] = "00" * 16
        unsigned_for_message_auth = RadiusPacket(
            request.code, request.identifier, attributes, zero_authenticator
        )
        wire_for_message_auth = encode(unsigned_for_message_auth, secret)
        attributes["Message-Authenticator"] = hmac.new(
            secret.encode("utf-8"), wire_for_message_auth, "md5"
        ).digest().hex()

    unsigned = RadiusPacket(
        request.code, request.identifier, attributes, zero_authenticator
    )
    wire = encode(unsigned, secret)
    request_authenticator = md5(
        wire[:4] + zero_authenticator + wire[20:] + secret.encode("utf-8")
    ).digest()
    return wire[:4] + request_authenticator + wire[20:]

def verify_accounting_request(data: bytes, secret: str) -> bool:
    """Verify the RFC 2866 Accounting-Request authenticator."""
    if len(data) < 20:
        return False
    code, identifier, length = unpack("!BBH", data[:4])
    if code != 4 or length < 20 or length != len(data):
        return False
    supplied = data[4:20]
    unsigned = data[:4] + bytes(16) + data[20:length]
    expected = md5(unsigned + secret.encode("utf-8")).digest()
    return supplied == expected


def verify_control_request(data: bytes, secret: str) -> bool:
    """Verify RFC 5176 Disconnect/CoA Request-Authenticator and Message-Authenticator."""
    if len(data) < 20:
        return False
    code, identifier, length = unpack("!BBH", data[:4])
    if code not in (40, 43) or length < 20 or length > len(data):
        return False
    authenticator = data[4:20]
    unsigned = data[:4] + bytes(16) + data[20:length]
    if authenticator != md5(unsigned + secret.encode("utf-8")).digest():
        return False
    try:
        message_start = _message_authenticator_offset(data[:length])
    except RadiusCodecError:
        return False
    if message_start is None:
        return True
    message_auth = data[message_start : message_start + 16]
    mutable = bytearray(data[:length])
    mutable[4:20] = bytes(16)
    mutable[message_start : message_start + 16] = bytes(16)
    expected = hmac.new(secret.encode("utf-8"), bytes(mutable), "md5").digest()
    return hmac.compare_digest(message_auth, expected)


def verify_control_response(data: bytes, request: RadiusPacket, secret: str) -> bool:
    """Verify a Disconnect/CoA response against its originating request."""
    if request.code not in {RadiusCode.DISCONNECT_REQUEST, RadiusCode.COA_REQUEST}:
        return False
    if len(request.authenticator) != 16 or len(data) < 20:
        return False
    code, identifier, length = unpack("!BBH", data[:4])
    expected_codes = {
        40: {41, 42},
        43: {44, 45},
    }
    if code not in expected_codes.get(
        40 if request.code is RadiusCode.DISCONNECT_REQUEST else 43, set()
    ):
        return False
    if identifier != request.identifier or length < 20 or length > len(data):
        return False
    expected_authenticator = md5(
        data[:4] + request.authenticator + data[20:length] + secret.encode("utf-8")
    ).digest()
    if not hmac.compare_digest(data[4:20], expected_authenticator):
        return False
    try:
        message_offset = _message_authenticator_offset(data[:length])
    except RadiusCodecError:
        return False
    request_has_message_authenticator = "Message-Authenticator" in request.attributes
    if request_has_message_authenticator and message_offset is None:
        return False
    if message_offset is not None:
        mutable = bytearray(data[:length])
        mutable[4:20] = request.authenticator
        mutable[message_offset : message_offset + 16] = bytes(16)
        expected_message_authenticator = hmac.new(
            secret.encode("utf-8"), bytes(mutable), "md5"
        ).digest()
        if not hmac.compare_digest(
            data[message_offset : message_offset + 16],
            expected_message_authenticator,
        ):
            return False
    return True
