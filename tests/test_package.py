import importlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_imports_as_anki_package(tmp_path):
    """Inside Anki the add-on is the package `card_redesign`; modules must import relatively."""
    shutil.copytree(ROOT / "card_redesign", tmp_path / "card_redesign", ignore=shutil.ignore_patterns("__pycache__"))
    code = ("import sys; sys.path.insert(0, %r); import card_redesign.runner as r; "
            "assert set(r.LANGS) == {'cn', 'jp', 'vn'}; print('ok')" % str(tmp_path))
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert out.stdout.strip() == "ok", out.stderr


def test_package_contents(tmp_path):
    out = tmp_path / "a.ankiaddon"
    subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "package.py"), str(out)], check=True)
    names = set(zipfile.ZipFile(out).namelist())
    for n in ("__init__.py", "manifest.json", "ui.py", "runner.py", "cn.py", "cn_templates.py", "html_tree.py", "zh_lex.py", "common.py", "jp.py", "vn.py", "jp_templates.py", "vn_templates.py",
              "templates/base.css", "templates/cn.css", "templates/cn_back.html", "templates/cn_front_3.html", "templates/jp_back.html", "templates/vn_back.html", "templates/jp.css", "templates/vn.css", "updater.py", "fieldnames.py", "fonts.py", "hints.py"):
        assert n in names, n
    assert not any("__pycache__" in n or n.startswith("user_files") for n in names)
