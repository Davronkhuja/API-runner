"""run.command: .venv, ko'rinadigan pip xatolari, Enter kutish, port siyosati, versiya. Hammasi tmp nusxada (haqiqiy .venv/ma'lumotga tegmaydi)."""
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k != "APIRUNNER_TESTING"}   # tmp nusxa o'z yo'llaridan foydalanadi
    env.update({"APIRUNNER_NO_BROWSER": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(extra)
    return env


@pytest.fixture
def proj(tmp_path):
    """Loyihaning toza nusxasi (.venv'siz)."""
    d = tmp_path / "proj"
    d.mkdir()
    for name in ("api_runner.py", "requirements.txt", "run.command"):
        shutil.copy2(os.path.join(REPO, name), d / name)
    shutil.copytree(os.path.join(REPO, "apirunner"), d / "apirunner", ignore=shutil.ignore_patterns("__pycache__"))
    return d


@pytest.fixture
def proj_with_venv(proj):
    """Haqiqiy .venv'ga symlink'lar orqali tayyor muhit (tarmoqsiz): tmp/.venv/{bin,lib} -> repo/.venv/{bin,lib}."""
    src = os.path.join(REPO, ".venv")
    if not os.path.isdir(src):
        pytest.skip(".venv yo'q")
    v = proj / ".venv"
    v.mkdir()
    for sub in ("bin", "lib"):
        os.symlink(os.path.join(src, sub), v / sub)
    shutil.copy2(os.path.join(src, "pyvenv.cfg"), v / "pyvenv.cfg")
    return proj


def run_script(proj, env, stdin=subprocess.DEVNULL, timeout=120):
    return subprocess.run(["bash", str(proj / "run.command")], cwd=str(proj), env=env, stdin=stdin,
                          capture_output=True, text=True, timeout=timeout)


def reader(p):
    """Jarayon chiqishini fon oqimida yig'adi (bloklanmaslik uchun)."""
    buf = []
    threading.Thread(target=lambda: [buf.append(ch) for ch in iter(lambda: p.stdout.read(1), "")], daemon=True).start()   # belgi-belgi: '\n'siz so'rov ham ko'rinadi
    return buf


def port_open(port):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.3).close()
        return True
    except OSError:
        return False


def wait_until(cond, timeout=40):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def test_script_is_executable_and_syntax_ok():
    p = os.path.join(REPO, "run.command")
    assert os.access(p, os.X_OK)
    assert subprocess.run(["bash", "-n", p]).returncode == 0


def test_pip_errors_are_never_hidden():
    lines = open(os.path.join(REPO, "run.command"), encoding="utf-8").read().splitlines()
    pip_lines = [l for l in lines if "pip" in l and not l.strip().startswith("#")]
    assert pip_lines and not any("/dev/null" in l or " -q" in l for l in pip_lines)


def test_creates_venv_and_shows_pip_failure_then_waits_for_enter(proj):
    env = clean_env(PIP_INDEX_URL="http://127.0.0.1:9/simple", PIP_RETRIES="0", PIP_DEFAULT_TIMEOUT="2", PIP_DISABLE_PIP_VERSION_CHECK="1")
    p = subprocess.Popen(["bash", str(proj / "run.command")], cwd=str(proj), env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    buf = reader(p)
    ok = wait_until(lambda: "Oynani yopish" in "".join(buf), 90)
    out = "".join(buf)
    assert ok and (proj / ".venv" / "bin" / "python").exists()                    # .venv yaratildi
    assert "Virtual muhit yaratilmoqda" in out
    assert "Kutubxonalarni o'rnatib bo'lmadi" in out and re.search(r"ERROR|Could not|No matching|Connection", out)   # pip'ning o'z xatosi ko'rinadi
    assert "Oynani yopish uchun Enter" in out
    assert p.poll() is None                                                       # oyna yopilmadi — Enter kutyapti
    p.stdin.write("\n")
    p.stdin.flush()
    assert p.wait(timeout=20) == 1


def test_port_taken_by_other_program_is_not_killed(proj_with_venv):
    port = free_port()
    other = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                             cwd=str(proj_with_venv), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert wait_until(lambda: port_open(port))
        r = run_script(proj_with_venv, clean_env(APIRUNNER_PORT=str(port)))
        assert r.returncode == 1
        assert "OGOHLANTIRISH" in r.stdout and f"PID {other.pid}" in r.stdout and "http.server" in r.stdout
        assert "boshqa dastur" in r.stdout and "o'ldirmadim" in r.stdout
        assert other.poll() is None and port_open(port)                           # boshqa dastur tirik qoldi
    finally:
        other.kill()
        other.wait()


def test_own_old_process_is_stopped_new_one_starts_and_prints_version(proj_with_venv):
    port = free_port()
    env = clean_env(APIRUNNER_PORT=str(port))
    old = subprocess.Popen([str(proj_with_venv / ".venv" / "bin" / "python"), "api_runner.py"], cwd=str(proj_with_venv), env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    new = None
    try:
        assert wait_until(lambda: port_open(port))
        new = subprocess.Popen(["bash", str(proj_with_venv / "run.command")], cwd=str(proj_with_venv), env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        assert wait_until(lambda: old.poll() is not None)                         # eski jarayon to'xtatildi
        assert wait_until(lambda: port_open(port))                                # yangisi ko'tarildi
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
        assert "__API_TOKEN__" in body
        os.killpg(new.pid, signal.SIGTERM)
        out = new.communicate(timeout=30)[0]
        assert "eski API Runner jarayoni" in out
        assert re.search(r"^API RUNNER v\d+\.\d+\.\d+", out, re.M)                # run.command sarlavhasi
        assert re.search(r"API RUNNER v\d+\.\d+\.\d+\s+—\s+http://127\.0\.0\.1:%d" % port, out)    # server bannerida ham
    finally:
        for pr in (old, new):
            if pr and pr.poll() is None:
                try:
                    os.killpg(pr.pid, signal.SIGKILL) if pr is new else pr.kill()
                except ProcessLookupError:
                    pass


def test_requirements_unchanged_skips_pip_so_it_works_offline(proj_with_venv):
    port = free_port()
    env = clean_env(APIRUNNER_PORT=str(port), PIP_INDEX_URL="http://127.0.0.1:9/simple", PIP_RETRIES="0", PIP_DEFAULT_TIMEOUT="2")
    sha = subprocess.run(["shasum", "requirements.txt"], cwd=str(proj_with_venv), capture_output=True, text=True).stdout.split()[0]
    (proj_with_venv / ".venv" / ".requirements.sha").write_text(sha + "\n")
    p = subprocess.Popen(["bash", str(proj_with_venv / "run.command")], cwd=str(proj_with_venv), env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        assert wait_until(lambda: port_open(port))
    finally:
        os.killpg(p.pid, signal.SIGTERM)
        out = p.communicate(timeout=30)[0]
    assert "Kutubxonalar o'rnatilmoqda" not in out and "API RUNNER v" in out
