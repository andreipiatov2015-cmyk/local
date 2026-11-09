"""Тесты site_admin/hls_cleanup.py — независимая от nginx-rtmp очистка
старых HLS-сегментов по возрасту файла (см. модуль: штатный hls_cleanup
nginx-rtmp-module работает, только пока поток активен)."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from rtmp_server.config import constants as C
from rtmp_server.site_admin import hls_cleanup


class RetentionConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_config_file = C.HLS_CLEANUP_CONFIG_FILE
        C.HLS_CLEANUP_CONFIG_FILE = str(Path(self.tmp.name) / "hls_cleanup.json")

    def tearDown(self):
        C.HLS_CLEANUP_CONFIG_FILE = self._orig_config_file
        self.tmp.cleanup()

    def test_default_when_file_missing(self):
        self.assertEqual(hls_cleanup.get_retention_seconds(), C.DEFAULT_HLS_RETENTION_SECONDS)

    def test_set_and_get_roundtrip(self):
        hls_cleanup.set_retention_seconds(600)
        self.assertEqual(hls_cleanup.get_retention_seconds(), 600)

    def test_set_rejects_non_positive(self):
        for bad in (0, -5):
            with self.assertRaises(ValueError):
                hls_cleanup.set_retention_seconds(bad)

    def test_get_falls_back_to_default_on_corrupt_file(self):
        Path(C.HLS_CLEANUP_CONFIG_FILE).write_text("not json", encoding="utf-8")
        self.assertEqual(hls_cleanup.get_retention_seconds(), C.DEFAULT_HLS_RETENTION_SECONDS)


class CleanupOnceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hls_dir = Path(self.tmp.name) / "hls"
        self.hls_dir.mkdir()
        self._orig_hls_dir = C.HLS_DIR
        C.HLS_DIR = str(self.hls_dir)
        self.now = time.time()

    def tearDown(self):
        C.HLS_DIR = self._orig_hls_dir
        self.tmp.cleanup()

    def _write_segment(self, name: str, age_seconds: float) -> Path:
        path = self.hls_dir / name
        path.write_bytes(b"x" * 1000)
        mtime = self.now - age_seconds
        import os
        os.utime(path, (mtime, mtime))
        return path

    def test_removes_only_files_older_than_retention(self):
        fresh = self._write_segment("stream-0001.ts", age_seconds=10)
        stale = self._write_segment("stream-0000.ts", age_seconds=400)

        result = hls_cleanup.cleanup_once(retention_seconds=300, now=self.now)

        self.assertTrue(fresh.exists())
        self.assertFalse(stale.exists())
        self.assertEqual(result.removed, 1)
        self.assertEqual(result.checked, 2)
        self.assertEqual(result.bytes_freed, 1000)

    def test_live_playlist_survives_while_actively_rewritten(self):
        """Плейлист активного потока перезаписывается непрерывно — его mtime
        всегда свежий, значит под очистку он попасть не должен."""
        live_playlist = self._write_segment("stream.m3u8", age_seconds=1)

        hls_cleanup.cleanup_once(retention_seconds=300, now=self.now)

        self.assertTrue(live_playlist.exists())

    def test_stale_playlist_from_finished_stream_is_removed(self):
        """Поток давно закончился — nginx больше не трогает этот .m3u8,
        он должен уйти по возрасту, как и сегменты."""
        stale_playlist = self._write_segment("stream.m3u8", age_seconds=1000)

        hls_cleanup.cleanup_once(retention_seconds=300, now=self.now)

        self.assertFalse(stale_playlist.exists())

    def test_ignores_non_hls_files(self):
        other = self.hls_dir / "readme.txt"
        other.write_text("не трогать")
        import os
        os.utime(other, (self.now - 10_000, self.now - 10_000))

        result = hls_cleanup.cleanup_once(retention_seconds=300, now=self.now)

        self.assertTrue(other.exists())
        self.assertEqual(result.checked, 0)

    def test_empty_directory_is_a_noop(self):
        result = hls_cleanup.cleanup_once(retention_seconds=300, now=self.now)
        self.assertEqual(result, hls_cleanup.CleanupResult())

    def test_missing_directory_does_not_raise(self):
        C.HLS_DIR = str(Path(self.tmp.name) / "does-not-exist")
        result = hls_cleanup.cleanup_once(retention_seconds=300, now=self.now)
        self.assertEqual(result.checked, 0)
        self.assertEqual(result.errors, [])

    def test_uses_configured_retention_when_not_overridden(self):
        self._orig_config_file = C.HLS_CLEANUP_CONFIG_FILE
        C.HLS_CLEANUP_CONFIG_FILE = str(Path(self.tmp.name) / "hls_cleanup.json")
        try:
            Path(C.HLS_CLEANUP_CONFIG_FILE).write_text(json.dumps({"retention_seconds": 60}), encoding="utf-8")
            stale_for_default_not_for_config = self._write_segment("stream-0002.ts", age_seconds=120)

            hls_cleanup.cleanup_once(now=self.now)  # no explicit retention_seconds -> reads config

            self.assertFalse(stale_for_default_not_for_config.exists())
        finally:
            C.HLS_CLEANUP_CONFIG_FILE = self._orig_config_file


class DirectoryUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hls_dir = Path(self.tmp.name) / "hls"
        self.hls_dir.mkdir()
        self._orig_hls_dir = C.HLS_DIR
        C.HLS_DIR = str(self.hls_dir)

    def tearDown(self):
        C.HLS_DIR = self._orig_hls_dir
        self.tmp.cleanup()

    def test_sums_file_sizes(self):
        (self.hls_dir / "a.ts").write_bytes(b"x" * 500)
        (self.hls_dir / "b.ts").write_bytes(b"x" * 1500)
        self.assertEqual(hls_cleanup.hls_directory_usage_bytes(), 2000)

    def test_zero_when_directory_missing(self):
        C.HLS_DIR = str(Path(self.tmp.name) / "does-not-exist")
        self.assertEqual(hls_cleanup.hls_directory_usage_bytes(), 0)


if __name__ == "__main__":
    unittest.main()
