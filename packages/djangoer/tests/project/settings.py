import os

SECRET_KEY = "tests"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "project.shop",
    "project.venue",
    "project.annex",
    "project.modern",
    "project.legacy",
    "djangoer",
]
# A file, not :memory:, which is one database per connection: the server reads from worker threads.
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ["DJANGOER_TEST_DB"]}
}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
