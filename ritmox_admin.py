"""Painel de plataforma RITMOX: módulos, permissões e identidade da marca.

A configuração vive no esquema ritmox_auth, separada dos dados de treino.
Não altera o banco legado, nem permite personalizar a assinatura Nexon Labs.
"""
from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ritmox_auth import AuthBase, AuthUser

MODULES = (
    ("home", "Início", True),
    ("workouts", "Treinos", False),
    ("run", "Corrida", False),
    ("evolution", "Evolução", False),
    ("community", "Comunidade", False),
    ("profile", "Perfil", True),
    ("settings", "Configurações", False),
)
MODULE_KEYS = frozenset(key for key, _, _ in MODULES)
FIXED_MODULE_KEYS = frozenset(key for key, _, required in MODULES if required)
DEFAULT_PRIMARY = "#ff2d7a"
DEFAULT_SECONDARY = "#00e5ff"
MAX_BRAND_UPLOAD_BYTES = 350_000


class AppModule(AuthBase):
    __tablename__ = "platform_modules"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)


class UserModuleAccess(AuthBase):
    __tablename__ = "user_module_access"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), primary_key=True
    )
    module_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)


class PlatformBrand(AuthBase):
    __tablename__ = "platform_brand"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    primary_color: Mapped[str] = mapped_column(String(7), default=DEFAULT_PRIMARY)
    secondary_color: Mapped[str] = mapped_column(String(7), default=DEFAULT_SECONDARY)
    logo_data: Mapped[str] = mapped_column(Text, default="")
    favicon_data: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ModuleUpdate(BaseModel):
    enabled: bool
    visible: bool


class UserModuleUpdate(BaseModel):
    allowed: bool


class BrandUpdate(BaseModel):
    primary_color: str = Field(max_length=7)
    secondary_color: str = Field(max_length=7)
    logo_data: str = Field(default="", max_length=480_000)
    favicon_data: str = Field(default="", max_length=480_000)


def module_for_path(path: str) -> str | None:
    """Bloqueia também rotas API diretas, não apenas itens do menu."""
    if path.startswith(("/api/dashboard", "/api/home/")):
        return "home"
    if path.startswith((
        "/api/workouts", "/api/exercises", "/api/training-plans",
        "/api/training-program", "/api/training-methods", "/api/modalities",
        "/api/anamnesis/form",
    )):
        return "workouts"
    if path.startswith(("/api/runs", "/api/integrations/strava")):
        return "run"
    if path.startswith((
        "/api/profile", "/api/health-assessment", "/api/clearance-requests",
        "/api/professional/",
    )):
        return "profile"
    if path.startswith("/api/settings/"):
        return "settings"
    return None


def _module_row(row, module, admin: bool, personal_allowed: bool):
    key, title, required = module
    global_enabled = True if required else row.enabled
    global_visible = True if required else row.visible
    allowed = admin or required or personal_allowed
    return {
        "key": key,
        "name": title,
        "required": required,
        "enabled": global_enabled,
        "visible": global_visible,
        "allowed": allowed,
        "effective": bool(global_enabled and allowed),
    }


def _image_data(value: str, name: str) -> str:
    """Somente PNG/WebP rasterizado, limitado e verificado pelo cabeçalho."""
    if not value:
        return ""
    matched = re.fullmatch(r"data:(image/png|image/webp);base64,([a-zA-Z0-9+/=]+)", value)
    if not matched:
        raise HTTPException(422, f"{name}: utilize PNG ou WebP.")
    try:
        raw = base64.b64decode(matched.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, f"{name}: arquivo inválido.") from None
    if not 100 <= len(raw) <= MAX_BRAND_UPLOAD_BYTES:
        raise HTTPException(422, f"{name}: tamanho máximo 350 KB.")
    if matched.group(1) == "image/png" and raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise HTTPException(422, f"{name}: assinatura PNG inválida.")
    if matched.group(1) == "image/webp" and not (
        raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
    ):
        raise HTTPException(422, f"{name}: assinatura WebP inválida.")
    return value


def _color(value: str) -> str:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise HTTPException(422, "Informe a cor em formato hexadecimal (#RRGGBB).")
    return value.lower()


class AdminControl:
    def __init__(self, manager):
        self.manager = manager
        AuthBase.metadata.create_all(manager.auth_engine)
        with manager.AuthDB.begin() as db:
            for key, _, _ in MODULES:
                if db.get(AppModule, key) is None:
                    db.add(AppModule(key=key, enabled=True, visible=True))
            if db.get(PlatformBrand, 1) is None:
                db.add(PlatformBrand(id=1))

    @staticmethod
    def require_admin(request: Request):
        actor = getattr(request.state, "ritmox_actor", None)
        if not actor or not actor["is_admin"]:
            raise HTTPException(403, "Somente a Administração RITMOX pode realizar esta ação.")
        return actor

    def list_modules(self, actor, user_id=None):
        target_id = actor["id"] if user_id is None else user_id
        with self.manager.AuthDB() as db:
            if not actor["is_admin"] and target_id != actor["id"]:
                raise HTTPException(403, "Acesso não autorizado.")
            user = db.get(AuthUser, target_id)
            if not user:
                raise HTTPException(404, "Usuário não encontrado.")
            platform = {x.key: x for x in db.scalars(select(AppModule)).all()}
            personal = {
                x.module_key: x.allowed for x in db.scalars(
                    select(UserModuleAccess).where(
                        UserModuleAccess.user_id == target_id
                    )
                )
            }
            return [
                _module_row(
                    platform[key], (key, name, required),
                    user.is_admin, personal.get(key, True),
                )
                for key, name, required in MODULES
            ]

    def allowed(self, actor, module: str) -> bool:
        if actor["is_admin"]:
            return True
        modules = self.list_modules(actor)
        return next((x["effective"] for x in modules if x["key"] == module), False)

    def brand(self):
        with self.manager.AuthDB() as db:
            item = db.get(PlatformBrand, 1)
            return {
                "primary_color": item.primary_color,
                "secondary_color": item.secondary_color,
                "logo_data": item.logo_data or "",
                "favicon_data": item.favicon_data or "",
                "institutional_signature": "by Nexon Labs",
                "updated_at": item.updated_at.isoformat() if item.updated_at else "",
            }

    def install(self, app):
        control = self

        @app.get("/api/brand/public")
        def public_brand():
            return control.brand()

        @app.get("/api/platform/modules")
        def permitted_modules(request: Request):
            return control.list_modules(request.state.ritmox_actor)

        @app.get("/api/admin/modules")
        def admin_modules(request: Request):
            control.require_admin(request)
            return control.list_modules(request.state.ritmox_actor)

        @app.put("/api/admin/modules/{key}")
        def update_module(key: str, payload: ModuleUpdate, request: Request):
            control.require_admin(request)
            if key not in MODULE_KEYS:
                raise HTTPException(404, "Módulo não encontrado.")
            if key in FIXED_MODULE_KEYS and not (payload.enabled and payload.visible):
                raise HTTPException(422, "Início e Perfil são módulos essenciais.")
            with control.manager.AuthDB.begin() as db:
                item = db.get(AppModule, key)
                item.enabled = payload.enabled
                item.visible = payload.visible
            return {"ok": True, "key": key}

        @app.get("/api/admin/users/{user_id}/modules")
        def user_modules(user_id: int, request: Request):
            control.require_admin(request)
            return control.list_modules(request.state.ritmox_actor, user_id)

        @app.put("/api/admin/users/{user_id}/modules/{key}")
        def update_user_module(
            user_id: int, key: str, payload: UserModuleUpdate, request: Request
        ):
            control.require_admin(request)
            if key not in MODULE_KEYS:
                raise HTTPException(404, "Módulo não encontrado.")
            if key in FIXED_MODULE_KEYS and not payload.allowed:
                raise HTTPException(422, "Início e Perfil são módulos essenciais.")
            with control.manager.AuthDB.begin() as db:
                user = db.get(AuthUser, user_id)
                if not user:
                    raise HTTPException(404, "Usuário não encontrado.")
                if user.is_admin:
                    raise HTTPException(403, "Permissões da conta administradora são fixas.")
                item = db.get(UserModuleAccess, (user_id, key))
                if item is None:
                    item = UserModuleAccess(user_id=user_id, module_key=key)
                    db.add(item)
                item.allowed = payload.allowed
            return {"ok": True, "user_id": user_id, "key": key}

        @app.get("/api/admin/brand")
        def get_brand(request: Request):
            control.require_admin(request)
            return control.brand()

        @app.put("/api/admin/brand")
        def update_brand(payload: BrandUpdate, request: Request):
            control.require_admin(request)
            primary = _color(payload.primary_color)
            secondary = _color(payload.secondary_color)
            logo = _image_data(payload.logo_data, "Logo")
            favicon = _image_data(payload.favicon_data, "Favicon")
            with control.manager.AuthDB.begin() as db:
                brand = db.get(PlatformBrand, 1)
                brand.primary_color = primary
                brand.secondary_color = secondary
                brand.logo_data = logo
                brand.favicon_data = favicon
                brand.updated_at = datetime.now(timezone.utc)
            return {"ok": True, "institutional_signature": "by Nexon Labs"}


def install_admin(app, manager):
    control = AdminControl(manager)
    control.install(app)
    return control
