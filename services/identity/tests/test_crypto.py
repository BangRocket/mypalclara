import pytest
from cryptography.fernet import Fernet
from identity.crypto import encrypt_secret, decrypt_secret, get_fernet


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("SECRETS_ENCRYPTION_KEY", key)
    get_fernet.cache_clear()  # reset singleton

    ciphertext = encrypt_secret("hello-token")
    assert isinstance(ciphertext, bytes)
    assert ciphertext != b"hello-token"
    assert decrypt_secret(ciphertext) == "hello-token"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("SECRETS_ENCRYPTION_KEY", raising=False)
    get_fernet.cache_clear()
    with pytest.raises(RuntimeError, match="SECRETS_ENCRYPTION_KEY"):
        encrypt_secret("x")
