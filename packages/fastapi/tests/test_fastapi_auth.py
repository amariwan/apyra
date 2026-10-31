import time
from threading import get_ident

import jwt
import pytest
from apyra.auth import AuthSettings, JWTAuthenticator, TokenService
from apyra.security import generate_csrf_token
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr

from apyra.fastapi import get_current_token, require_csrf, require_roles, require_scopes

SECRET = "secret-with-enough-length-for-hs256"
CSRF_SECRET = "csrf-test-secret-with-at-least-32-bytes"


def make_token(scopes: list[str], roles: list[str]) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "user-1",
            "iat": now,
            "exp": now + 3600,
            "iss": "apyra-tests",
            "aud": "apyra-api",
            "type": "access",
            "jti": "token-1",
            "scopes": scopes,
            "roles": roles,
        },
        SECRET,
        algorithm="HS256",
    )


def test_fastapi_auth_dependencies() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    authenticator = JWTAuthenticator(settings)

    app = FastAPI()
    app.state.authenticator = authenticator

    @app.get("/scopes")
    async def scopes(
        payload: dict[str, object] = Depends(require_scopes("read", "write")),
    ) -> dict[str, object]:
        return payload

    @app.get("/roles")
    async def roles(
        payload: dict[str, object] = Depends(require_roles("admin")),
    ) -> dict[str, object]:
        return payload

    with TestClient(app) as client:
        token = make_token(["read", "write"], ["admin"])
        response = client.get("/scopes", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

        token = make_token(["read"], ["admin"])
        response = client.get("/scopes", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

        token = make_token(["read"], ["user"])
        response = client.get("/roles", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


def test_revoked_token_is_rejected() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    store = TokenService(settings).store
    authenticator = JWTAuthenticator(settings, revocation_store=store)

    app = FastAPI()
    app.state.authenticator = authenticator

    @app.get("/protected")
    async def protected(
        payload: dict[str, object] = Depends(require_scopes("read")),
    ) -> dict[str, object]:
        return payload

    token = make_token(["read"], ["user"])
    service = TokenService(settings, store=store)
    service.revoke(token)

    with TestClient(app) as client:
        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_refresh_token_cannot_authenticate_api_request() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    service = TokenService(settings)
    authenticator = JWTAuthenticator(settings, revocation_store=service.store)
    pair = service.issue_token_pair("user-1", scopes=["read"])

    app = FastAPI()
    app.state.authenticator = authenticator

    @app.get("/protected")
    async def protected(
        payload: dict[str, object] = Depends(require_scopes("read")),
    ) -> dict[str, object]:
        return payload

    with TestClient(app) as client:
        response = client.get(
            "/protected", headers={"Authorization": f"Bearer {pair.refresh_token}"}
        )

    assert response.status_code == 401


def test_untyped_token_is_rejected_when_access_type_is_configured() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
        expected_access_token_type="access",
    )
    app = FastAPI()
    app.state.auth_settings = settings
    app.state.authenticator = JWTAuthenticator(
        AuthSettings(
            mode="hs",
            hs_secret=SecretStr(SECRET),
            algorithms=["HS256"],
            issuer="apyra-tests",
            audience="apyra-api",
        )
    )

    @app.get("/protected")
    async def protected(
        payload: dict[str, object] = Depends(require_scopes("read")),
    ) -> dict[str, object]:
        return payload

    now = int(time.time())
    untyped_token = jwt.encode(
        {
            "sub": "user-1",
            "iat": now,
            "exp": now + 3600,
            "iss": "apyra-tests",
            "aud": "apyra-api",
            "scopes": ["read"],
        },
        SECRET,
        algorithm="HS256",
    )

    with TestClient(app) as client:
        response = client.get("/protected", headers={"Authorization": f"Bearer {untyped_token}"})

    assert response.status_code == 401


def test_injected_jwt_authenticator_enforces_its_access_type_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_EXPECTED_ACCESS_TOKEN_TYPE", raising=False)
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
        expected_access_token_type="access",
    )
    app = FastAPI()
    app.state.authenticator = JWTAuthenticator(settings)

    @app.get("/protected")
    async def protected(
        payload: dict[str, object] = Depends(require_scopes("read")),
    ) -> dict[str, object]:
        return payload

    now = int(time.time())
    untyped_token = jwt.encode(
        {
            "sub": "user-1",
            "iat": now,
            "exp": now + 3600,
            "iss": "apyra-tests",
            "aud": "apyra-api",
            "scopes": ["read"],
        },
        SECRET,
        algorithm="HS256",
    )

    with TestClient(app) as client:
        response = client.get("/protected", headers={"Authorization": f"Bearer {untyped_token}"})

    assert response.status_code == 401


def test_fastapi_enforces_configured_access_token_header_typ() -> None:
    from apyra.fastapi.auth import get_current_token

    decoded_header = {"typ": "JWT"}

    class Authenticator:
        def decode_token(self, _token: str) -> dict[str, object]:
            return {"header": decoded_header, "payload": {"sub": "user-1"}}

    app = FastAPI()
    app.state.auth_settings = AuthSettings(expected_access_token_header_typ="at+jwt")
    app.state.authenticator = Authenticator()

    @app.get("/protected")
    async def protected(
        payload: dict[str, object] = Depends(get_current_token),
    ) -> dict[str, object]:
        return payload

    with TestClient(app) as client:
        ordinary = client.get("/protected", headers={"Authorization": "Bearer test-token"})
        decoded_header["typ"] = "at+jwt"
        access = client.get("/protected", headers={"Authorization": "Bearer test-token"})

    assert ordinary.status_code == 401
    assert ordinary.json()["detail"] == "token_header_type_invalid"
    assert access.status_code == 200


def test_none_access_token_cookie_disables_cookie_authentication() -> None:
    app = FastAPI()
    app.state.auth_settings = AuthSettings(access_token_cookie=None)

    class Authenticator:
        def decode_token(self, _token: str) -> dict[str, object]:
            return {"header": {}, "payload": {"sub": "user-1"}}

    app.state.authenticator = Authenticator()

    @app.get("/protected")
    async def protected(
        payload: dict[str, object] = Depends(get_current_token),
    ) -> dict[str, object]:
        return payload

    with TestClient(app) as client:
        client.cookies.set("access_token", "cookie-token")
        cookie_response = client.get("/protected")
        bearer_response = client.get("/protected", headers={"Authorization": "Bearer api-token"})

    assert cookie_response.status_code == 401
    assert cookie_response.json()["detail"] == "missing_authorization"
    assert bearer_response.status_code == 200


def test_jwt_validation_runs_outside_event_loop_thread() -> None:
    from apyra.fastapi.auth import get_current_token

    decode_thread: list[int] = []

    class Authenticator:
        def decode_token(self, token: str) -> dict[str, object]:
            decode_thread.append(get_ident())
            return {"header": {}, "payload": {"sub": "user-1"}}

    app = FastAPI()
    app.state.authenticator = Authenticator()

    @app.get("/thread")
    async def thread_id(
        payload: dict[str, object] = Depends(get_current_token),
    ) -> dict[str, int]:
        return {"thread_id": get_ident()}

    with TestClient(app) as client:
        response = client.get("/thread", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert decode_thread
    assert decode_thread[0] != response.json()["thread_id"]


def test_csrf_dependency_protects_unsafe_requests_and_cookie_auth() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(SECRET),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    app = FastAPI()
    app.state.authenticator = JWTAuthenticator(settings)
    csrf_dependency = require_csrf(CSRF_SECRET, binding_cookie_name="session_id")

    @app.post("/write")
    async def write(
        _payload: dict[str, object] = Depends(get_current_token),
        _csrf: None = Depends(csrf_dependency),
    ) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/read")
    async def read(
        _payload: dict[str, object] = Depends(get_current_token),
    ) -> dict[str, bool]:
        return {"ok": True}

    login_csrf_dependency = require_csrf(CSRF_SECRET)

    @app.post("/login", dependencies=[Depends(login_csrf_dependency)])
    async def login() -> dict[str, bool]:
        return {"ok": True}

    access_token = make_token([], [])
    session_id = "session-123"
    csrf_token = generate_csrf_token(CSRF_SECRET, binding=session_id)

    with TestClient(app) as client:
        assert client.post("/login").status_code == 403
        bearer_login = client.post(
            "/login",
            headers={"Authorization": "Bearer attacker-controlled"},
        )
        assert bearer_login.status_code == 403

        login_csrf_token = generate_csrf_token(CSRF_SECRET)
        client.cookies.set("csrf_token", login_csrf_token)
        login_response = client.post(
            "/login",
            headers={"X-CSRF-Token": login_csrf_token},
        )
        assert login_response.status_code == 200
        client.cookies.delete("csrf_token")

        client.cookies.set("access_token", access_token)
        assert client.post("/write").status_code == 403

        client.cookies.set("csrf_token", csrf_token)
        assert client.post("/write", headers={"X-CSRF-Token": "incorrect"}).status_code == 403

        client.cookies.set("session_id", "other-session")
        assert client.post("/write", headers={"X-CSRF-Token": csrf_token}).status_code == 403

        client.cookies.set("session_id", session_id)
        response = client.post("/write", headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

        client.cookies.delete("csrf_token")
        assert client.get("/read").status_code == 200
        bearer = client.post("/write", headers={"Authorization": f"Bearer {access_token}"})
        assert bearer.status_code == 403

        client.cookies.set("csrf_token", csrf_token)
        protected_bearer = client.post(
            "/write",
            headers={"Authorization": f"Bearer {access_token}", "X-CSRF-Token": csrf_token},
        )
        assert protected_bearer.status_code == 200


@pytest.mark.asyncio
async def test_csrf_dependency_rejects_non_ascii_tokens() -> None:
    app = FastAPI()
    app.state.auth_settings = AuthSettings()
    dependency = require_csrf(CSRF_SECRET)
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/write",
            "raw_path": b"/write",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"cookie", b"access_token=signed-token; csrf_token=\xf8"),
                (b"x-csrf-token", b"\xf8"),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "app": app,
        }
    )

    with pytest.raises(HTTPException) as raised:
        await dependency(request)

    assert raised.value.status_code == 403
    assert raised.value.detail == "csrf_token_invalid"


def test_csrf_dependency_rejects_short_secrets_at_configuration_time() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        require_csrf("short")


def test_csrf_dependency_rejects_empty_cookie_or_header_names() -> None:
    with pytest.raises(ValueError, match="cookie and header names"):
        require_csrf(CSRF_SECRET, csrf_cookie_name="")
    with pytest.raises(ValueError, match="cookie and header names"):
        require_csrf(CSRF_SECRET, csrf_header_name="")
    with pytest.raises(ValueError, match="binding cookie name"):
        require_csrf(CSRF_SECRET, binding_cookie_name="")


def test_csrf_dependency_skips_safe_http_methods() -> None:
    app = FastAPI()
    csrf_dependency = require_csrf(CSRF_SECRET)

    @app.api_route(
        "/safe",
        methods=["GET", "HEAD", "OPTIONS", "TRACE"],
        dependencies=[Depends(csrf_dependency)],
    )
    async def safe() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        responses = [
            client.get("/safe"),
            client.head("/safe"),
            client.options("/safe"),
            client.request("TRACE", "/safe"),
        ]

    assert [response.status_code for response in responses] == [200, 200, 200, 200]
