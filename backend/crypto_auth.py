"""
RSA-OAEP (SHA-256) helpers for encrypting credentials in transit.

Passwords are never accepted in plaintext over the API; the client encrypts
with the server public key, and the server decrypts only in memory.
"""
from __future__ import annotations

import base64
import logging
import threading

from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_private_key: Optional[rsa.RSAPrivateKey] = None


def _ensure_keys() -> rsa.RSAPrivateKey:
    global _private_key
    with _lock:
        if _private_key is None:
            _private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            logger.info("[CryptoAuth] RSA-2048 key pair generated for login encryption")
        return _private_key


def get_public_key_pem() -> str:
    """Return SubjectPublicKeyInfo PEM for Web Crypto importKey('spki')."""
    key = _ensure_keys()
    pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode("ascii")


def decrypt_password_b64(cipher_b64: str) -> str:
    """Decrypt base64 RSA-OAEP ciphertext to UTF-8 password string."""
    if not cipher_b64 or not str(cipher_b64).strip():
        raise ValueError("missing encrypted password")
    try:
        raw = base64.b64decode(str(cipher_b64).strip())
    except Exception as e:
        raise ValueError(f"invalid ciphertext encoding: {e}") from e
    key = _ensure_keys()
    try:
        plain = key.decrypt(
            raw,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except Exception as e:
        raise ValueError("password decrypt failed") from e
    try:
        return plain.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError("password is not valid UTF-8") from e


# Generate at import so first login is warm
_ensure_keys()
