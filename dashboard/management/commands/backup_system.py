"""Create a private database/media backup and verify an isolated restore."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tarfile
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_status(data):
    temporary = settings.BASE_DIR / (".backup-status-" + uuid4().hex)
    temporary.write_text(json.dumps(data), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, settings.BASE_DIR / ".backup-status.json")
    (settings.BASE_DIR / ".activity-version").touch()


class Command(BaseCommand):
    help = "Back up SQLite and media; verify a restore without changing live data."

    def handle(self, *args, **options):
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("This backup command requires SQLite.")
        root = (settings.BASE_DIR.parent / "abi-scheduled-backups").resolve()
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        folder = root / (timezone.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8])
        folder.mkdir(mode=0o700)
        try:
            database = folder / "database.sqlite3"
            with closing(sqlite3.connect(settings.DATABASES["default"]["NAME"])) as source, closing(sqlite3.connect(database)) as target:
                source.backup(target)
            database.chmod(0o600)
            media = Path(settings.MEDIA_ROOT)
            manifest = {}
            with tarfile.open(folder / "media.tar.gz", "w:gz") as archive:
                if media.exists():
                    for path in sorted(media.rglob("*")):
                        if path.is_symlink():
                            raise CommandError("Media symlinks must be reviewed before backup.")
                        if path.is_file():
                            name = path.relative_to(media).as_posix()
                            archive.add(path, arcname=name, recursive=False)
                            manifest[name] = digest(path)
            (folder / "media.tar.gz").chmod(0o600)
            (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (folder / "manifest.json").chmod(0o600)
            with TemporaryDirectory(prefix="abi-restore-") as temporary:
                restored = Path(temporary)
                shutil.copy2(database, restored / "database.sqlite3")
                with closing(sqlite3.connect(restored / "database.sqlite3")) as check:
                    if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise CommandError("Database restore integrity check failed.")
                    if check.execute("PRAGMA foreign_key_check").fetchone():
                        raise CommandError("Database restore foreign-key check failed.")
                with tarfile.open(folder / "media.tar.gz") as archive:
                    archive.extractall(restored / "media", filter="data")
                for name, expected in manifest.items():
                    if digest(restored / "media" / name) != expected:
                        raise CommandError("Media restore checksum verification failed.")
            status = {"verified_at": timezone.now().isoformat(), "last_attempt_ok": True,
                      "database_check": "Integrity and foreign keys passed", "media_files": len(manifest)}
            (folder / "verified.json").write_text(json.dumps(status), encoding="utf-8")
            write_status(status)
            # Only prune verified backup directories directly within the fixed backup root.
            previous = sorted([item for item in root.iterdir() if item.is_dir() and not item.is_symlink() and (item / "verified.json").exists()], key=lambda item: item.name)
            for item in previous[:-14]:
                if item.resolve().parent != root:
                    raise CommandError("Backup retention path validation failed.")
                shutil.rmtree(item)
            self.stdout.write(self.style.SUCCESS("Database and media backup restored and verified."))
        except Exception as error:
            try:
                old = json.loads((settings.BASE_DIR / ".backup-status.json").read_text())
            except (OSError, ValueError):
                old = {}
            old.update(last_attempt_ok=False, attempted_at=timezone.now().isoformat())
            write_status(old)
            raise CommandError("Backup or isolated restore verification failed; inspect the private server logs.") from error
