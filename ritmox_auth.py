"""RITMOX: autenticação própria e isolamento de dados por esquema PostgreSQL.

A base legada 'ritmox' permanece intacta para a primeira conta administradora.
Cada novo usuário recebe seu próprio esquema 'ritmox_u_<id>'. Não há acesso
cruzado: cada sessão SQL usa uma conexão com search_path fixado no servidor.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

COOKIE = "__Host-ritmox_session"
SESSION_DAYS = 7
HASH_ROUNDS = 420_000
AUTH_SCHEMA = "ritmox_auth"
LEGACY_SCHEMA = "ritmox"
FAILED_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
ATTEMPT_LOCK = Lock()


class AuthBase(DeclarativeBase):
    pass


class AuthUser(AuthBase):
    __tablename__ = "auth_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(256))
    data_schema: Mapped[str] = mapped_column(String(70), unique=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AuthSession(AuthBase):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped[AuthUser] = relationship()


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=220)
    password: str = Field(min_length=1, max_length=1024)


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=5, max_length=220)
    name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=1024)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Informe um e-mail válido.")
    return email


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, HASH_ROUNDS)
    return "pbkdf2_sha256:%d:%s:%s" % (HASH_ROUNDS, salt.hex(), digest.hex())


def _verify_password(password: str, encoded: str) -> bool:
    try:
        kind, rounds, salt, expected = encoded.split(":")
        if kind != "pbkdf2_sha256" or not 100_000 <= int(rounds) <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def _new_engine(db_url: str, schema: str):
    """Nunca intercala o search_path de usuários no mesmo pool de conexões."""
    if not re.fullmatch(r"ritmox(?:_auth|_u_[1-9][0-9]*)?", schema):
        raise ValueError("Nome de esquema inválido.")
    if db_url.startswith("postgresql+psycopg://"):
        return create_engine(
            db_url, pool_pre_ping=True, pool_size=1, max_overflow=2,
            connect_args={"options": "-csearch_path=" + schema + ",public"},
        )
    if not db_url.startswith("sqlite:///"):
        raise RuntimeError("RITMOX: conexão não suportada em modo multiusuário.")
    path = Path(db_url.removeprefix("sqlite:///"))
    scoped = path if schema == LEGACY_SCHEMA else path.with_name(
        path.stem + "_" + schema + path.suffix
    )
    return create_engine(
        "sqlite:///" + str(scoped), connect_args={"check_same_thread": False}
    )


class AuthManager:
    def __init__(self, db_url, data_base, seed_defaults):
        self.db_url = db_url
        self.data_base = data_base
        self.seed_defaults = seed_defaults
        self.postgres = db_url.startswith("postgresql+psycopg://")
        self.cookie_secure = os.getenv("RITMOX_COOKIE_SECURE", "true").lower() not in {
            "false", "0", "no"
        }
        self.cookie_name = COOKIE if self.cookie_secure else "ritmox_session_local"
        self.auth_engine = _new_engine(db_url, AUTH_SCHEMA)
        if self.postgres:
            with self.auth_engine.begin() as connection:
                connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS ritmox_auth")
        AuthBase.metadata.create_all(self.auth_engine)
        self.AuthDB = sessionmaker(bind=self.auth_engine, expire_on_commit=False)

        @lru_cache(maxsize=24)
        def for_schema(schema):
            return sessionmaker(
                bind=_new_engine(self.db_url, schema), expire_on_commit=False
            )
        self._sessions_for_schema = for_schema
        self._bootstrap_admin()

    def _bootstrap_admin(self):
        with self.AuthDB() as db:
            if db.scalar(select(AuthUser.id).limit(1)) is not None:
                return
            email = os.getenv("RITMOX_ADMIN_EMAIL", "").strip()
            password = os.getenv("RITMOX_ADMIN_PASSWORD", "")
            if not email or len(password) < 12:
                raise RuntimeError(
                    "RITMOX: configure RITMOX_ADMIN_EMAIL e RITMOX_ADMIN_PASSWORD "
                    "(12 caracteres ou mais) para criar a conta inicial."
                )
            db.add(AuthUser(
                email=_normalize_email(email),
                name=os.getenv("RITMOX_ADMIN_NAME", "Administrador").strip() or "Administrador",
                password_hash=_hash_password(password),
                data_schema=LEGACY_SCHEMA,
                is_admin=True,
            ))
            db.commit()

    def get_actor(self, request: Request):
        token = request.cookies.get(self.cookie_name, "")
        if len(token) < 32 or len(token) > 128:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.AuthDB() as db:
            login = db.scalar(
                select(AuthSession).join(AuthUser)
                .where(
                    AuthSession.token_hash == token_hash,
                    AuthUser.active.is_(True),
                    AuthSession.expires_at > datetime.now(timezone.utc),
                )
            )
            if login is None:
                return None
            user = login.user
            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_admin": user.is_admin,
                "schema": user.data_schema,
                "csrf": login.csrf,
                "token_hash": login.token_hash,
            }

    def data_session(self, request: Request) -> Session:
        actor = getattr(request.state, "ritmox_actor", None)
        if not actor:
            raise HTTPException(401, "Faça login para acessar seus dados.")
        db = self._sessions_for_schema(actor["schema"])()
        db.info["ritmox_actor"] = actor
        return db

    def provision_user_schema(self, schema: str):
        engine = _new_engine(self.db_url, schema)
        try:
            if self.postgres:
                with engine.begin() as conn:
                    conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS " + schema)
            self.data_base.metadata.create_all(engine)
            with Session(engine) as db:
                self.seed_defaults(db)
                db.commit()
        finally:
            engine.dispose()

    def install(self, app):
        manager = self

        @app.middleware("http")
        async def authenticate(request: Request, call_next):
            path = request.url.path
            if path in ("/health", "/saude", "/Saúde", "/api/version"):
                return await call_next(request)
            if path.startswith("/static/"):
                return await call_next(request)
            if path == "/api/auth/login":
                origin = request.headers.get("origin", "")
                if origin and urlparse(origin).netloc != request.headers.get("host", ""):
                    return JSONResponse({"detail": "Origem não autorizada."}, status_code=403)
                return await call_next(request)
            if path not in ("/", "/login", "/conta") and not path.startswith("/api/"):
                return await call_next(request)

            actor = manager.get_actor(request)
            request.state.ritmox_actor = actor
            if path == "/login" and actor:
                return RedirectResponse("/", status_code=303)
            if path in ("/", "/conta") and not actor:
                return RedirectResponse("/login", status_code=303)
            if path.startswith("/api/"):
                if actor is None:
                    return JSONResponse({"detail": "Sessão inválida. Faça login."}, status_code=401)
                if request.method not in ("GET", "HEAD", "OPTIONS"):
                    origin = request.headers.get("origin", "")
                    if origin and urlparse(origin).netloc != request.headers.get("host", ""):
                        return JSONResponse({"detail": "Origem não autorizada."}, status_code=403)
                    if not hmac.compare_digest(
                        request.headers.get("x-csrf-token", ""),
                        actor["csrf"],
                    ):
                        return JSONResponse({"detail": "Validação de segurança da sessão falhou."}, status_code=403)
            response = await call_next(request)
            if path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store"
            return response

        @app.post("/api/auth/login")
        def login(payload: LoginRequest, response: Response, request: Request):
            ip = request.client.host if request.client else "unknown"
            key = ip + ":" + payload.email.strip().lower()[:220]
            now = time.monotonic()
            with ATTEMPT_LOCK:
                FAILED_ATTEMPTS[key] = [t for t in FAILED_ATTEMPTS[key] if now - t < 900]
                if len(FAILED_ATTEMPTS[key]) >= 5:
                    raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
            with manager.AuthDB() as db:
                user = db.scalar(select(AuthUser).where(AuthUser.email == payload.email.strip().lower()))
                if not user or not user.active or not _verify_password(payload.password, user.password_hash):
                    with ATTEMPT_LOCK:
                        FAILED_ATTEMPTS[key].append(now)
                    raise HTTPException(401, "E-mail ou senha incorretos.")
                with ATTEMPT_LOCK:
                    FAILED_ATTEMPTS.pop(key, None)
                token = secrets.token_urlsafe(48)
                csrf = secrets.token_urlsafe(32)
                db.add(AuthSession(
                    user_id=user.id,
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    csrf=csrf,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
                ))
                db.commit()
                response.set_cookie(
                    manager.cookie_name, token, max_age=SESSION_DAYS * 86400,
                    httponly=True, secure=manager.cookie_secure,
                    samesite="strict", path="/",
                )
                return {"ok": True}

        @app.get("/api/auth/me")
        def me(request: Request):
            a = request.state.ritmox_actor
            return {
                "id": a["id"], "email": a["email"], "name": a["name"],
                "is_admin": a["is_admin"], "csrf": a["csrf"],
            }

        @app.post("/api/auth/logout")
        def logout(request: Request, response: Response):
            actor = request.state.ritmox_actor
            with manager.AuthDB() as db:
                active = db.scalar(select(AuthSession).where(
                    AuthSession.token_hash == actor["token_hash"]
                ))
                if active:
                    db.delete(active)
                    db.commit()
            response.delete_cookie(manager.cookie_name, path="/")
            return {"ok": True}

        @app.get("/api/auth/users")
        def users(request: Request):
            if not request.state.ritmox_actor["is_admin"]:
                raise HTTPException(403, "Acesso administrativo necessário.")
            with manager.AuthDB() as db:
                rows = db.scalars(select(AuthUser).order_by(AuthUser.id)).all()
                return [
                    {"id": u.id, "email": u.email, "name": u.name,
                     "is_admin": u.is_admin, "active": u.active}
                    for u in rows
                ]

        @app.post("/api/auth/users", status_code=201)
        def create_user(payload: CreateUserRequest, request: Request):
            if not request.state.ritmox_actor["is_admin"]:
                raise HTTPException(403, "Acesso administrativo necessário.")
            email = _normalize_email(payload.email)
            with manager.AuthDB() as db:
                if db.scalar(select(AuthUser.id).where(AuthUser.email == email)) is not None:
                    raise HTTPException(409, "Este e-mail já está cadastrado.")
                user = AuthUser(
                    email=email, name=payload.name.strip(),
                    password_hash=_hash_password(payload.password),
                    data_schema="pending", is_admin=False,
                )
                db.add(user)
                db.flush()
                schema = "ritmox_u_" + str(user.id)
                user.data_schema = schema
                manager.provision_user_schema(schema)
                db.commit()
                return {"id": user.id, "email": user.email, "name": user.name, "active": True}

        @app.post("/api/auth/change-password")
        def change_password(payload: PasswordChangeRequest, request: Request):
            a = request.state.ritmox_actor
            with manager.AuthDB() as db:
                user = db.get(AuthUser, a["id"])
                if not user or not _verify_password(payload.current_password, user.password_hash):
                    raise HTTPException(403, "Senha atual incorreta.")
                if payload.current_password == payload.new_password:
                    raise HTTPException(422, "A nova senha deve ser diferente.")
                user.password_hash = _hash_password(payload.new_password)
                for item in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)):
                    if item.token_hash != a["token_hash"]:
                        db.delete(item)
                db.commit()
            return {"ok": True}

        @app.post("/api/auth/users/{user_id}/disable")
        def disable_user(user_id: int, request: Request):
            a = request.state.ritmox_actor
            if not a["is_admin"] or a["id"] == user_id:
                raise HTTPException(403, "Operação não autorizada.")
            with manager.AuthDB() as db:
                user = db.get(AuthUser, user_id)
                if not user:
                    raise HTTPException(404, "Usuário não encontrado.")
                user.active = False
                for item in db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)):
                    db.delete(item)
                db.commit()
            return {"ok": True}

    def close(self):
        self.auth_engine.dispose()
        self._sessions_for_schema.cache_clear()
