"""Contrato visual RITMOX/Nexon Labs — etapa 1, sem acesso a dados."""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_login_institucional_e_autenticacao_intacta():
    login = _read("login.html")
    assert "RITMOX | Treinamento &amp; Performance" in login
    assert 'id="login-form"' in login
    assert '"/api/auth/login"' in login
    assert 'id="username"' in login
    assert 'id="password"' in login
    assert login.count("by Nexon Labs") == 1
    premium = _read("ritmox-login-approved.css")
    assert "--ritmox-login-card-width:860px" in premium
    assert "--ritmox-login-card-height:520px" in premium
    assert "width:min(430px,100%)" in premium
    assert "ritmox-athlete-approved.webp" in login
    assert 'id="togglePassword"' in login
    assert "ritmox-login-approved.css?v=premium-approved-02" in login
    assert '"/api/auth/login"' in login
    assert "nexon-monochrome-dark.svg" in login
    assert "ritmox-login-atmosphere.svg" in premium
    assert "height:auto" in login
    assert "font-size:16px" in login


def test_mesmo_favicon_e_nome_nas_telas():
    login, app = _read("login.html"), _read("index.html")
    for html in (login, app):
        assert "RITMOX | Treinamento &amp; Performance" in html
        assert "/static/assets/validated/ritmox-r-favicon.png?v=premium-01" in html
        assert 'rel="apple-touch-icon"' in html


def test_moldura_e_rolagem_protegidas():
    app = _read("index.html")
    css = _read("nexon-premium-frame.css")
    assert 'href="/static/nexon-premium-frame.css?v=premium-01"' in app
    assert "nexon-frame-radius: 27px" in css
    assert "nexon-frame-radius: 23px" in css
    assert "100dvh" in css
    assert ".main-content" in css
    assert "overflow-y: auto" in css
    assert ".side-nav" in css
    assert "overflow-x: hidden" in css
    assert "nexon-app-atmosphere.svg" in css
    assert (STATIC / "nexon-app-atmosphere.svg").exists()


def test_assinatura_institucional_fixa_e_unica():
    app = _read("index.html")
    login = _read("login.html")
    assert app.count("by Nexon Labs") == 1
    assert 'class="institutional-signature"' in app
    assert app.index('class="institutional-signature"') < app.index("</main>")
    assert login.count("by Nexon Labs") == 1


def test_arte_premium_e_easter_egg():
    login = _read("login.html")
    css = _read("ritmox-login-approved.css")
    art = _read("ritmox-login-atmosphere.svg")
    asset = STATIC / "assets" / "login" / "ritmox-athlete-approved.webp"
    assert asset.is_file()
    assert asset.stat().st_size > 2_000
    assert art.startswith("<svg")
    assert "Nexon easter egg" in art
    assert "Nexon Labs" in art
    assert 'class="ritmox-athlete"' in login
    assert "ritmox-athlete-approved.webp" in login
    assert "nexon-monochrome-dark.svg" in login
    assert "background:#080d24" in css
    assert "prefers-reduced-motion:reduce" in css


def test_nenhuma_credencial_fixa_no_formulario():
    login = _read("login.html")
    assert 'id="username" type="text"' in login
    assert 'id="password" type="password"' in login
    assert 'value="adminritmox"' not in login
    assert "current-password" in login
