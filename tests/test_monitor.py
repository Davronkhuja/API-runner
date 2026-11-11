"""Monitor: cron ifoda, saqlash/tekshiruv, scheduler tick, run tarixiga (kind=monitor) yozish, xatoda bildirishnoma."""
import datetime as dt

import pytest

from apirunner import monitor
from apirunner.monitor import CronError, matches, next_run, parse_cron


def at(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M")


def test_cron_matching_lists_ranges_steps_and_names():
    assert matches(parse_cron("*/15 * * * *"), at("2026-03-02 10:30"))
    assert not matches(parse_cron("*/15 * * * *"), at("2026-03-02 10:31"))
    assert matches(parse_cron("0 9-17 * * mon-fri"), at("2026-03-02 09:00"))      # dushanba
    assert not matches(parse_cron("0 9-17 * * mon-fri"), at("2026-03-01 09:00"))  # yakshanba
    assert matches(parse_cron("0,30 8 1 jan *"), at("2027-01-01 08:30"))
    assert matches(parse_cron("0 0 * * 7"), at("2026-03-01 00:00"))                # 7 = yakshanba
    assert matches(parse_cron("5/20 * * * *"), at("2026-03-02 10:45"))


def test_cron_day_of_month_or_weekday_semantics():
    p = parse_cron("0 0 13 * fri")                  # 13-sana YOKI juma
    assert matches(p, at("2026-03-13 00:00")) and matches(p, at("2026-03-06 00:00")) and not matches(p, at("2026-03-05 00:00"))


@pytest.mark.parametrize("bad", ["", "* * * *", "60 * * * *", "* 24 * * *", "*/0 * * * *", "a * * * *", "5-1 * * * *", "* * 0 * *", "* * * 13 *"])
def test_cron_rejects_invalid(bad):
    with pytest.raises(CronError):
        parse_cron(bad)


def test_next_run():
    assert next_run("30 14 * * *", at("2026-03-02 14:30")) == at("2026-03-03 14:30")
    assert next_run("*/10 * * * *", at("2026-03-02 14:31")) == at("2026-03-02 14:40")
    assert next_run("0 0 29 2 *", at("2026-03-01 00:00"), limit_days=1500) == at("2028-02-29 00:00")


def mk(client, url, name="Col"):
    col = {"info": {"_postman_id": "mon1", "name": name, "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
           "item": [{"id": "r1", "name": "Ping", "request": {"method": "GET", "header": [], "url": {"raw": url}}}]}
    client.app.extensions["workspace"].save_collection(col)
    return "mon1"


def test_monitor_crud_and_validation(client):
    cid = mk(client, "http://127.0.0.1:1/x")
    assert client.post("/api/monitors", json={"collection_id": cid, "cron": "bad"}).status_code == 400
    assert client.post("/api/monitors", json={"cron": "* * * * *"}).status_code == 400
    r = client.post("/api/monitors", json={"name": "M1", "collection_id": cid, "cron": "*/5 * * * *"})
    assert r.status_code == 201
    m = r.get_json()
    assert m["next_at"] and m["enabled"] and m["notify"]
    assert client.put(f"/api/monitors/{m['id']}", json={"name": "M2", "collection_id": cid, "cron": "0 * * * *", "enabled": False}).get_json()["next_at"] is None
    assert [x["name"] for x in client.get("/api/monitors").get_json()["items"]] == ["M2"]
    assert client.post("/api/monitors/validate", json={"cron": "x"}).get_json()["ok"] is False
    assert client.post("/api/monitors/validate", json={"cron": "* * * * *"}).get_json()["ok"] is True
    assert client.delete(f"/api/monitors/{m['id']}").status_code == 200
    assert client.delete(f"/api/monitors/{m['id']}").status_code == 404
    assert client.get("/api/monitors").get_json()["items"] == []


def test_run_now_success_and_failure_recorded_in_history(client, echo, monkeypatch):
    sent = []
    monkeypatch.setattr(monitor, "notify", lambda t, m: sent.append((t, m)))
    cid = mk(client, echo + "/echo")
    mid = client.post("/api/monitors", json={"name": "OK", "collection_id": cid, "cron": "* * * * *"}).get_json()["id"]
    last = client.post(f"/api/monitors/{mid}/run?wait=1").get_json()
    assert last["ok"] and last["total"] == 1 and last["failures"] == 0 and not sent
    runs = client.get("/api/runs").get_json()
    rows = runs["items"] if isinstance(runs, dict) else runs
    assert any(r.get("kind") == "monitor" and r["id"] == last["run_id"] for r in rows)
    assert client.get("/api/monitors").get_json()["items"][0]["last"]["ok"] is True

    cid = mk(client, "http://127.0.0.1:1/x", "Bad")
    mid = client.post("/api/monitors", json={"name": "Bad", "collection_id": cid, "cron": "* * * * *"}).get_json()["id"]
    last = client.post(f"/api/monitors/{mid}/run?wait=1").get_json()
    assert not last["ok"] and last["failures"] == 1
    assert len(sent) == 1 and "Bad" in sent[0][0]
    mid2 = client.post("/api/monitors", json={"name": "Quiet", "collection_id": cid, "cron": "* * * * *", "notify": False}).get_json()["id"]
    client.post(f"/api/monitors/{mid2}/run?wait=1")
    assert len(sent) == 1


def test_missing_collection_is_reported_not_raised(client, monkeypatch):
    monkeypatch.setattr(monitor, "notify", lambda t, m: None)
    mid = client.post("/api/monitors", json={"name": "X", "collection_id": "nope", "cron": "* * * * *"}).get_json()["id"]
    last = client.post(f"/api/monitors/{mid}/run?wait=1").get_json()
    assert not last["ok"] and last["error"]


def test_scheduler_tick_fires_once_per_minute_and_skips_disabled(client, echo, monkeypatch):
    monkeypatch.setattr(monitor, "notify", lambda t, m: None)
    cid = mk(client, echo + "/echo")
    a = client.post("/api/monitors", json={"name": "A", "collection_id": cid, "cron": "30 10 * * *"}).get_json()["id"]
    client.post("/api/monitors", json={"name": "B", "collection_id": cid, "cron": "30 10 * * *", "enabled": False})
    client.post("/api/monitors", json={"name": "C", "collection_id": cid, "cron": "31 10 * * *"})
    sch = client.app.extensions["scheduler"]
    assert sch.tick(at("2026-03-02 10:30")) == [a]
    assert sch.tick(at("2026-03-02 10:30")) == []              # shu daqiqada qayta yurmaydi
    import time
    for _ in range(100):
        if not sch.busy:
            break
        time.sleep(0.1)
    assert client.get("/api/monitors").get_json()["items"][0]["last"]["ok"]
    assert sch.tick(at("2026-03-03 10:30")) == [a]
    for _ in range(100):
        if not sch.busy:
            break
        time.sleep(0.1)
