"""Testes de segurança multiusuário: sessão, CSRF, papéis e isolamento real."""
import os
import tempfile
from pathlib import Path

if not os.environ.get("DATABASE_URL"):
    _sandbox = tempfile.TemporaryDirectory(prefix="ritmox_auth_ci_")
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_sandbox.name) / "ritmox.db")

os.environ["RITMOX_REQUIRE_AUTH"] = "true"
os.environ["RITMOX_ADMIN_EMAIL"] = "owner@example.com"
os.environ["RITMOX_ADMIN_NAME"] = "Admin Inicial"
os.environ["RITMOX_ADMIN_PASSWORD"] = "SenhaTemporariaMuitoForte_2026!"
os.environ["RITMOX_COOKIE_SECURE"] = "false"
os.environ["RITMOX_CLEANUP_DEMO_DATA"] = "false"

from fastapi.testclient import TestClient

from app import app


def login(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    return me.json()


def post(client, url, csrf, payload):
    return client.post(url, json=payload, headers={"X-CSRF-Token": csrf})


def test_multiuser_security_and_data_isolation():
    admin = TestClient(app)
    alpha = TestClient(app)
    beta = TestClient(app)

    assert admin.get("/", follow_redirects=False).status_code == 303
    assert admin.get("/api/profile").status_code == 401
    assert admin.get("/api/auth/me").status_code == 401
    assert admin.get("/login").status_code == 200
    assert b"RITMOX | Acesso" in admin.get("/login").content
    assert admin.get("/docs").status_code == 404

    wrong = admin.post("/api/auth/login", json={
        "email": "owner@example.com", "password": "SenhaErrada"
    })
    assert wrong.status_code == 401
    adm = login(admin, "owner@example.com", "SenhaTemporariaMuitoForte_2026!")
    assert adm["is_admin"] is True
    assert admin.get("/conta").status_code == 200
    assert admin.get("/").status_code == 200
    assert admin.get("/api/auth/users").status_code == 200

    # A conta inicial continua usando os dados legados, nunca os dos novos membros.
    own_profile = admin.get("/api/profile").json()
    assert own_profile["name"] in ("Admin Inicial", "Júnior")
    payload = {"title":"Treino do administrador","distance_km":3.5,
               "duration_sec":1300,"avg_pace":"6:10"}
    assert post(admin, "/api/runs", adm["csrf"], payload).status_code == 200

    for client, who in (
        (alpha, ("alpha@example.com", "Conta Alfa", "NovaSenhaSeguraAlpha_2026!")),
        (beta, ("beta@example.com", "Conta Beta", "NovaSenhaSeguraBeta_2026!")),
    ):
        new = post(admin, "/api/auth/users", adm["csrf"], {
            "email":who[0], "name":who[1], "password":who[2]
        })
        assert new.status_code == 201, new.text
        account = login(client, who[0], who[2])
        assert not account["is_admin"]
        profile = client.get("/api/profile")
        assert profile.status_code == 200
        assert profile.json()["name"] == who[1]
        assert profile.json()["email"] == who[0]
        assert client.get("/api/runs/latest").json() is None
        assert client.get("/api/auth/users").status_code == 403
        assert client.get("/api/anamnesis/form").status_code == 200

    a = alpha.get("/api/auth/me").json()
    b = beta.get("/api/auth/me").json()
    run = {"title":"Somente a Alfa","distance_km":10.0,
           "duration_sec":4200,"avg_pace":"7:00"}
    assert post(alpha, "/api/runs", a["csrf"], run).status_code == 200
    assert beta.get("/api/runs/latest").json() is None
    assert admin.get("/api/runs/latest").json()["title"] == "Treino do administrador"
    assert alpha.get("/api/runs/latest").json()["title"] == "Somente a Alfa"

    # Sem CSRF não há gravação, mesmo com cookie válido.
    assert beta.post("/api/runs", json=run).status_code == 403
    assert post(beta, "/api/runs", "csrf-invalido", run).status_code == 403
    assert beta.get("/api/runs/latest").json() is None

    assert post(beta, "/api/auth/change-password", b["csrf"], {
        "current_password":"NovaSenhaSeguraBeta_2026!",
        "new_password":"NovaSenhaSeguraBeta_2026_Alterada!"
    }).status_code == 200
    assert post(beta, "/api/auth/logout", b["csrf"], {}).status_code == 200
    assert beta.get("/api/profile").status_code == 401
    assert login(beta,"beta@example.com","NovaSenhaSeguraBeta_2026_Alterada!")
    assert beta.get("/api/runs/latest").json() is None

    # Bloquear um usuário revoga imediatamente todas as sessões.
    assert post(admin, "/api/auth/users/"+str(a["id"])+"/disable", adm["csrf"], {}).status_code == 200
    assert alpha.get("/api/profile").status_code == 401

    admin.close()
    alpha.close()
    beta.close()


def test_untrusted_cross_origin_and_cannot_create_account():
    client = TestClient(app)
    data={"email":"owner@example.com","password":"SenhaTemporariaMuitoForte_2026!"}
    login_cross=client.post(
        "/api/auth/login",json=data,
        headers={"Origin":"https://attacker.example"},
    )
    assert login_cross.status_code == 403
    assert client.post("/api/auth/users", json={
        "email":"x@example.com","name":"Intruso","password":"SenhaSeguraDeIntruso1234"
    }).status_code == 401
    client.close()
