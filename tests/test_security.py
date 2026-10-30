import pytest

from tests.conftest import TOKEN


@pytest.mark.parametrize("host", ["evil.com", "evil.com:5050", "127.0.0.1.evil.com", "192.168.0.5:5050", "localhost.evil.com"])
def test_foreign_host_rejected_even_with_token(client, host):
    r = client.get("/saved", headers={"Host": host})
    assert r.status_code == 403


@pytest.mark.parametrize("host", ["127.0.0.1:5050", "localhost:5050", "localhost", "[::1]:5050"])
def test_local_hosts_accepted(client, host):
    assert client.get("/saved", headers={"Host": host}).status_code == 200


def test_foreign_host_cannot_load_index(client):
    assert client.get("/", headers={"Host": "evil.com"}).status_code == 403


def test_missing_token_is_401(make_client):
    c = make_client()
    del c.environ_base["HTTP_X_SESSION_TOKEN"]
    for method, path in [("get", "/saved"), ("post", "/run"), ("post", "/run_one"),
                         ("get", "/stream/x"), ("post", "/stop/x"), ("get", "/api/workspace"),
                         ("post", "/upload_temp"), ("post", "/saved/folder")]:
        assert getattr(c, method)(path).status_code == 401, path


def test_wrong_token_is_401(client):
    assert client.get("/saved", headers={"X-Session-Token": "nope"}).status_code == 401


def test_token_via_query_for_eventsource(make_client):
    c = make_client()
    del c.environ_base["HTTP_X_SESSION_TOKEN"]
    assert c.get("/stream/x?token=" + TOKEN).status_code == 200


def test_foreign_origin_rejected(client):
    assert client.get("/saved", headers={"Origin": "https://evil.com"}).status_code == 403
    assert client.get("/saved", headers={"Origin": "http://localhost:5050"}).status_code == 200


def test_index_is_public_and_injects_token(make_client):
    c = make_client()
    del c.environ_base["HTTP_X_SESSION_TOKEN"]
    r = c.get("/")
    assert r.status_code == 200 and TOKEN in r.get_data(as_text=True)
    assert r.headers["Cache-Control"] == "no-store"


def test_tokens_are_random_per_app(isolated):
    from apirunner.app import create_app
    a = create_app(workspace_dir=str(isolated / "w1"), saved_file="", upload_dir=str(isolated / "u"))
    b = create_app(workspace_dir=str(isolated / "w2"), saved_file="", upload_dir=str(isolated / "u"))
    assert a.config["SESSION_TOKEN"] != b.config["SESSION_TOKEN"] and len(a.config["SESSION_TOKEN"]) >= 32


def test_workspace_ids_cannot_traverse(client):
    assert client.get("/api/collections/..%2f..%2fetc").status_code == 404
    assert client.get("/api/environments/..").status_code == 404
