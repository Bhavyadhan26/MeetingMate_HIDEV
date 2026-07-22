from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict
from urllib.request import urlopen

try:
    from fastapi import Depends, HTTPException
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
except Exception:  # pragma: no cover
    Depends = None
    HTTPException = Exception
    HTTPBearer = None
    HTTPAuthorizationCredentials = object

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import padding, rsa


AUTH_NAMESPACE = os.getenv("AUTH0_CLAIMS_NAMESPACE", "https://meetingmate")
_bearer = HTTPBearer(auto_error=False) if HTTPBearer else None
_jwks_cache: dict[str, Any] = {"expires_at": 0.0, "keys": None}


@dataclass(frozen=True)
class UserContext:
    subject: str
    email: str
    roles: set[str]
    teams: set[str]
    claims: Dict[str, Any]

    @property
    def is_admin(self) -> bool:
        return bool({"admin", "platform_admin"} & self.roles)


def auth_required() -> bool:
    raw = os.getenv("AUTH_REQUIRED")
    if raw is not None and raw.strip():
        return raw.lower() in {"1", "true", "yes"}
    return bool(os.getenv("AUTH0_DOMAIN") and os.getenv("AUTH0_AUDIENCE"))


def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> UserContext:
    if not auth_required():
        return UserContext(
            subject="local-dev",
            email="local-dev@meetingmate.local",
            roles={"admin", "team_lead"},
            teams={"*"},
            claims={"sub": "local-dev"},
        )
    if credentials is None:
        raise HTTPException(status_code=401, detail={"code": "auth_required", "message": "Missing bearer token."})
    return verify_access_token(credentials.credentials)


def require_team_access(user: UserContext, team_id: str) -> None:
    if user.is_admin or "*" in user.teams or team_id in user.teams:
        return
    raise HTTPException(
        status_code=403,
        detail={"code": "forbidden_team", "message": "User is not allowed to access this team.", "team_id": team_id},
    )


def require_role(user: UserContext, allowed_roles: set[str]) -> None:
    if user.is_admin or user.roles & allowed_roles:
        return
    raise HTTPException(status_code=403, detail={"code": "forbidden_role", "message": "User role is not allowed."})


def verify_access_token(token: str) -> UserContext:
    domain = _auth0_domain()
    audience = os.getenv("AUTH0_AUDIENCE")
    issuer = f"https://{domain}/"
    header, claims, signing_input, signature = _decode_token_parts(token)
    key = _signing_key(header, domain)
    try:
        key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        _validate_claims(claims, issuer, audience)
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Bearer token is invalid."}) from exc
    return UserContext(
        subject=str(claims.get("sub", "")),
        email=str(claims.get("email") or claims.get(f"{AUTH_NAMESPACE}/email") or ""),
        roles=set(_claim_list(claims, "roles")),
        teams=set(_claim_list(claims, "teams")),
        claims=claims,
    )


def _decode_token_parts(token: str) -> tuple[Dict[str, Any], Dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Bearer token is invalid."})
    header = json.loads(_b64decode(parts[0]))
    claims = json.loads(_b64decode(parts[1]))
    if header.get("alg") != "RS256":
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Only RS256 tokens are accepted."})
    return header, claims, f"{parts[0]}.{parts[1]}".encode("ascii"), _b64decode(parts[2])


def _signing_key(header: Dict[str, Any], domain: str) -> Any:
    kid = header.get("kid")
    jwks = _jwks(domain)
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return _public_key_from_jwk(key_data)
    raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Token signing key was not found."})


def _public_key_from_jwk(key_data: Dict[str, Any]) -> Any:
    exponent = int.from_bytes(_b64decode(key_data["e"]), "big")
    modulus = int.from_bytes(_b64decode(key_data["n"]), "big")
    return rsa.RSAPublicNumbers(exponent, modulus).public_key()


def _validate_claims(claims: Dict[str, Any], issuer: str, audience: str | None) -> None:
    now = int(time.time())
    if claims.get("iss") != issuer:
        raise ValueError("issuer mismatch")
    if audience:
        token_audience = claims.get("aud", [])
        if isinstance(token_audience, str):
            token_audience = [token_audience]
        if not any(hmac.compare_digest(str(item), audience) for item in token_audience):
            raise ValueError("audience mismatch")
    if int(claims.get("exp", 0)) <= now:
        raise ValueError("token expired")
    if "nbf" in claims and int(claims["nbf"]) > now:
        raise ValueError("token not yet valid")


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _jwks(domain: str) -> Dict[str, Any]:
    now = time.time()
    if _jwks_cache["keys"] is not None and _jwks_cache["expires_at"] > now:
        return _jwks_cache["keys"]
    with urlopen(f"https://{domain}/.well-known/jwks.json", timeout=10) as response:
        keys = json.loads(response.read().decode("utf-8"))
    _jwks_cache["keys"] = keys
    _jwks_cache["expires_at"] = now + 3600
    return keys


def _auth0_domain() -> str:
    domain = os.getenv("AUTH0_DOMAIN", "").strip().replace("https://", "").rstrip("/")
    if not domain:
        raise HTTPException(status_code=500, detail={"code": "auth_not_configured", "message": "AUTH0_DOMAIN is required."})
    return domain


def _claim_list(claims: Dict[str, Any], name: str) -> list[str]:
    raw = claims.get(f"{AUTH_NAMESPACE}/{name}", claims.get(name, []))
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return []


def encrypt_json(value: Dict[str, Any]) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_encryption_key()).encrypt(nonce, json.dumps(value, default=str).encode("utf-8"), None)
    return "aesgcm256:" + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_json(value: str) -> Dict[str, Any]:
    if not value:
        return {}
    if not value.startswith("aesgcm256:"):
        return json.loads(value)
    raw = base64.urlsafe_b64decode(value.split(":", 1)[1].encode("ascii"))
    plaintext = AESGCM(_encryption_key()).decrypt(raw[:12], raw[12:], None)
    return json.loads(plaintext.decode("utf-8"))


def _encryption_key() -> bytes:
    raw = os.getenv("REDACTION_MAP_ENCRYPTION_KEY", "")
    if raw:
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        return hashlib.sha256(raw.encode("utf-8")).digest()
    if os.getenv("APP_ENV", "local") != "local":
        raise RuntimeError("REDACTION_MAP_ENCRYPTION_KEY is required outside local development.")
    return hashlib.sha256(b"meetingmate-local-redaction-map-key").digest()
