"""Yangi qat'iy `height: NNNpx` (>56px) kontent konteynerlari uchun taqiqlangan (tools/check_fixed_heights.py)."""
import importlib.util
from pathlib import Path


def test_no_new_fixed_pixel_heights_on_content_containers():
    spec = importlib.util.spec_from_file_location("chk", Path(__file__).resolve().parents[1] / "tools" / "check_fixed_heights.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.scan() == []


def test_lint_catches_a_new_fixed_height(tmp_path, monkeypatch):
    import importlib.util as iu
    spec = iu.spec_from_file_location("chk2", Path(__file__).resolve().parents[1] / "tools" / "check_fixed_heights.py")
    mod = iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "x.css").write_text(".editor{height:300px}.ok{height:32px}.fine{min-height:300px}", encoding="utf-8")
    monkeypatch.setattr(mod, "SRC", tmp_path)
    bad = mod.scan()
    assert len(bad) == 1 and "height:300px" in bad[0]
