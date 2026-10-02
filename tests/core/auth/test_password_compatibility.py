import bcrypt

from openagentic.core.auth.service import hash_password, verify_password


def test_new_hash_accepts_long_unicode_password_without_truncation():
    password = "商家安全密码" * 16
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password(password[:-1] + "另", hashed)


def test_existing_bcrypt_accounts_still_sign_in():
    hashed = bcrypt.hashpw(b"existing-password", bcrypt.gensalt()).decode()
    assert verify_password("existing-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_malformed_stored_password_rejected():
    assert not verify_password("password", "invalid-hash")
