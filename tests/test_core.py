from app.core.config import get_settings
from app.core.security import hash_password, verify_password


def test_settings_loads():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql")
    assert settings.secret_key != ""
    assert settings.app_env == "development"


def test_password_hash_is_not_plain():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert hashed.startswith("$2b$")


def test_password_verify_correct():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True


def test_password_verify_wrong():
    hashed = hash_password("secret123")
    assert verify_password("wrongpassword", hashed) is False


def test_same_password_produces_different_hashes():
    # bcrypt adds a random salt — same input never produces same output
    hash1 = hash_password("secret123")
    hash2 = hash_password("secret123")
    assert hash1 != hash2


async def test_app_starts(client):
    response = await client.get("/docs")
    assert response.status_code == 200
