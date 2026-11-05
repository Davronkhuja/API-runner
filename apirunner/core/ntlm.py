"""NTLMv2 (Windows integrated auth) httpx.Auth sifatida: 401 → Type 1 → Type 2 (challenge) → Type 3. Faqat stdlib (MD4 kerak bo'lsa sof Python)."""
import base64
import hashlib
import hmac
import os
import struct
import time

import httpx

SIG = b"NTLMSSP\x00"
F_UNICODE, F_OEM, F_REQ_TARGET, F_NTLM, F_ALWAYS_SIGN, F_EXT_SEC, F_128, F_56 = 0x1, 0x2, 0x4, 0x200, 0x8000, 0x80000, 0x20000000, 0x80000000
NEGOTIATE_FLAGS = F_UNICODE | F_OEM | F_REQ_TARGET | F_NTLM | F_ALWAYS_SIGN | F_EXT_SEC | F_128 | F_56


def _md4_py(data):
    def lrot(x, n):
        x &= 0xFFFFFFFF
        return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF
    msg = bytearray(data)
    ln = len(msg) * 8
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += struct.pack("<Q", ln)
    a, b, c, d = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    for off in range(0, len(msg), 64):
        x = struct.unpack("<16I", msg[off:off + 64])
        aa, bb, cc, dd = a, b, c, d
        f = lambda x_, y, z: (x_ & y) | (~x_ & z)  # noqa: E731
        for i in range(16):
            k, s = i, (3, 7, 11, 19)[i % 4]
            a, b, c, d = d, lrot(a + f(b, c, d) + x[k], s), b, c
        g = lambda x_, y, z: (x_ & y) | (x_ & z) | (y & z)  # noqa: E731
        for i in range(16):
            k, s = (i % 4) * 4 + i // 4, (3, 5, 9, 13)[i % 4]
            a, b, c, d = d, lrot(a + g(b, c, d) + x[k] + 0x5A827999, s), b, c
        h = lambda x_, y, z: x_ ^ y ^ z  # noqa: E731
        order = (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15)
        for i in range(16):
            k, s = order[i], (3, 9, 11, 15)[i % 4]
            a, b, c, d = d, lrot(a + h(b, c, d) + x[k] + 0x6ED9EBA1, s), b, c
        a, b, c, d = (a + aa) & 0xFFFFFFFF, (b + bb) & 0xFFFFFFFF, (c + cc) & 0xFFFFFFFF, (d + dd) & 0xFFFFFFFF
    return struct.pack("<4I", a, b, c, d)


def md4(data):
    try:
        return hashlib.new("md4", data).digest()
    except ValueError:                      # OpenSSL 3: MD4 o'chirilgan
        return _md4_py(data)


def _hmac_md5(key, msg):
    return hmac.new(key, msg, hashlib.md5).digest()


def nt_hash(password):
    return md4(password.encode("utf-16-le"))


def ntowf_v2(password, user, domain):
    return _hmac_md5(nt_hash(password), (user.upper() + domain).encode("utf-16-le"))


def negotiate_message():
    return SIG + struct.pack("<I", 1) + struct.pack("<I", NEGOTIATE_FLAGS) + struct.pack("<HHI", 0, 0, 32) + struct.pack("<HHI", 0, 0, 32)


def parse_challenge(msg):
    """Type 2 → (server_challenge, flags, target_info, timestamp | None)."""
    if msg[:8] != SIG or struct.unpack("<I", msg[8:12])[0] != 2:
        raise ValueError("NTLM: Type 2 (challenge) xabari noto'g'ri")
    flags = struct.unpack("<I", msg[20:24])[0]
    challenge = msg[24:32]
    ln, _, off = struct.unpack("<HHI", msg[40:48])
    info = msg[off:off + ln]
    ts, i = None, 0
    while i + 4 <= len(info):
        av, avlen = struct.unpack("<HH", info[i:i + 4])
        if av == 0:
            break
        if av == 7:
            ts = info[i + 4:i + 4 + avlen]
        i += 4 + avlen
    return challenge, flags, info, ts


def authenticate_message(challenge_msg, user, password, domain="", workstation="", client_challenge=None, timestamp=None):
    challenge, flags, info, ts = parse_challenge(challenge_msg)
    client_challenge = client_challenge or os.urandom(8)
    ts = ts or timestamp or struct.pack("<Q", int((time.time() + 11644473600) * 10_000_000))
    key = ntowf_v2(password, user, domain)
    blob = b"\x01\x01\x00\x00\x00\x00\x00\x00" + ts + client_challenge + b"\x00\x00\x00\x00" + info + b"\x00\x00\x00\x00"
    nt_proof = _hmac_md5(key, challenge + blob)
    nt_resp = nt_proof + blob
    lm_resp = _hmac_md5(key, challenge + client_challenge) + client_challenge
    enc = (lambda s: s.encode("utf-16-le")) if flags & F_UNICODE else (lambda s: s.encode("latin-1", "replace"))
    parts = [lm_resp, nt_resp, enc(domain), enc(user), enc(workstation), b""]
    off = 64
    fields = b""
    for p in parts:
        fields += struct.pack("<HHI", len(p), len(p), off)
        off += len(p)
    flags_out = flags & (F_UNICODE | F_OEM | F_NTLM | F_ALWAYS_SIGN | F_EXT_SEC | F_128 | F_56)
    return SIG + struct.pack("<I", 3) + fields + struct.pack("<I", flags_out) + b"".join(parts)


class NTLMAuth(httpx.Auth):
    def __init__(self, username, password, domain="", workstation=""):
        if "\\" in username and not domain:
            domain, username = username.split("\\", 1)
        self.user, self.password, self.domain, self.workstation = username, password, domain, workstation

    @staticmethod
    def _challenge(resp):
        for v in resp.headers.get_list("www-authenticate"):
            for scheme in ("NTLM", "Negotiate"):
                if v.upper().startswith(scheme + " "):
                    try:
                        return base64.b64decode(v.split(" ", 1)[1].strip())
                    except ValueError:
                        return None
        return None

    def auth_flow(self, request):
        resp = yield request
        wa = " ".join(resp.headers.get_list("www-authenticate")).upper()
        if resp.status_code != 401 or ("NTLM" not in wa and "NEGOTIATE" not in wa):
            return
        resp.read()
        request.headers["Authorization"] = "NTLM " + base64.b64encode(negotiate_message()).decode()
        resp2 = yield request
        chal = self._challenge(resp2)
        if resp2.status_code != 401 or not chal:
            return
        resp2.read()
        request.headers["Authorization"] = "NTLM " + base64.b64encode(authenticate_message(chal, self.user, self.password, self.domain, self.workstation)).decode()
        yield request
