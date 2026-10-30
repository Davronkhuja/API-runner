"""/run + /stream + /stop — hozirgi xatti-harakat."""
import time


def cfg(echo, **kw):
    base = {"method": "GET", "url": echo + "/echo"}
    base.update(kw)
    return base


def test_run_requires_url(client):
    assert client.post("/run", json={"rows": []}).status_code == 400
    assert client.post("/run", data="").status_code in (400, 415)


def test_no_rows_means_single_request(run_batch, echo):
    results, summary = run_batch(cfg(echo))
    assert len(results) == 1 and summary["total"] == 1 and summary["completed"] == 1
    assert results[0]["status"] == 200 and results[0]["index"] == 1


def test_rows_substitute_variables_in_url_headers_body(run_batch, echo):
    rows = [{"id": "1", "tok": "a"}, {"id": "2", "tok": "b"}]
    results, summary = run_batch(cfg(
        echo, method="POST", url=echo + "/echo?id={{id}}",
        headers=[{"name": "X-Tok", "value": "{{tok}}"}],
        body='{"id": "{{id}}"}', body_type="json", content_type="application/json", rows=rows))
    assert summary["successful"] == 2 and summary["failed"] == 0
    got = {r["index"]: r["response"] for r in results}
    assert got[1]["args"] == {"id": ["1"]} and got[1]["headers"]["X-Tok"] == "a"
    assert got[2]["json"] == {"id": "2"}


def test_row_values_override_env_vars(run_batch, echo):
    results, _ = run_batch(cfg(echo, url=echo + "/echo?v={{v}}&e={{e}}",
                               env_vars={"v": "env", "e": "E"}, rows=[{"v": "row"}]))
    assert results[0]["response"]["args"] == {"v": ["row"], "e": ["E"]}


def test_authorization_and_params_table(run_batch, echo):
    results, _ = run_batch(cfg(echo, authorization="Bearer {{t}}",
                               params=[{"name": "q", "value": "{{t}}"}], rows=[{"t": "Z"}]))
    r = results[0]["response"]
    assert r["headers"]["Authorization"] == "Bearer Z" and r["args"] == {"q": ["Z"]}


def test_4xx_counts_as_failed(run_batch, echo):
    results, summary = run_batch(cfg(echo, url=echo + "/status/404"))
    assert results[0]["error"] is True and summary["failed"] == 1 and summary["successful"] == 0


def test_connection_error_result_shape(run_batch):
    results, summary = run_batch({"method": "GET", "url": "http://127.0.0.1:1/", "timeout": 2})
    assert results[0]["status"] == "ERROR" and results[0]["error"] is True
    assert summary["failed"] == 1


def test_retry_until_success(run_batch, echo):
    results, summary = run_batch(cfg(echo, url=echo + "/flaky", retry_count=2))
    assert results[0]["status"] == 200 and results[0]["retries"] == 2
    assert summary["successful"] == 1


def test_retry_exhausted(run_batch, echo):
    results, summary = run_batch(cfg(echo, url=echo + "/flaky", retry_count=1))
    # 2 urinish ham 500 — oxirgi urinishda natija 'failed'
    assert results[0]["status"] == 500 and summary["failed"] == 1


def test_form_body_sent_as_raw_string_quirk(run_batch, echo):
    """Hozirgi nuqson: form body jadval emas, xom string sifatida ketadi."""
    results, _ = run_batch(cfg(echo, method="POST", body="a=1&b=2", body_type="form",
                               content_type="application/x-www-form-urlencoded"))
    r = results[0]["response"]
    assert r["data"] == "a=1&b=2" and r["form"] == {"a": ["1"], "b": ["2"]}


def test_multipart_fields(run_batch, echo):
    results, _ = run_batch(cfg(echo, method="POST", body_type="multipart",
                               multipart_fields=[{"name": "k", "value": "{{v}}"}], rows=[{"v": "val"}]))
    assert results[0]["response"]["form"] == {"k": ["val"]}


def test_file_param_upload(run_batch, echo, isolated):
    f = isolated / "uploads" / "a.txt"
    f.write_text("fayl-mazmuni")
    results, _ = run_batch(cfg(echo, method="POST",
                               params=[{"name": "doc", "value": f"{f}::asl.txt", "type": "file"}]))
    assert results[0]["response"]["files"]["doc"] == {"filename": "asl.txt", "content": "fayl-mazmuni"}


def test_file_param_outside_allowed_roots_is_denied(run_batch, echo, tmp_path):
    """Bosqich 1 xavfsizlik: diskdagi ixtiyoriy yo'l o'qilmaydi (workspace / .tmp_uploads bilan cheklangan)."""
    f = tmp_path / "secret.txt"
    f.write_text("maxfiy")
    results, summary = run_batch(cfg(echo, method="POST",
                                     params=[{"name": "d", "value": str(f), "type": "file"}]))
    assert results[0]["status"] == "ERROR" and "ruxsat yo'q" in results[0]["response"]
    assert "maxfiy" not in str(results) and summary["failed"] == 1


def test_file_param_symlink_escape_is_denied(run_batch, echo, isolated, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("maxfiy")
    link = isolated / "uploads" / "link.txt"
    link.symlink_to(secret)
    results, _ = run_batch(cfg(echo, method="POST", params=[{"name": "d", "value": str(link), "type": "file"}]))
    assert results[0]["status"] == "ERROR"


def test_concurrency_all_complete(run_batch, echo):
    rows = [{"i": str(i)} for i in range(12)]
    results, summary = run_batch(cfg(echo, url=echo + "/echo?i={{i}}", concurrency=4, rows=rows))
    assert sorted(r["index"] for r in results) == list(range(1, 13))
    assert summary["total"] == 12 and summary["completed"] == 12 and summary["successful"] == 12


def test_concurrency_is_capped_at_10_and_actually_parallel(run_batch, echo):
    rows = [{} for _ in range(8)]
    t0 = time.perf_counter()
    run_batch(cfg(echo, url=echo + "/slow?s=0.4", concurrency=99, rows=rows))
    assert time.perf_counter() - t0 < 8 * 0.4 * 0.7  # ketma-ket bo'lsa 3.2s


def test_sequential_delay(run_batch, echo):
    t0 = time.perf_counter()
    run_batch(cfg(echo, delay=0.3, rows=[{}, {}, {}]))
    assert time.perf_counter() - t0 >= 0.55  # 2 ta oraliq kechikish


def test_stop_sequential(run_batch, echo):
    rows = [{} for _ in range(50)]
    results, summary = run_batch(cfg(echo, url=echo + "/slow?s=0.2", rows=rows), stop_after=0.5)
    assert summary["stopped"] is True and 0 < len(results) < 50
    assert summary["completed"] == len(results)      # Bosqich 1: hisob tuzatildi


def test_stop_unknown_job_404(client):
    assert client.post("/stop/nope").status_code == 404


def test_stream_unknown_job(client):
    assert "Job topilmadi" in client.get("/stream/nope").get_data(as_text=True)


def test_summary_time_stats(run_batch, echo):
    _, s = run_batch(cfg(echo, rows=[{}, {}]))
    assert 0 <= s["min_time"] <= s["avg_time"] <= s["max_time"]


def test_upload_temp(client, isolated):
    import io, os
    r = client.post("/upload_temp", data={"file": (io.BytesIO(b"abc"), "x.csv")},
                    content_type="multipart/form-data").get_json()
    assert r["name"] == "x.csv" and r["path"].endswith(".csv") and open(r["path"], "rb").read() == b"abc"
    assert os.path.dirname(r["path"]) == str(isolated / "uploads")
    assert client.post("/upload_temp").status_code == 400


def test_stop_concurrent_completed_matches_results(run_batch, echo):
    rows = [{} for _ in range(60)]
    results, summary = run_batch(cfg(echo, url=echo + "/slow?s=0.2", concurrency=3, rows=rows), stop_after=0.5)
    assert summary["stopped"] is True
    assert summary["completed"] == len(results) < 60
    assert summary["successful"] + summary["failed"] == len(results)
