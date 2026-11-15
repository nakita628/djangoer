import os
import sys
from argparse import Namespace
from pathlib import Path

from django.core.management.base import BaseCommand

import djangoer
from djangoer.cli import add_studio_arguments, serve


class Command(BaseCommand):
    help = "Open Djangoer Studio: browse rows, run SQL and try ORM queries in the browser."
    # Studio shows a project as it is, also one whose checks do not pass yet.
    requires_system_checks = []

    def add_arguments(self, parser):
        add_studio_arguments(parser)

    def handle(self, *args, **options):
        selected = Namespace(
            host=options["host"],
            port=options["port"],
            database=options["database"],
            no_reload=options["no_reload"],
            open=options["open"],
            verbose=options["verbose"],
        )
        if not selected.no_reload:
            self.restart_as_djangoer(selected)
        serve(selected, write=self.write_line)

    def restart_as_djangoer(self, selected):
        """Have the reloader start `djangoer studio`, not `manage.py studio`, each time.

        `manage.py` loads the project before it runs a command, and exits when that fails. A
        models.py saved half-written would end Studio there; `djangoer studio` loads the project
        itself, says why it does not load, and starts again when the file is saved. The
        reloader runs what `sys.argv` names, so that is what is changed.
        """
        argv = [
            str(Path(djangoer.__file__).parent / "__main__.py"),
            "studio",
            "--settings",
            os.environ["DJANGO_SETTINGS_MODULE"],
            "--host",
            selected.host,
            "--port",
            str(selected.port),
            "--database",
            selected.database,
        ]
        if selected.open:
            argv.append("--open")
        if selected.verbose:
            argv.append("--verbose")
        sys.argv = argv

    def write_line(self, text):
        # Flushed: the address has to show at once, also when the output is a pipe.
        self.stdout.write(text)
        self.stdout.flush()
