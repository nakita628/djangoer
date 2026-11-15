"""`djangoer studio`: Studio for the Django project in the current directory."""

from __future__ import annotations

import argparse
import ast
import os
import sys
import webbrowser
from pathlib import Path

from . import __version__

DEFAULT_PORT = 5555


def settings_from_manage_py(directory: Path) -> str | None:
    """The settings module `manage.py` sets as the default, read without running it."""
    manage = directory / "manage.py"
    try:
        tree = ast.parse(manage.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) != 2:
            continue
        name, value = node.args
        if (
            isinstance(name, ast.Constant)
            and name.value == "DJANGO_SETTINGS_MODULE"
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            return value.value
    return None


def add_studio_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--host", default="127.0.0.1", help="address to listen on (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--database", default="default", help="alias in DATABASES to open (default: default)"
    )
    parser.add_argument(
        "--no-reload", action="store_true", help="do not restart when the project's code changes"
    )
    parser.add_argument("--open", action="store_true", help="open Studio in the browser")
    parser.add_argument("--verbose", action="store_true", help="log every request")


def _print(text: str) -> None:
    # Flushed: the address has to show at once, also when the output is a pipe.
    print(text, flush=True)


def serve(options: argparse.Namespace, *, write=_print) -> None:
    """Serve Studio until interrupted. Django's settings must be configured."""
    import django
    from django.apps import apps
    from django.conf import settings
    from django.utils import autoreload

    def run() -> None:
        # A project that does not load (a syntax error in models.py, saved half-written) is not
        # the end of Studio: it says why, and starts again when the file changes. `check_errors`
        # is what tells Django's reloader to keep watching the file that failed.
        failure: BaseException | None = None
        try:
            autoreload.check_errors(django.setup)()
        except Exception as error:
            if options.no_reload:
                raise
            failure = error
            # Django's reloader starts watching files once the apps are ready, or once this
            # thread ends. Neither will happen: the apps did not load, and this thread goes on
            # to serve. Saying "ready" is what lets it watch for the fix.
            apps.ready_event.set()
        from .studio.server import create_server

        if failure is None and options.database not in settings.DATABASES:
            raise SystemExit(
                f'djangoer: no database "{options.database}" in DATABASES '
                f"(there is: {', '.join(settings.DATABASES) or 'none'})"
            )
        try:
            server = create_server(
                options.host,
                options.port,
                database=options.database,
                root=Path.cwd(),
                quiet=not options.verbose,
                failure=failure,
            )
        except OSError as error:
            raise SystemExit(
                f"djangoer: cannot listen on {options.host}:{options.port}: {error}"
            ) from error
        host = f"[{options.host}]" if ":" in options.host else options.host
        url = f"http://{host}:{server.server_address[1]}"
        write(f"Djangoer Studio {__version__} · Django {django.get_version()}")
        write(f"  {url}")
        if failure is not None:
            write(f"  The project does not load: {type(failure).__name__}: {failure}")
            write("  Studio shows why, and starts again when the file is saved.")
        if options.host not in ("127.0.0.1", "localhost", "::1"):
            write(
                "  Listening beyond localhost: anyone who can reach this port can read and change the database."
            )
        if options.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        finally:
            server.server_close()

    try:
        if options.no_reload:
            run()
        else:
            autoreload.run_with_reloader(run)
    except KeyboardInterrupt:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="djangoer", description="A Studio for your Django models and their data."
    )
    parser.add_argument("--version", action="version", version=f"djangoer {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")
    studio = commands.add_parser("studio", help="open Studio for the project in this directory")
    studio.add_argument(
        "--settings",
        help="settings module (default: $DJANGO_SETTINGS_MODULE, else what manage.py sets)",
    )
    studio.add_argument(
        "--pythonpath", help="directory to import the project from (default: the current directory)"
    )
    add_studio_arguments(studio)
    options = parser.parse_args(argv)
    if options.command != "studio":
        parser.print_help()
        return 0 if options.command is None else 2

    root = Path(options.pythonpath or Path.cwd()).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    settings_module = (
        options.settings
        or os.environ.get("DJANGO_SETTINGS_MODULE")
        or settings_from_manage_py(Path.cwd())
    )
    if not settings_module:
        print(
            "djangoer: no settings module. Run this beside manage.py, set DJANGO_SETTINGS_MODULE, "
            "or pass --settings myproject.settings.",
            file=sys.stderr,
        )
        return 2
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    try:
        serve(options)
    except ImportError as error:
        print(f"djangoer: cannot import the project: {error}", file=sys.stderr)
        return 1
    return 0
