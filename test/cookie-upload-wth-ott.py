import os, json, base64, requests
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import secrets

BASE="http://localhost:8000"
OTT=os.environ["OTT"]  # set this from your /auth/ott call

# 1) Fetch public key
pub = requests.get(f"{BASE}/crypto/public-key").json()
kid = pub["kid"]
public_key = serialization.load_pem_public_key(pub["pem"].encode())

# 2) Make a sample storage_state (cookies only)
state = state = {
  "cookies": [
    {"name":"auth_token","value":"abc","domain":".x.com","path":"/","expires":0,"httpOnly":True,"secure":True,"sameSite":"Lax"},
    {"name":"ct0","value":"xyz","domain":".x.com","path":"/","expires":0,"httpOnly":False,"secure":True,"sameSite":"Lax"}
  ],
  "origins": []
}
plaintext = json.dumps(state, separators=(",", ":")).encode()

# 3) Encrypt with AES-GCM (32-byte key, 12-byte nonce)
data_key = secrets.token_bytes(32)
nonce = secrets.token_bytes(12)
aesgcm = AESGCM(data_key)
ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)  # includes tag

# 4) Wrap the AES key with RSA-OAEP-256
wrapped = public_key.encrypt(
  data_key,
  padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
)

# 5) Base64-encode (standard, with padding)
b64 = lambda b: base64.b64encode(b).decode()
body = {
  "ciphertext": b64(ciphertext),
  "nonce": b64(nonce),
  "wrappedKey": b64(wrapped),
  "kid": kid,
  "metadata": {"sites": ["x"], "createdAt": "2025-09-17T12:34:56Z", "version": "cookies-v1"}
}

# 6) POST to /auth/storage-state
res = requests.post(f"{BASE}/auth/storage-state", json=body, headers={"Authorization": f"Bearer {OTT}"})
print(res.status_code, res.text)