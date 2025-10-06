import os
import base64
import json
from typing import Optional, Dict, Any, List

from .dependencies import supabase


def get_cookie_upload_by_id(record_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a cookie_uploads row by id. Returns None if not found or DB disabled.

    Fields returned are limited to what is needed for decryption and metadata display.
    """
    if not supabase:
        return None
    try:
        data = (
            supabase.table("cookie_uploads")
            .select("id,user_id,kid,ciphertext,wrapped_key,nonce,metadata,verified,status,created_at,updated_at")
            .eq("id", record_id)
            .single()
            .execute()
            .data
        )
        return data
    except Exception:
        return None


def get_latest_verified_cookie_upload(user_id: str, sites: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Fetch the latest verified cookie upload for a user.

    If sites is provided, prefers records whose metadata.sites cover all requested sites; otherwise returns newest verified.
    """
    if not supabase:
        return None

    try:
        # Get latest verified uploads for user
        rows = (
            supabase.table("cookie_uploads")
            .select("id,user_id,kid,ciphertext,wrapped_key,nonce,metadata,verified,status,created_at")
            .eq("user_id", user_id)
            .eq("status", "verified")
            .order("created_at", desc=True)
            .limit(25)
            .execute()
            .data
        )
    except Exception:
        return None

    if not rows:
        return None

    if not sites:
        return rows[0]

    wanted = set(sites)
    for r in rows:
        meta_sites = set((r.get("metadata") or {}).get("sites") or [])
        if wanted.issubset(meta_sites):
            return r
    return rows[0]


# ──────────────────────────────────────────────────────────────────────────────
# Decryption utilities
# ──────────────────────────────────────────────────────────────────────────────

def _decode_blob_field(value: Any) -> bytes:
    """Decode a field that may be Postgres hex bytea ("\\x.."), base64/base64url, or bytes."""
    if value is None:
        raise ValueError("missing field")
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    s = str(value).strip()
    # Hex bytea: "\\xDEADBEEF"
    if s.startswith("\\x") or s.startswith("\\X"):
        try:
            raw = bytes.fromhex(s[2:])
            # If raw looks like base64 ASCII, decode one more layer
            try:
                if raw and all((32 <= b <= 126) for b in raw):
                    txt = raw.decode("ascii")
                    t = txt.replace("\n", "").replace("\r", "").replace(" ", "")
                    t = t.replace('-', '+').replace('_', '/')
                    missing = len(t) % 4
                    if missing:
                        t += '=' * (4 - missing)
                    return base64.b64decode(t)
            except Exception:
                pass
            return raw
        except Exception as e:
            raise ValueError(f"invalid hex bytea: {e}")
    # Base64 / base64url
    t = s.replace("\n", "").replace("\r", "").replace(" ", "")
    t = t.replace('-', '+').replace('_', '/')
    missing = len(t) % 4
    if missing:
        t += '=' * (4 - missing)
    try:
        return base64.b64decode(t)
    except Exception as e:
        # last try urlsafe
        try:
            return base64.urlsafe_b64decode(t + '=' * ((4 - len(t) % 4) % 4))
        except Exception:
            raise ValueError(f"invalid base64: {e}")


def _load_private_key():
    from cryptography.hazmat.primitives import serialization
    pem = os.getenv("COOKIE_PRIVATE_KEY_PEM")
    path = os.getenv("COOKIE_PRIVATE_KEY_PATH")
    if not pem and path and os.path.exists(path):
        with open(path, "r") as f:
            pem = f.read()
    if not pem:
        raise RuntimeError("Private key not configured (COOKIE_PRIVATE_KEY_PEM/_PATH)")
    return serialization.load_pem_private_key(pem.encode("utf-8"), password=None)


def decrypt_storage_state_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt a cookie_uploads row into a Playwright-compatible storage_state dict.

    Returns: { "cookies": [...], "origins": [] }
    Raises ValueError on decode/decrypt errors.
    """
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as e:
        raise RuntimeError("Cryptography library not available") from e

    private_key = _load_private_key()

    wrapped_key = _decode_blob_field(row.get("wrapped_key"))
    nonce = _decode_blob_field(row.get("nonce"))
    ciphertext = _decode_blob_field(row.get("ciphertext"))

    try:
        data_key = private_key.decrypt(
            wrapped_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
    except Exception as e:
        raise ValueError(f"unwrap_failed: {e}")

    try:
        aesgcm = AESGCM(data_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
        state = json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"decrypt_failed: {e}")

    # Normalize minimal schema
    cookies = state.get("cookies") or []
    if not isinstance(cookies, list):
        raise ValueError("invalid cookies format")
    if "origins" not in state:
        state["origins"] = []
    return {"cookies": cookies, "origins": state.get("origins", [])}
