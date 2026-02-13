"""Unit tests for password hashing and verification."""

from app.auth.passwords import hash_password, verify_password


class TestHashPassword:
    """Test password hashing."""

    def test_hash_returns_string(self):
        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)

    def test_hash_differs_from_plaintext(self):
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"

    def test_different_passwords_different_hashes(self):
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")
        assert hash1 != hash2

    def test_same_password_different_salts(self):
        """Hashing the same password twice should produce different hashes (different salts)."""
        hash1 = hash_password("samepassword")
        hash2 = hash_password("samepassword")
        assert hash1 != hash2


class TestVerifyPassword:
    """Test password verification."""

    def test_correct_password_verifies(self):
        hashed = hash_password("testpass123")
        assert verify_password("testpass123", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("testpass123")
        assert verify_password("wrongpassword", hashed) is False

    def test_unicode_password(self):
        hashed = hash_password("p\u00e4ssw\u00f6rd\u00fc")
        assert verify_password("p\u00e4ssw\u00f6rd\u00fc", hashed) is True
        assert verify_password("password", hashed) is False

    def test_long_password(self):
        long_pass = "a" * 72  # bcrypt max is 72 bytes
        hashed = hash_password(long_pass)
        assert verify_password(long_pass, hashed) is True
