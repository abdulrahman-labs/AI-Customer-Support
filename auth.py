"""المصادقة: التسجيل، تسجيل الدخول، الجلسات، وإدارة كلمات المرور."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time

from database import db, now

ITERATIONS = 240_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
MAX_FAILED = 5
LOCK_SECONDS = 600
SESSION_DAYS = 7
GENERIC_LOGIN_ERROR = "البريد الإلكتروني أو كلمة المرور غير صحيحة."
_PUBLIC = ("id", "email", "name", "role", "is_active", "created_at", "last_login")


# ───────────────────────── كلمات المرور ─────────────────────────
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(calc.hex(), digest)
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password("dummy-password-for-timing")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def password_error(password: str) -> str | None:
    if len(password) < 8:
        return "كلمة المرور يجب ألا تقل عن 8 أحرف."
    if not re.search(r"[A-Za-z\u0600-\u06FF]", password) or not re.search(r"\d", password):
        return "كلمة المرور يجب أن تحتوي على حروف وأرقام."
    if len(password) > 128:
        return "كلمة المرور طويلة جداً."
    return None


def _public(row) -> dict | None:
    return {k: row[k] for k in _PUBLIC} if row else None


# ───────────────────────── المستخدمون ─────────────────────────
def get_user(user_id: int) -> dict | None:
    with db() as c:
        return _public(c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())


def register(name: str, email: str, password: str) -> tuple[dict | None, str | None]:
    name, email = " ".join((name or "").split()), normalize_email(email)
    if not 2 <= len(name) <= 60:
        return None, "الاسم يجب أن يكون بين حرفين و60 حرفاً."
    if not EMAIL_RE.match(email):
        return None, "البريد الإلكتروني غير صالح."
    if err := password_error(password):
        return None, err
    try:
        with db() as c:
            uid = c.execute(
                "INSERT INTO users (email, name, password_hash, role, created_at, last_login) VALUES (?,?,?,?,?,?)",
                (email, name, hash_password(password), "user", now(), now()),
            ).lastrowid
    except sqlite3.IntegrityError:
        return None, "هذا البريد الإلكتروني مسجّل بالفعل."
    return get_user(uid), None


def authenticate(email: str, password: str) -> tuple[dict | None, str | None]:
    email = normalize_email(email)
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row is None:
            verify_password(password, _DUMMY_HASH)  # توحيد زمن الاستجابة
            return None, GENERIC_LOGIN_ERROR
        if row["locked_until"] > time.time():
            mins = int((row["locked_until"] - time.time()) // 60) + 1
            return None, f"تم إيقاف المحاولات مؤقتاً. أعد المحاولة بعد {mins} دقيقة."
        if not verify_password(password, row["password_hash"]):
            failed = row["failed_attempts"] + 1
            locked = time.time() + LOCK_SECONDS if failed >= MAX_FAILED else 0
            c.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?",
                      (0 if locked else failed, locked, row["id"]))
            return None, GENERIC_LOGIN_ERROR
        if not row["is_active"]:
            return None, "تم إيقاف هذا الحساب. تواصل مع الدعم."
        c.execute("UPDATE users SET failed_attempts=0, locked_until=0, last_login=? WHERE id=?", (now(), row["id"]))
        return _public(row), None


def update_name(user_id: int, name: str) -> str | None:
    name = " ".join((name or "").split())
    if not 2 <= len(name) <= 60:
        return "الاسم يجب أن يكون بين حرفين و60 حرفاً."
    with db() as c:
        c.execute("UPDATE users SET name=? WHERE id=?", (name, user_id))
    return None


def change_password(user_id: int, current: str, new: str) -> str | None:
    with db() as c:
        row = c.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or not verify_password(current, row["password_hash"]):
            return "كلمة المرور الحالية غير صحيحة."
        if err := password_error(new):
            return err
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new), user_id))
        c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    return None


def admin_reset_password(user_id: int) -> str:
    temp = secrets.token_urlsafe(9) + "7"
    with db() as c:
        c.execute("UPDATE users SET password_hash=?, failed_attempts=0, locked_until=0 WHERE id=? AND role='user'",
                  (hash_password(temp), user_id))
        c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    return temp


def set_active(user_id: int, active: bool) -> None:
    with db() as c:
        c.execute("UPDATE users SET is_active=? WHERE id=? AND role='user'", (int(active), user_id))
        if not active:
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))


def delete_account(user_id: int, password: str) -> str | None:
    with db() as c:
        row = c.execute("SELECT password_hash, role FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            return "كلمة المرور غير صحيحة."
        if row["role"] == "admin":
            return "لا يمكن حذف حساب المدير من هنا."
        c.execute("DELETE FROM tickets WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM users WHERE id=?", (user_id,))
    return None


def ensure_admin(email: str, password: str) -> None:
    """المدير الوحيد هو صاحب هذا البريد (من الإعدادات السرية). أي حساب آخر يعود مستخدماً عادياً."""
    email = normalize_email(email)
    if not EMAIL_RE.match(email):
        raise ValueError("ADMIN_EMAIL غير صالح.")
    if err := password_error(password):
        raise ValueError(f"ADMIN_PASSWORD: {err}")
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row is None:
            c.execute(
                "INSERT INTO users (email, name, password_hash, role, created_at) VALUES (?,?,?,?,?)",
                (email, "مدير النظام", hash_password(password), "admin", now()),
            )
        else:
            c.execute("UPDATE users SET role='admin', is_active=1 WHERE id=?", (row["id"],))
            if not verify_password(password, row["password_hash"]):
                c.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), row["id"]))
                c.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
        c.execute("UPDATE users SET role='user' WHERE role='admin' AND email<>?", (email,))


# ───────────────────────── الجلسات (تذكّرني) ─────────────────────────
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with db() as c:
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
        c.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?,?,?)",
                  (_hash_token(token), user_id, time.time() + SESSION_DAYS * 86400))
    return token


def user_from_token(token: str) -> dict | None:
    with db() as c:
        row = c.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash=? AND s.expires_at>? AND u.is_active=1",
            (_hash_token(token), time.time()),
        ).fetchone()
    return _public(row)


def revoke_session(token: str) -> None:
    with db() as c:
        c.execute("DELETE FROM sessions WHERE token_hash=?", (_hash_token(token),))
