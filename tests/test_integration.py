import hashlib
import json
import struct
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sd_model_hub.core.events.models import LibraryChangedEvent
from starlette import _utils

from sd_webui_model_hub.host import create_factory, mount_hub


@pytest.fixture
def dist(tmp_path, monkeypatch):
    from sd_model_hub.api import app, static

    directory = tmp_path / "dist"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text('<script src="./assets/app.js"></script>')
    (directory / "assets" / "app.js").write_text("window.modelHubLoaded = true;")
    monkeypatch.setattr(app, "web_dist_dir", lambda: directory)
    monkeypatch.setattr(static, "web_dist_dir", lambda: directory)
    return directory


def test_mount_after_startup_prefix_auth_roots_socket_and_shutdown(host, dist):
    shared, paths = host
    parent = FastAPI()
    parent.auth = {"user": "password"}
    parent.tokens = {"valid": "user"}
    parent.cookie_id = "forge"
    # Emulate a reverse proxy / --subpath, with old/new Starlette scope semantics.
    base = "/webui/sd-model-hub" if hasattr(_utils, "get_route_path") else "/sd-model-hub"
    with TestClient(parent, base_url="http://localhost", root_path="/webui") as client:
        runtime = mount_hub(SimpleNamespace(server_port=7860), parent, shared, paths)
        assert mount_hub(None, parent, shared, paths) is runtime
        assert runtime.task is None
        assert client.get(f"{base}/_host/status").status_code == 401
        assert runtime.task is None  # Unauthenticated users cannot start workers.
        client.cookies.set("access-token-forge", "valid")
        status = client.get(f"{base}/_host/status")
        assert status.status_code == 200, status.text
        assert status.json()["ui_available"]
        assert client.get(f"{base}/").text == '<script src="./assets/app.js"></script>'
        assert client.get(f"{base}/assets/app.js").status_code == 200
        assert client.get(f"{base}/api/v1/app/meta").json()["roots_locked"]
        assert client.get(f"{base}/api/v1/app/health").json()["auth_required"] is False
        assert client.post(f"{base}/api/v1/library/roots", json={"path": paths.data_path}).status_code == 409
        destination = client.get(f"{base}/api/v1/library/destination", params={"kind": "lora"}).json()
        settings = client.get(f"{base}/api/v1/settings").json()
        roots = settings["paths"]["model_roots"]
        assert next(r["path"] for r in roots if r["id"] == destination["root_id"]) == shared.cmd_opts.lora_dir
        assert destination["rel_dir"] == ""
        assert client.patch(f"{base}/api/v1/settings", json={}, headers={"Origin": "http://evil.example"}).status_code == 403
        assert client.get(f"{base}/_host/status", headers={"Host": "evil.example"}).status_code == 400
        callback = client.get(f"{base}/api/v1/auth/civitai/callback?error=access_denied", follow_redirects=False)
        assert callback.headers["location"] == "/webui/sd-model-hub/#/settings?civitai=error"
        assert "Path=/webui/sd-model-hub/api/v1/auth/civitai" in callback.headers["set-cookie"]

        services = runtime.services.services
        workers = list(services.downloads._threads)
        assert workers and all(worker.is_alive() for worker in workers)
        polling = client.get(f"{base}/ws/socket.io/?EIO=4&transport=polling")
        assert polling.status_code == 200 and polling.text.startswith('0{"sid":')
        with client.websocket_connect(f"ws://localhost{base}/ws/socket.io/?EIO=4&transport=websocket", headers={"Upgrade": "websocket"}) as socket:
            assert socket.receive_text().startswith('0{"sid":')
            socket.send_text("40")
            assert socket.receive_text().startswith("40")
            services.events.publish(LibraryChangedEvent(root_id=destination["root_id"], rel_path="example.safetensors"))
            assert socket.receive_text().startswith('42["library_changed",')
        assert client.get(f"{base}/_host/status").json()["revision"] >= 1
        shared.state.job_count = 1
        assert client.get(f"{base}/_host/status").json()["busy"]
    assert runtime.closed and runtime.task.done()
    assert all(not worker.is_alive() for worker in workers)


def test_real_download_to_custom_root_updates_host_revision(host, dist, monkeypatch):
    from sd_model_hub.core import context

    shared, paths = host
    # A tiny, valid safetensors header is sufficient; no actual model or internet needed.
    header = json.dumps({"__metadata__": {"modelspec.title": "Extension integration test"}}).encode()
    payload = struct.pack("<Q", len(header)) + header
    original = context.build_services

    def build(**kwargs):
        return original(**kwargs, environ={}, transport=httpx.MockTransport(lambda request: httpx.Response(200, content=payload)))

    monkeypatch.setattr(context, "build_services", build)
    parent = FastAPI()
    runtime = mount_hub(object(), parent, shared, paths)
    with TestClient(parent, base_url="http://localhost") as client:
        base = "/sd-model-hub"
        destination = client.get(f"{base}/api/v1/library/destination?kind=lora").json()
        created = client.post(
            f"{base}/api/v1/downloads",
            json={"url": "https://models.example/test.safetensors", **destination, "expected_sha256": hashlib.sha256(payload).hexdigest()},
        )
        assert created.status_code == 201, created.text
        job_id = created.json()["id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            job = client.get(f"{base}/api/v1/downloads/{job_id}").json()
            if job["state"] in {"completed", "failed"}:
                break
            time.sleep(0.02)
        assert job["state"] == "completed", job
        assert Path(job["final_path"]).parent == Path(shared.cmd_opts.lora_dir)
        assert Path(job["final_path"]).read_bytes() == payload
        assert client.get(f"{base}/_host/status").json()["revision"] > 0
    assert runtime.closed


def test_proxy_public_url_and_forge_destination(host, dist):
    shared, paths = host
    shared.opts.data["model_hub_public_url"] = "https://models.example/webui/sd-model-hub"
    factory = create_factory(shared, paths, None, {"modules_forge.main_entry": object()})
    resources, app = factory()
    try:
        with TestClient(app, base_url="https://models.example") as client:
            assert client.get("/_host/status").json()["host"] == "Forge"
            assert client.get("/api/v1/library/destination?kind=diffusion_model").json() == client.get("/api/v1/library/destination?kind=checkpoint").json()
            response = client.get("/api/v1/auth/civitai/callback?error=access_denied", follow_redirects=False)
            assert response.headers["location"] == "/webui/sd-model-hub/#/settings?civitai=error"
    finally:
        resources.close()


def test_complete_model_directory_browses_unregistered_folders(host, dist):
    shared, paths = host
    models = Path(paths.models_path)
    (models / "custom-kind" / "nested").mkdir(parents=True)
    factory = create_factory(shared, paths, None, {})
    resources, app = factory()
    try:
        with TestClient(app, base_url="http://localhost") as client:
            roots = client.get("/api/v1/library/roots").json()
            complete = next(r for r in roots if r["path"] == str(models))
            assert complete["kind"] is None
            url = f"/api/v1/library/roots/{complete['id']}/entries"
            listing = client.get(url, params={"kind": "lora"}).json()
            assert [folder["path"] for folder in listing["folders"]] == ["custom-kind"]
            nested = client.get(url, params={"path": "custom-kind", "kind": "lora"}).json()
            assert nested["folders"][0]["path"] == "custom-kind/nested"
            assert client.get(url, params={"path": ".."}).status_code == 400
            destination = client.get("/api/v1/library/destination", params={"kind": "lora"}).json()
            assert next(r["path"] for r in roots if r["id"] == destination["root_id"]) == shared.cmd_opts.lora_dir
            assert destination["rel_dir"] == ""
    finally:
        resources.close()
