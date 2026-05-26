import pytest

from app.services.access_tokens import (
    AccessTokenError,
    create_access_token,
    create_csrf_token,
    create_session_token,
    verify_access_token,
    verify_csrf_token,
    verify_session_token,
)


def test_access_token_roundtrip() -> None:
    token = create_access_token(123456)

    assert verify_access_token(token) == 123456


def test_session_token_roundtrip() -> None:
    token = create_session_token(123456)

    assert verify_session_token(token) == 123456


def test_csrf_token_roundtrip() -> None:
    verify_csrf_token(create_csrf_token())


def test_rejects_tampered_token() -> None:
    token = create_session_token(123456)

    with pytest.raises(AccessTokenError):
        verify_session_token(f"{token}x")
