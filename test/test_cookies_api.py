import os
import json
import base64
import jwt
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _gen_rsa_keypair():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv_pem, pub_pem


def _encrypt_storage_state(pub_pem: str, state: dict):
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os as _os
    public_key = serialization.load_pem_public_key(pub_pem.encode())
    data_key = _os.urandom(32)
    nonce = _os.urandom(12)
    aesgcm = AESGCM(data_key)
    plaintext = json.dumps(state, separators=(",", ":")).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    wrapped = public_key.encrypt(
        data_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    b64 = lambda b: base64.b64encode(b).decode()
    return {
        "ciphertext": b64(ciphertext),
        "nonce": b64(nonce),
        "wrappedKey": b64(wrapped),
    }


def _make_client(env: dict):
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = str(v)
    
    # Mock Supabase client to avoid real initialization
    with patch('backend.routers.supabase', MagicMock()):
        # Import here to ensure env is set before app init
        from backend.api import app
        return TestClient(app)


def test_public_key_and_ott_and_upload_roundtrip():
    priv_pem, pub_pem = _gen_rsa_keypair()
    env = {
        "INTERACTIVE_MODE": "false",
        "SUPABASE_JWT_SECRET": "testsecret",
        "COOKIE_PRIVATE_KEY_PEM": priv_pem,
        "COOKIE_PUBLIC_KEY_PEM": pub_pem,
        "COOKIE_KID": "rsa-test",
        "FEATURE_USE_COOKIES": "true",
    }
    client = _make_client(env)

    # Public key endpoint
    r = client.get("/crypto/public-key")
    assert r.status_code == 200
    data = r.json()
    assert data["kid"] == "rsa-test"
    assert "BEGIN PUBLIC KEY" in data["pem"]

    # Issue OTT (use a HS256 access token with sub)
    access = jwt.encode({"sub": "user-1"}, os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")
    r = client.post("/auth/ott", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    ott = r.json()["ott"]

    # Upload encrypted storage_state (cookies-only). No DB => status likely pending.
    state = {
        "cookies": [
            {"name": "auth_token", "value": "abc", "domain": ".x.com", "path": "/", "expires": 0, "httpOnly": True, "secure": True, "sameSite": "Lax"}
        ],
        "origins": []
    }
    enc = _encrypt_storage_state(pub_pem, state)
    body = {**enc, "kid": "rsa-test", "metadata": {"sites": ["x"], "version": "cookies-v1"}}
    r = client.post("/auth/storage-state", headers={"Authorization": f"Bearer {ott}"}, json=body)
    assert r.status_code == 200
    up = r.json()
    assert "id" in up and up["id"].startswith("st_")


def test_decrypt_util_roundtrip():
    # Generate keys and state, then decrypt via helper
    priv_pem, pub_pem = _gen_rsa_keypair()
    os.environ["COOKIE_PRIVATE_KEY_PEM"] = priv_pem
    from backend.cookies import decrypt_storage_state_row

    state = {
        "cookies": [
            {"name": "sessionid", "value": "xyz", "domain": ".example.com", "path": "/", "expires": 0, "httpOnly": True, "secure": True, "sameSite": "Lax"}
        ],
        "origins": []
    }
    enc = _encrypt_storage_state(pub_pem, state)
    # Simulate a DB row (base64 strings)
    row = {"ciphertext": enc["ciphertext"], "wrapped_key": enc["wrappedKey"], "nonce": enc["nonce"]}
    out = decrypt_storage_state_row(row)
    assert isinstance(out.get("cookies"), list)
    assert out["cookies"][0]["name"] == "sessionid"