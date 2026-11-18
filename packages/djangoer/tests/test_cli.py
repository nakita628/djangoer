import subprocess
import sys

from returns.result import Success

from djangoer import cli
from djangoer.studio.domain import export


def test_a_png_is_written_and_the_files_after_it_too(tmp_path, monkeypatch):
    # resvg-py is an extra: any bytes stand for the picture, which are no text to count.
    monkeypatch.setattr(export, "png", lambda _document: Success(b"\x89PNG\r\n\x1a\n"))
    png, md = tmp_path / "er.png", tmp_path / "er.md"
    assert cli.main(["er", "-o", str(png), "-o", str(md)]) == 0
    assert png.read_bytes().startswith(b"\x89PNG")
    assert md.is_file()


def run(tmp_path, *args: str) -> subprocess.CompletedProcess:
    """`djangoer` in a project whose settings name a user model no app has."""
    (tmp_path / "broken_settings.py").write_text(
        'SECRET_KEY = "x"\n'
        'INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth"]\n'
        'AUTH_USER_MODEL = "accounts.User"\n'
        'DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}\n'
    )
    return subprocess.run(  # noqa: S603 - this interpreter, on the package under test
        [
            sys.executable,
            "-m",
            "djangoer",
            "er",
            "-o",
            "er.md",
            "--settings",
            "broken_settings",
            *args,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_settings_mistake_is_one_line(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 1
    assert result.stderr == (
        "djangoer: cannot load the project: AUTH_USER_MODEL refers to model 'accounts.User' "
        "that has not been installed\n"
    )


def test_the_whole_traceback_is_there_when_asked_for(tmp_path):
    result = run(tmp_path, "--traceback")
    assert result.returncode == 1
    assert result.stderr.startswith("Traceback (most recent call last):")
    assert "django.core.exceptions.ImproperlyConfigured: AUTH_USER_MODEL" in result.stderr
