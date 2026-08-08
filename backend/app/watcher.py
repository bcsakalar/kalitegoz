"""Watch-folder servisi: WATCH_DIR'e dusen ses dosyalarini otomatik isler.

Calistirma: python -m app.watcher
Dosya adi kurali: '<temsilci>_<serbest>.wav' -> ilk '_' oncesi temsilci adi sayilir.
Islenen dosya depoya TASINIR, boylece klasor kuyruk gibi davranir.
"""

import logging
import time
from pathlib import Path
from queue import Empty, Queue

from watchdog.events import FileSystemEventHandler
# PollingObserver bilinçli tercih: Windows/macOS'ta Docker bind mount'lara
# inotify olaylari dusmez; polling her ortamda calisir (2 sn aralik yeterli).
from watchdog.observers.polling import PollingObserver

from .config import settings
from .db import SessionLocal
from .models import Tenant
from .services.audio import AUDIO_EXTS
from .services.ingest import IngestError, ingest_audio

# Watch-folder hangi tenant'a alim yapsin (slug); demo kurulumu icin "demo"
WATCH_TENANT_SLUG = "demo"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("kalitegoz.watcher")

_queue: Queue[Path] = Queue()


class _Handler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            _queue.put(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            _queue.put(Path(event.dest_path))


def _wait_until_stable(path: Path, checks: int = 3, interval: float = 1.0) -> bool:
    """Dosya hala kopyalaniyor olabilir; boyut sabitlenene kadar bekle."""
    last = -1
    stable = 0
    for _ in range(120):  # en fazla ~2 dk
        if not path.exists():
            return False
        size = path.stat().st_size
        if size == last and size > 0:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
        last = size
        time.sleep(interval)
    return False


def _ingest(path: Path) -> None:
    if path.suffix.lower() not in AUDIO_EXTS:
        return
    if not _wait_until_stable(path):
        logger.warning("Dosya stabil hale gelmedi, atlaniyor: %s", path.name)
        return
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == WATCH_TENANT_SLUG).first()
        if tenant is None:
            logger.warning("Watch tenant '%s' bulunamadi, atlaniyor: %s", WATCH_TENANT_SLUG, path.name)
            return
        call = ingest_audio(db, tenant.id, path, path.name, move=True)
        logger.info("Kuyruga alindi: %s -> cagri #%s", path.name, call.id)
    except IngestError as exc:
        logger.warning("Alinamadi (%s): %s", path.name, exc)
    except Exception:
        logger.exception("Beklenmedik hata: %s", path.name)
    finally:
        db.close()


def main() -> None:
    watch_dir = settings.watch_dir
    watch_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Watch-folder izleniyor: %s", watch_dir)

    # Baslangicta klasorde bekleyen dosyalari da al
    for existing in sorted(watch_dir.iterdir()):
        if existing.is_file():
            _queue.put(existing)

    observer = PollingObserver(timeout=2)
    observer.schedule(_Handler(), str(watch_dir), recursive=False)
    observer.start()
    try:
        while True:
            try:
                path = _queue.get(timeout=5)
            except Empty:
                continue
            _ingest(path)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
