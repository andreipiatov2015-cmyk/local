"""Тест жёсткого общего дедлайна в updates/staging.download_file().

Регрессия: самообновление в GUI зависало без вообще какой-либо обратной
связи — urllib.request.urlopen(timeout=...) ограничивает только отдельные
операции на сокете, а не суммарное время передачи. Здесь имитируем сервер,
отдающий данные "по капле" (каждое чтение укладывается в лимит), и
проверяем, что download_file всё равно обрывается по общему дедлайну,
а не виснет бесконечно."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from rtmp_server.updates.staging import DownloadTimeoutError, download_file


class _DrippingResponse:
    """Поддельный HTTP-ответ: каждое чтение мгновенное и успешное (сокет
    как бы не виснет), но суммарно чтений бесконечно много — имитирует
    сервер, который никогда не отдаёт EOF достаточно быстро."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self, n):
        return b"x"  # всегда есть ещё один байт — общая передача не кончается


class DownloadDeadlineTests(unittest.TestCase):
    def test_download_aborts_on_overall_deadline_not_just_per_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.bin"
            with mock.patch("urllib.request.urlopen", return_value=_DrippingResponse()):
                start = time.monotonic()
                with self.assertRaises(DownloadTimeoutError):
                    download_file("http://example.invalid/file", dest, timeout=0.2)
                elapsed = time.monotonic() - start

        # Должно оборваться быстро (в разумных пределах над таймаутом),
        # а не зависнуть навсегда.
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
