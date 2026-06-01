from app.infrastructure.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_workspace_id,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("secret-value")
    assert verify_password("secret-value", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_decode():
    token = create_access_token("user-1", "workspace-1")
    data = decode_token(token)
    assert data["sub"] == "user-1"
    assert data["type"] == "access"
    assert token_workspace_id(data) == "workspace-1"
    assert data.get("jti")


def test_refresh_token_without_workspace():
    token = create_refresh_token("user-1")
    data = decode_token(token)
    assert data["type"] == "refresh"
    assert token_workspace_id(data) is None
