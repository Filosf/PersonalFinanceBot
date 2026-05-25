from app.services.access_tokens import create_access_token, verify_access_token


def test_access_token_roundtrip() -> None:
    token = create_access_token(123456)

    assert verify_access_token(token) == 123456
