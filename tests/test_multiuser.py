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


def test_admin_controls_modules_and_institutional_brand():
    import base64

    admin=TestClient(app)
    member=TestClient(app)
    assert member.get("/api/admin/modules").status_code == 401
    assert member.get("/api/admin/brand").status_code == 401
    me=login(admin,"owner@example.com","SenhaTemporariaMuitoForte_2026!")
    assert me["is_admin"]

    created=post(admin,"/api/auth/users",me["csrf"],{
        "email":"module-member@example.com",
        "name":"Aluno Módulos",
        "password":"SenhaTemporariaModulo_2026!"
    })
    assert created.status_code == 201, created.text
    member_id=created.json()["id"]
    other=login(member,"module-member@example.com","SenhaTemporariaModulo_2026!")
    assert member.get("/api/admin/modules").status_code == 403
    assert member.get("/api/admin/brand").status_code == 403
    assert member.get("/api/admin/users/"+str(member_id)+"/modules").status_code == 403

    modules=admin.get("/api/admin/modules").json()
    assert set(x["key"] for x in modules)=={
        "home","workouts","run","evolution","community","profile","settings"
    }
    assert all(x["effective"] for x in modules)
    assert post(admin,"/api/admin/modules/run",me["csrf"],{
        "enabled":False,"visible":False
    }).status_code == 405  # O painel usa PUT, não POST.
    assert admin.put("/api/admin/modules/run",json={
        "enabled":False,"visible":False
    },headers={"X-CSRF-Token":me["csrf"]}).status_code == 200
    assert member.get("/api/runs/latest").status_code == 403
    assert admin.get("/api/runs/latest").status_code == 200
    listed=member.get("/api/platform/modules").json()
    assert next(x for x in listed if x["key"]=="run")["effective"] is False

    # O administrador não pode desligar Início/Perfil nem desativar seu próprio acesso.
    result=admin.put("/api/admin/modules/home",json={
        "enabled":False,"visible":False
    },headers={"X-CSRF-Token":me["csrf"]})
    assert result.status_code == 422
    assert admin.put("/api/admin/modules/run",json={
        "enabled":True,"visible":True
    },headers={"X-CSRF-Token":me["csrf"]}).status_code == 200

    disable=admin.put("/api/admin/users/"+str(member_id)+"/modules/workouts",
        json={"allowed":False},headers={"X-CSRF-Token":me["csrf"]})
    assert disable.status_code == 200
    assert member.get("/api/training-plans").status_code == 403
    assert member.get("/api/profile").status_code == 200
    assert admin.get("/api/training-plans?start_date=2026-10-01&end_date=2026-10-31").status_code == 200
    assert member.put("/api/admin/modules/run",json={
        "enabled":False,"visible":False
    },headers={"X-CSRF-Token":other["csrf"]}).status_code == 403
    assert admin.put("/api/admin/users/"+str(member_id)+"/modules/workouts",
        json={"allowed":True},headers={"X-CSRF-Token":me["csrf"]}).status_code == 200
    assert member.get("/api/training-plans?start_date=2026-10-01&end_date=2026-10-31").status_code == 200

    before=admin.get("/api/admin/brand").json()
    assert before["institutional_signature"] == "by Nexon Labs"
    assert member.get("/api/brand/public").status_code == 200
    assert member.put("/api/admin/brand",json={
        "primary_color":"#123456","secondary_color":"#789abc"
    },headers={"X-CSRF-Token":other["csrf"]}).status_code == 403
    # PNG raster de teste, com cabeçalho válido (sem scripts/SVG).
    image="data:image/png;base64,"+base64.b64encode(
        b"\x89PNG\r\n\x1a\n"+b"X"*128
    ).decode()
    update=admin.put("/api/admin/brand",json={
        "primary_color":"#aabbcc","secondary_color":"#ddee12",
        "logo_data":image,"favicon_data":image,
        "institutional_signature":"remover"
    },headers={"X-CSRF-Token":me["csrf"]})
    assert update.status_code == 200, update.text
    current=member.get("/api/brand/public").json()
    assert current["primary_color"]=="#aabbcc"
    assert current["favicon_data"]==image
    assert current["institutional_signature"]=="by Nexon Labs"
    # Retorna o estado original para não interferir nas demais execuções.
    assert admin.put("/api/admin/brand",json={
        "primary_color":before["primary_color"],
        "secondary_color":before["secondary_color"],
        "logo_data":before["logo_data"],
        "favicon_data":before["favicon_data"],
    },headers={"X-CSRF-Token":me["csrf"]}).status_code == 200
    admin.close()
    member.close()
