from backend.app.security import hash_password, verify_password


def test_password_hash_and_verify():
    stored = hash_password("password-kuat")
    assert stored != "password-kuat"
    assert verify_password("password-kuat", stored)
    assert not verify_password("password-salah", stored)


def test_password_minimum_length():
    try:
        hash_password("pendek")
    except ValueError as exc:
        assert "minimal" in str(exc)
    else:
        raise AssertionError("Password pendek harus ditolak")
