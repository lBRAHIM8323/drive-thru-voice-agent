from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")

    import server.settings as settings_mod

    settings_mod.get_settings.cache_clear()
    import server.app as app_mod
    import server.db as db_mod

    importlib.reload(db_mod)
    importlib.reload(app_mod)

    with TestClient(app_mod.app) as c:
        yield c


@pytest.fixture()
def token(client) -> str:
    resp = client.post("/agent/auth/login", json={"username": "admin", "password": "secret"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth(client, token) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_default_branch_seeded(client, auth):
    branches = client.get("/agent/branches", headers=auth).json()
    assert any(b["slug"] == "main" for b in branches)


def test_menu_crud_with_sizes(client, auth):
    create = client.post(
        "/agent/menu",
        headers=auth,
        json={
            "name": "Coca-Cola",
            "category": "drink",
            "currency": "USD",
            "sizes": [
                {"size": "S", "price": 1.49, "calories": 200},
                {"size": "L", "price": 1.89, "calories": 380},
            ],
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["id"] == "coca_cola"
    assert len(body["sizes"]) == 2

    patched = client.patch("/agent/menu/coca_cola", headers=auth, json={"available": False})
    assert patched.json()["available"] is False
    assert len(patched.json()["sizes"]) == 2

    assert client.delete("/agent/menu/coca_cola", headers=auth).status_code == 204
    assert client.get("/agent/menu/coca_cola", headers=auth).status_code == 404


def test_menu_dietary_favourite_and_offer(client, auth):
    # Item with dietary info, serving size, favourite flag and a live offer.
    family = client.post(
        "/agent/menu",
        headers=auth,
        json={
            "name": "Family Veggie Platter",
            "category": "platter",
            "price": 24.99,
            "dietary": "veg",
            "tags": ["lactose_free", "gluten_free"],
            "serves": 4,
            "is_favorite": True,
            "offer_price": 19.99,
            "offer_until": "2999-01-01T00:00:00+00:00",
        },
    )
    assert family.status_code == 201, family.text
    body = family.json()
    assert body["dietary"] == "veg"
    assert body["tags"] == ["lactose_free", "gluten_free"]
    assert body["serves"] == 4
    assert body["is_favorite"] is True
    assert body["offer_price"] == 19.99

    # A second, non-favourite item with an expired offer.
    client.post(
        "/agent/menu",
        headers=auth,
        json={
            "name": "Plain Burger",
            "category": "regular",
            "price": 5.0,
            "dietary": "non_veg",
            "offer_price": 3.0,
            "offer_until": "2000-01-01T00:00:00+00:00",
        },
    )

    favourites = client.get("/agent/menu", headers=auth, params={"favorite": True}).json()
    assert [i["id"] for i in favourites] == ["family_veggie_platter"]

    on_offer = client.get("/agent/menu", headers=auth, params={"on_offer": True}).json()
    # Only the live offer qualifies; the expired one is excluded.
    assert [i["id"] for i in on_offer] == ["family_veggie_platter"]


def test_handoff_notes_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("AGENT_API_KEY", "agent-secret")

    import server.settings as settings_mod

    settings_mod.get_settings.cache_clear()
    import server.app as app_mod
    import server.db as db_mod

    importlib.reload(db_mod)
    importlib.reload(app_mod)

    from server.models import Session as SessionModel

    with TestClient(app_mod.app) as c:
        # Seed an active session with a known room name.
        with db_mod.Session(db_mod.engine) as s:
            row = SessionModel(room_name="room-xyz", status="active")
            s.add(row)
            s.commit()
            session_id = str(row.id)

        agent_auth = {"Authorization": "Bearer agent-secret"}
        r = c.post(
            "/agent/sessions/by-room/room-xyz/handoff-notes",
            headers=agent_auth,
            json={"reason": "refund request", "notes": [{"text": "sorted it out", "at": "now"}]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["episodes"] == 1

        # A second episode appends rather than overwriting.
        r2 = c.post(
            "/agent/sessions/by-room/room-xyz/handoff-notes",
            headers=agent_auth,
            json={"reason": "complaint", "notes": []},
        )
        assert r2.json()["episodes"] == 2

        # Wrong/missing agent key is rejected.
        assert (
            c.post("/agent/sessions/by-room/room-xyz/handoff-notes", json={}).status_code == 401
        )

        # Admin can read the episodes back off the session transcript.
        token = c.post(
            "/agent/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        got = c.get(
            f"/agent/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        episodes = got["transcript"]["handoff_episodes"]
        assert len(episodes) == 2
        assert episodes[0]["reason"] == "refund request"
        assert episodes[0]["notes"][0]["text"] == "sorted it out"


def test_csv_parse_review_confirm(client, auth):
    csv = (
        "id,name,category,size,calories,price\n"
        "coca_cola,Coca-Cola,drink,S,200,1.49\n"
        "coca_cola,Coca-Cola,drink,M,270,1.69\n"
        "fries,Fries,regular,,350,3.99\n"
    )
    resp = client.post(
        "/agent/documents", headers=auth, files={"file": ("menu.csv", csv, "text/csv")}
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] == "parsed"
    assert doc["parser_provider"] == "csv"
    items = {i["id"]: i for i in doc["items"]}
    assert len(items["coca_cola"]["sizes"]) == 2
    assert items["fries"]["price"] == 3.99

    doc_id = doc["id"]
    edit = client.patch(f"/agent/documents/{doc_id}", headers=auth, json={"items": doc["items"]})
    assert edit.status_code == 200

    committed = client.post(f"/agent/documents/{doc_id}/confirm?mode=replace", headers=auth)
    assert committed.status_code == 200
    assert set(committed.json()) == {"coca_cola", "fries"}

    menu = {i["id"]: i for i in client.get("/agent/menu", headers=auth).json()}
    assert {s["size"] for s in menu["coca_cola"]["sizes"]} == {"S", "M"}

    assert client.patch(f"/agent/documents/{doc_id}", headers=auth, json={"items": []}).status_code == 409


def test_agent_config_contract(client, auth):
    created = client.post(
        "/agent/agent-configs",
        headers=auth,
        json={
            "name": "default",
            "config": {"llm": {"provider": "anthropic", "model": "claude-haiku-4-5"}},
        },
    )
    assert created.status_code == 201, created.text
    config_id = created.json()["id"]

    cfg = client.get(f"/agent/agent-configs/{config_id}", headers=auth)
    assert cfg.status_code == 200
    body = cfg.json()
    assert set(body) == {
        "instructions", "greeting", "stt", "llm", "tts",
        "vad", "turn_detection", "session", "background_audio", "ui",
    }
    assert body["llm"]["provider"] == "anthropic"
    assert body["stt"]["provider"] == "deepgram"


def test_agent_config_ui_persists(client, auth):
    created = client.post(
        "/agent/agent-configs",
        headers=auth,
        json={"name": "themed", "config": {"ui": {"visualizer": "radial", "title": "Welcome!"}}},
    )
    assert created.status_code == 201, created.text
    cfg = client.get(f"/agent/agent-configs/{created.json()['id']}", headers=auth).json()
    assert cfg["ui"]["visualizer"] == "radial"
    assert cfg["ui"]["title"] == "Welcome!"


def test_connection_requires_livekit(client, monkeypatch):
    for var in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        monkeypatch.delenv(var, raising=False)
    resp = client.post("/agent/connection", json={})
    assert resp.status_code == 503


def test_parser_config_get_update(client, auth):
    assert client.get("/agent/parser-config", headers=auth).json()["provider"] == "anthropic"
    updated = client.put(
        "/agent/parser-config",
        headers=auth,
        json={"provider": "openai", "model": "gpt-4.1-mini"},
    )
    assert updated.json() == {
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "temperature": None,
        "system_prompt": None,
    }


def test_login_invalid(client):
    resp = client.post("/agent/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_users_crud(client, auth):
    create = client.post(
        "/agent/users",
        headers=auth,
        json={"username": "manager1", "password": "pw", "role": "manager"},
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]
    assert create.json()["role"] == "manager"

    listed = client.get("/agent/users", headers=auth)
    assert listed.status_code == 200
    assert any(u["id"] == user_id for u in listed.json())

    updated = client.patch(
        f"/agent/users/{user_id}", headers=auth, json={"is_active": False}
    )
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/agent/users/{user_id}", headers=auth)
    assert deleted.status_code == 204


def test_unauthorized_without_token(client):
    assert client.get("/agent/branches").status_code == 401
    assert client.post("/agent/menu", json={}).status_code == 401
    assert client.put("/agent/parser-config", json={}).status_code == 401
