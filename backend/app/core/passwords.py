from __future__ import annotations

from dataclasses import dataclass

from passlib.context import CryptContext
from passlib.exc import PasswordTruncateError, UnknownHashError


LEGACY_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2x$", "$2y$")


@dataclass(frozen=True)
class PasswordHashError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


class PasswordManager:
    def __init__(self) -> None:
        self._context = CryptContext(
            schemes=["argon2", "bcrypt"],
            default="argon2",
            deprecated="bcrypt",
        )

    @staticmethod
    def _password_bytes(password: str) -> bytes:
        return password.encode("utf-8")

    @staticmethod
    def _is_bcrypt_hash(hashed_password: str) -> bool:
        return hashed_password.startswith(LEGACY_BCRYPT_PREFIXES)

    def hash_password(self, password: str, scheme: str = "argon2") -> str:
        if scheme not in {"argon2", "bcrypt"}:
            raise PasswordHashError(f"Unsupported password scheme: {scheme}")

        if scheme == "bcrypt" and len(self._password_bytes(password)) > 72:
            raise PasswordHashError(
                "bcrypt cannot safely hash passwords longer than 72 UTF-8 bytes; use argon2"
            )

        return self._context.hash(password, scheme=scheme)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        if self._is_bcrypt_hash(hashed_password) and len(self._password_bytes(plain_password)) > 72:
            return False

        try:
            return self._context.verify(plain_password, hashed_password)
        except (PasswordTruncateError, UnknownHashError, ValueError):
            return False


password_manager = PasswordManager()


def get_password_hash(password: str, scheme: str = "argon2") -> str:
    return password_manager.hash_password(password, scheme=scheme)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_manager.verify_password(plain_password, hashed_password)