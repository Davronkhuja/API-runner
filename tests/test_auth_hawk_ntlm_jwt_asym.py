"""JWT RS*/PS*/ES*, Hawk (rasmiy vektor), NTLMv2 (MS-NLMP vektorlari + httpx oqimi)."""
import base64
import json
import struct

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from apirunner.core import ntlm
from apirunner.core.auth import hawk_header, make_jwt


def pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


def split(tok):
    h, p, s = tok.split(".")
    d = lambda x: base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))  # noqa: E731
    return json.loads(d(h)), json.loads(d(p)), d(s), f"{h}.{p}".encode()


@pytest.mark.parametrize("alg,hname", [("RS256", "SHA256"), ("RS384", "SHA384"), ("RS512", "SHA512")])
def test_jwt_rs_signature_verifies(alg, hname):
    key = rsa.generate_private_key(65537, 2048)
    h, p, sig, signing = split(make_jwt({"algorithm": alg, "privateKey": pem(key), "payload": '{"a":1}'}, {}))
    assert h["alg"] == alg and p == {"a": 1}
    key.public_key().verify(sig, signing, padding.PKCS1v15(), getattr(hashes, hname)())


def test_jwt_ps256_signature_verifies():
    key = rsa.generate_private_key(65537, 2048)
    _, _, sig, signing = split(make_jwt({"algorithm": "PS256", "privateKey": pem(key)}, {}))
    key.public_key().verify(sig, signing, padding.PSS(padding.MGF1(hashes.SHA256()), 32), hashes.SHA256())


@pytest.mark.parametrize("alg,curve,size,h", [("ES256", ec.SECP256R1(), 32, hashes.SHA256()), ("ES384", ec.SECP384R1(), 48, hashes.SHA384()), ("ES512", ec.SECP521R1(), 66, hashes.SHA512())])
def test_jwt_es_signature_is_raw_r_s_and_verifies(alg, curve, size, h):
    key = ec.generate_private_key(curve)
    _, _, sig, signing = split(make_jwt({"algorithm": alg, "privateKey": pem(key)}, {}))
    assert len(sig) == 2 * size                                          # JOSE r||s, DER emas
    der = encode_dss_signature(int.from_bytes(sig[:size], "big"), int.from_bytes(sig[size:], "big"))
    key.public_key().verify(der, signing, ec.ECDSA(h))


def test_jwt_asym_errors():
    ec_key = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(ValueError, match="private key"):
        make_jwt({"algorithm": "RS256"}, {})
    with pytest.raises(ValueError, match="RSA"):
        make_jwt({"algorithm": "RS256", "privateKey": pem(ec_key)}, {})
    with pytest.raises(ValueError, match="secp384r1"):
        make_jwt({"algorithm": "ES384", "privateKey": pem(ec_key)}, {})
    with pytest.raises(ValueError, match="o'qilmadi"):
        make_jwt({"algorithm": "ES256", "privateKey": "not a pem"}, {})


def test_jwt_private_key_from_variable_and_passphrase():
    key = ec.generate_private_key(ec.SECP256R1())
    enc = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(b"pw")).decode()
    tok = make_jwt({"algorithm": "ES256", "privateKey": "{{k}}", "passphrase": "pw"}, {"k": enc})
    assert tok.count(".") == 2


def test_jwt_rs256_through_engine(client, echo):
    key = rsa.generate_private_key(65537, 2048)
    d = client.post("/run_one", json={"url": echo + "/echo", "auth_config": {"type": "jwt", "algorithm": "RS256", "privateKey": pem(key), "payload": '{"x":1}'}}).get_json()
    assert d["response"]["headers"]["Authorization"].startswith("Bearer eyJ")


# ── Hawk ──
HAWK = {"id": "dh37fgj492je", "key": "werxhqb98rpaxn39848xrunpaw3489ruxnpa98w4rxn", "algorithm": "sha256", "ext": "some-app-ext-data"}


def test_hawk_matches_official_reference_vector():
    h = hawk_header(HAWK, "GET", "http://example.com:8000/resource/1?b=1&a=2", ts=1353832234, nonce="j4h3g2")
    assert h == 'Hawk id="dh37fgj492je", ts="1353832234", nonce="j4h3g2", ext="some-app-ext-data", mac="6R4rV5iE+NPoym+WwjeHzjAGXUtLNIxmo1vpMofpLAE="'


def test_hawk_payload_hash_changes_mac_and_is_included():
    base = hawk_header({**HAWK, "includePayloadHash": "true"}, "POST", "http://example.com/x", b'{"a":1}', "application/json; charset=utf-8", ts=1, nonce="n")
    other = hawk_header({**HAWK, "includePayloadHash": "true"}, "POST", "http://example.com/x", b'{"a":2}', "application/json", ts=1, nonce="n")
    assert 'hash="' in base and base != other


def test_hawk_requires_id_and_key_and_works_through_engine(client, echo):
    with pytest.raises(ValueError):
        hawk_header({"id": "", "key": ""}, "GET", "http://x/")
    d = client.post("/run_one", json={"url": echo + "/echo?q=1", "auth_config": {"type": "hawk", "id": "i", "key": "k"}}).get_json()
    assert d["response"]["headers"]["Authorization"].startswith('Hawk id="i"')


# ── NTLM ──
def test_ntlm_ms_nlmp_vectors():
    assert ntlm.nt_hash("Password").hex() == "a4f49c406510bdcab6824ee7c30fd852"
    assert ntlm.ntowf_v2("Password", "User", "Domain").hex() == "0c868a403bfd7a93a3001ef22ef02e3f"
    assert ntlm._md4_py(b"abc").hex() == "a448017aaf21d8525fc10ae87aa6729d"


def _type2(challenge=b"\x01\x23\x45\x67\x89\xab\xcd\xef"):
    info = struct.pack("<HH", 2, 8) + "DOM".encode("utf-16-le")[:6].ljust(8, b"\0") + struct.pack("<HH", 0, 0)
    off = 48
    return ntlm.SIG + struct.pack("<I", 2) + struct.pack("<HHI", 0, 0, off) + struct.pack("<I", ntlm.NEGOTIATE_FLAGS) + challenge + b"\0" * 8 + struct.pack("<HHI", len(info), len(info), off) + info


def test_ntlm_type3_nt_proof_is_correct():
    t2, cc, ts = _type2(), b"\xaa" * 8, b"\x00" * 8
    msg = ntlm.authenticate_message(t2, "User", "Password", "Domain", "WS", client_challenge=cc, timestamp=ts)
    assert msg[:8] == ntlm.SIG and struct.unpack("<I", msg[8:12])[0] == 3
    nt_len, _, nt_off = struct.unpack("<HHI", msg[20:28])
    nt = msg[nt_off:nt_off + nt_len]
    key = ntlm.ntowf_v2("Password", "User", "Domain")
    assert nt[:16] == ntlm._hmac_md5(key, b"\x01\x23\x45\x67\x89\xab\xcd\xef" + nt[16:])    # NTProofStr = HMAC(key, challenge + blob)
    ulen, _, uoff = struct.unpack("<HHI", msg[36:44])
    assert msg[uoff:uoff + ulen].decode("utf-16-le") == "User"


def test_ntlm_three_step_handshake_via_httpx():
    seen = []

    def handler(req):
        a = req.headers.get("authorization", "")
        seen.append(a[:13])
        if not a:
            return httpx.Response(401, headers={"WWW-Authenticate": "NTLM"})
        raw = base64.b64decode(a.split(" ", 1)[1])
        t = struct.unpack("<I", raw[8:12])[0]
        if t == 1:
            return httpx.Response(401, headers={"WWW-Authenticate": "NTLM " + base64.b64encode(_type2()).decode()})
        assert t == 3
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        r = c.get("http://srv.test/", auth=ntlm.NTLMAuth("DOM\\User", "Password"))
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert seen == ["", "NTLM TlRMTVNT", "NTLM TlRMTVNT"]


def test_ntlm_skips_when_server_does_not_ask():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as c:
        assert c.get("http://srv.test/", auth=ntlm.NTLMAuth("u", "p")).status_code == 200
