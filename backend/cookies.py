import os
import base64
import json
from typing import Optional, Dict, Any, List

from .dependencies import supabase


def _env_ttl_hours() -> Optional[int]:
    try:
        v = os.getenv("COOKIE_VERIFY_TTL_HOURS")
        return int(v) if v else None
    except Exception:
        return None


def get_cookie_upload_by_id(record_id: str) -> Optional[Dict[str, Any]]:
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
    if not supabase:
        return None
    try:
        rows = (
            supabase.table("cookie_uploads")
            .select("id,user_id,kid,ciphertext,wrapped_key,nonce,metadata,verified,status,created_at")
            .eq("user_id", user_id)
            .eq("status", "verified")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
        )
    except Exception:
        return None
    if not rows:
        return None

    # TTL filter
    ttl = _env_ttl_hours()
    if ttl is not None and ttl > 0:
        import datetime as _dt
        cutoff = _dt.datetime.utcnow() - _dt.timedelta(hours=ttl)
        def _is_fresh(r):
            ts = r.get("updated_at") or r.get("created_at")
            try:
                # Postgrest returns ISO 8601
                dt = _dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
                return dt.replace(tzinfo=None) >= cutoff
            except Exception:
                return True  # if unknown, keep
        rows = [r for r in rows if _is_fresh(r)] or rows

    if not sites:
        return rows[0]
    wanted = set(sites)
    for r in rows:
        meta_sites = set((r.get("metadata") or {}).get("sites") or [])
        if wanted.issubset(meta_sites):
            return r
    return rows[0]


def _decode_blob_field(value: Any) -> bytes:
    if value is None:
        raise ValueError("missing field")
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    s = str(value).strip()
    if s.startswith("\\x") or s.startswith("\\X"):
        raw = bytes.fromhex(s[2:])
        try:
            if raw and all((32 <= b <= 126) for b in raw):
                txt = raw.decode("ascii").replace("\n","" ).replace("\r","" ).replace(" ","")
                txt = txt.replace('-', '+').replace('_', '/')
                missing = len(txt) % 4
                if missing:
                    txt += '=' * (4 - missing)
                return base64.b64decode(txt)
        except Exception:
            pass
        return raw
    t = s.replace("\n","" ).replace("\r","" ).replace(" ","")
    t = t.replace('-', '+').replace('_', '/')
    missing = len(t) % 4
    if missing:
        t += '=' * (4 - missing)
    return base64.b64decode(t)


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

    data_key = private_key.decrypt(
        wrapped_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    aesgcm = AESGCM(data_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    state = json.loads(plaintext.decode("utf-8"))
    if not isinstance(state.get("cookies"), list):
        raise ValueError("invalid cookies format")
    if "origins" not in state:
        state["origins"] = []
    return {"cookies": state["cookies"], "origins": state.get("origins", [])}


