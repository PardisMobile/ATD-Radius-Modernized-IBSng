"""RADIUS wire codec for the ATD transport boundary."""
from __future__ import annotations

from hashlib import md5
import hmac
from ipaddress import IPv4Address
from struct import pack, unpack

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
    1:"User-Name",2:"User-Password",4:"NAS-IP-Address",5:"NAS-Port",6:"Service-Type",
    7:"Framed-Protocol",8:"Framed-IP-Address",9:"Framed-IP-Netmask",10:"Framed-Routing",
    11:"Filter-Id",12:"Framed-MTU",18:"Reply-Message",24:"State",25:"Class",
    26:"Vendor-Specific",27:"Session-Timeout",28:"Idle-Timeout",30:"Called-Station-Id",
    31:"Calling-Station-Id",32:"NAS-Identifier",40:"Acct-Status-Type",41:"Acct-Delay-Time",
    42:"Acct-Input-Octets",43:"Acct-Output-Octets",44:"Acct-Session-Id",45:"Acct-Authentic",
    46:"Acct-Session-Time",47:"Acct-Input-Packets",48:"Acct-Output-Packets",
    49:"Acct-Terminate-Cause",61:"NAS-Port-Type",80:"Message-Authenticator",
}
_ATTR_NUMBERS = {name:number for number,name in _ATTR_NAMES.items()}
_INTEGER_ATTRS = {
    "NAS-Port","Service-Type","Framed-Protocol","Framed-MTU","Session-Timeout","Idle-Timeout",
    "Acct-Status-Type","Acct-Delay-Time","Acct-Input-Octets","Acct-Output-Octets",
    "Acct-Session-Time","Acct-Input-Packets","Acct-Output-Packets","Acct-Terminate-Cause","NAS-Port-Type",
}
_IP_ATTRS = {"NAS-IP-Address","Framed-IP-Address","Framed-IP-Netmask"}


class RadiusCodecError(ValueError):
    pass


def _crypt_password(value: bytes, secret: bytes, authenticator: bytes) -> bytes:
    padded = value + bytes((-len(value)) % 16)
    result = bytearray()
    previous = authenticator
    for offset in range(0, len(padded), 16):
        previous = md5(secret + previous).digest()
        result.extend(a ^ b for a,b in zip(padded[offset:offset+16], previous))
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


def _encode_value(name: str, value: str, secret: str | None, authenticator: bytes) -> bytes:
    if name in _HEX_ATTRS:
        try:
            return bytes.fromhex(value)
        except ValueError as exc:
            raise RadiusCodecError(f"invalid hex attribute {name}") from exc
    if name == "User-Password":
        if secret is None:
            raise RadiusCodecError("secret is required for User-Password")
        return encrypt_user_password(value, secret, authenticator)
    if name in _IP_ATTRS:
        try:
            return IPv4Address(value).packed
        except ValueError as exc:
            raise RadiusCodecError(f"invalid IPv4 attribute {name}") from exc
    if name in _INTEGER_ATTRS:
        try:
            return pack("!I", int(value))
        except ValueError as exc:
            raise RadiusCodecError(f"invalid integer attribute {name}") from exc
    return value.encode("utf-8")


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
        return str(unpack("!I", value)[0])
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.hex()


def encode(packet: RadiusPacket, secret: str | None = None) -> bytes:
    if packet.code not in _CODE_TO_BYTE:
        raise RadiusCodecError(f"unsupported RADIUS code: {packet.code}")
    if len(packet.authenticator) not in (0,16):
        raise RadiusCodecError("authenticator must be empty or 16 bytes")
    authenticator = packet.authenticator or bytes(16)
    body = bytearray()
    for name,value in packet.attributes.items():
        number = _ATTR_NUMBERS.get(name)
        if number is None and name.startswith("Attr-"):
            try:
                number = int(name[5:])
            except ValueError:
                number = None
        if number is None or not 1 <= number <= 255:
            raise RadiusCodecError(f"unsupported RADIUS attribute: {name}")
        raw = _encode_value(name,str(value),secret,authenticator)
        if len(raw) > 253:
            raise RadiusCodecError(f"attribute too long: {name}")
        body.extend(bytes((number,len(raw)+2)))
        body.extend(raw)
    length = 20 + len(body)
    if length > 4096:
        raise RadiusCodecError("RADIUS packet exceeds 4096 bytes")
    return pack("!BBH",_CODE_TO_BYTE[packet.code],packet.identifier,length) + authenticator + body


def decode(data: bytes, secret: str | None = None) -> RadiusPacket:
    if len(data) < 20:
        raise RadiusCodecError("RADIUS packet is shorter than 20 bytes")
    code_byte,identifier,length = unpack("!BBH",data[:4])
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
        number,attr_length = data[offset],data[offset+1]
        if attr_length < 2 or offset + attr_length > length:
            raise RadiusCodecError("invalid attribute length")
        raw = data[offset+2:offset+attr_length]
        name = _ATTR_NAMES.get(number,f"Attr-{number}")
        attrs[name] = _decode_value(name,raw,secret,authenticator)
        offset += attr_length
    return RadiusPacket(code,identifier,attrs,authenticator)

def encode_response(response: RadiusPacket, request: RadiusPacket, secret: str) -> bytes:
    """Encode a response and calculate its RFC 2865/2866 response authenticator."""
    if len(request.authenticator) != 16:
        raise RadiusCodecError("request authenticator must be 16 bytes")
    unsigned = RadiusPacket(response.code, response.identifier, response.attributes, request.authenticator)
    wire = encode(unsigned, secret)
    response_authenticator = md5(wire[:4] + request.authenticator + wire[20:] + secret.encode("utf-8")).digest()
    return wire[:4] + response_authenticator + wire[20:]

def verify_accounting_request(data: bytes, secret: str) -> bool:
    """Verify the RFC 2866 Accounting-Request authenticator."""
    if len(data) < 20:
        return False
    code, identifier, length = unpack("!BBH", data[:4])
    if code != 4 or length < 20 or length > len(data):
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
    offset = 20
    message_auth = None
    message_start = None
    while offset < length:
        if offset + 2 > length:
            return False
        attr_length = data[offset + 1]
        if attr_length < 2 or offset + attr_length > length:
            return False
        if data[offset] == 80:
            if attr_length != 18:
                return False
            message_auth = data[offset + 2:offset + 18]
            message_start = offset
            break
        offset += attr_length
    if message_auth is None or message_start is None:
        return False
    mutable = bytearray(data[:length])
    mutable[message_start + 2:message_start + 18] = bytes(16)
    expected = hmac.new(secret.encode("utf-8"), bytes(mutable), "md5").digest()
    return hmac.compare_digest(message_auth, expected)
