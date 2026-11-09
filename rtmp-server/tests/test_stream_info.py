"""Тесты site_admin/stream_info.py — только детерминированные части (файлы,
JSON), без реальной сети/ffprobe. Сетевые/ffprobe-функции проверяются через
подмену subprocess/urlopen, чтобы тест не зависел от окружения."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rtmp_server.config import constants as C
from rtmp_server.site_admin import stream_info


class HlsBasedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hls_dir = Path(self.tmp.name) / "hls"
        self.hls_dir.mkdir()
        self._orig_hls_dir = C.HLS_DIR
        C.HLS_DIR = str(self.hls_dir)

    def tearDown(self):
        C.HLS_DIR = self._orig_hls_dir
        self.tmp.cleanup()

    def test_list_live_streams_detects_m3u8_files(self):
        (self.hls_dir / "stream.m3u8").write_text("#EXTM3U\n")
        (self.hls_dir / "another.m3u8").write_text("#EXTM3U\n")
        self.assertEqual(stream_info.list_live_streams(), ["another", "stream"])

    def test_list_live_streams_empty_when_no_dir(self):
        C.HLS_DIR = str(Path(self.tmp.name) / "does-not-exist")
        self.assertEqual(stream_info.list_live_streams(), [])

    def test_measure_segment_bitrate_no_segments(self):
        result = stream_info.measure_segment_bitrate("stream")
        self.assertEqual(result.segments_measured, 0)
        self.assertIsNone(result.avg_kbps)

    def test_measure_segment_bitrate_computes_from_file_sizes(self):
        # 3-секундный фрагмент, ~375000 байт -> ровно 1000 кбит/с
        for i in range(3):
            (self.hls_dir / f"stream-{i}.ts").write_bytes(b"x" * 375_000)

        result = stream_info.measure_segment_bitrate("stream", last_n=5)

        self.assertEqual(result.segments_measured, 3)
        self.assertAlmostEqual(result.avg_kbps, 1000.0, delta=1.0)
        self.assertAlmostEqual(result.min_kbps, 1000.0, delta=1.0)
        self.assertAlmostEqual(result.max_kbps, 1000.0, delta=1.0)


class VkSettingsRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_settings = C.VK_SETTINGS_FILE
        self._orig_targets = C.STREAM_TARGETS_FILE
        C.VK_SETTINGS_FILE = str(Path(self.tmp.name) / "vk_settings.json")
        C.STREAM_TARGETS_FILE = str(Path(self.tmp.name) / "stream_targets.json")

    def tearDown(self):
        C.VK_SETTINGS_FILE = self._orig_settings
        C.STREAM_TARGETS_FILE = self._orig_targets
        self.tmp.cleanup()

    def test_get_vk_settings_defaults_when_file_missing(self):
        settings = stream_info.get_vk_settings()
        self.assertFalse(settings.enabled)
        self.assertIsNone(settings.bitrate_kbps)

    def test_save_and_reload_vk_settings_roundtrip(self):
        settings = stream_info.VkPushSettings(
            enabled=True, vk_rtmp_url="rtmp://example/input/key",
            target_ids=["abc123"], bitrate_kbps=4500, resolution_height=720,
        )
        stream_info.save_vk_settings(settings)

        reloaded = stream_info.get_vk_settings()
        self.assertEqual(reloaded.enabled, True)
        self.assertEqual(reloaded.bitrate_kbps, 4500)
        self.assertEqual(reloaded.resolution_height, 720)
        self.assertEqual(reloaded.target_ids, ["abc123"])

    def test_save_vk_settings_preserves_unknown_fields(self):
        """server.py тоже читает этот файл (title, preview_path и т.п.) —
        сохранение настроек из RTMP-server не должно их стирать."""
        Path(C.VK_SETTINGS_FILE).write_text(
            json.dumps({"title": "важное поле сайта", "show_preview": True}), encoding="utf-8"
        )
        stream_info.save_vk_settings(stream_info.VkPushSettings(enabled=True, vk_rtmp_url="rtmp://x"))

        raw = json.loads(Path(C.VK_SETTINGS_FILE).read_text(encoding="utf-8"))
        self.assertEqual(raw["title"], "важное поле сайта")
        self.assertEqual(raw["show_preview"], True)
        self.assertTrue(raw["enabled"])

    def test_clearing_bitrate_removes_key_not_writes_null(self):
        stream_info.save_vk_settings(stream_info.VkPushSettings(enabled=True, vk_rtmp_url="x", bitrate_kbps=3000))
        stream_info.save_vk_settings(stream_info.VkPushSettings(enabled=True, vk_rtmp_url="x", bitrate_kbps=None))

        raw = json.loads(Path(C.VK_SETTINGS_FILE).read_text(encoding="utf-8"))
        self.assertNotIn("bitrate_kbps", raw)

    def test_stream_targets_roundtrip(self):
        targets = [
            stream_info.VkTarget(id="a1", name="Первая площадка", url="rtmp://a", enabled=True),
            stream_info.VkTarget(id="b2", name="Вторая", url="rtmp://b", enabled=False),
        ]
        stream_info.save_stream_targets(targets)

        reloaded = stream_info.list_stream_targets()
        self.assertEqual(len(reloaded), 2)
        self.assertEqual(reloaded[0].name, "Первая площадка")
        self.assertFalse(reloaded[1].enabled)


class ProbeIncomingStreamTests(unittest.TestCase):
    def test_probe_parses_ffprobe_output(self):
        fake_ffprobe_json = json.dumps({
            "streams": [
                {"codec_type": "video", "width": 1280, "height": 720, "codec_name": "h264", "avg_frame_rate": "30/1"},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000"},
            ],
            "format": {},
        })
        fake_result = mock.Mock(returncode=0, stdout=fake_ffprobe_json, stderr="")

        with mock.patch("subprocess.run", return_value=fake_result):
            info = stream_info.probe_incoming_stream("stream")

        self.assertTrue(info.live)
        self.assertEqual(info.width, 1280)
        self.assertEqual(info.height, 720)
        self.assertEqual(info.fps, 30.0)
        self.assertEqual(info.video_codec, "h264")
        self.assertEqual(info.audio_sample_rate, 48000)

    def test_probe_handles_ffprobe_failure_gracefully(self):
        fake_result = mock.Mock(returncode=1, stdout="", stderr="Connection refused")

        with mock.patch("subprocess.run", return_value=fake_result):
            info = stream_info.probe_incoming_stream("stream")

        self.assertFalse(info.live)
        self.assertIsNotNone(info.error)


class StreamKeyTests(unittest.TestCase):
    """Ключ трансляции (RTMP_STREAM_NAME) — должен совпадать с тем, что
    www/live-server/server.py реально читает из окружения, иначе сайт не
    найдёт HLS-плейлист под новым ключом."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_config_file = C.SITE_CONFIG_ENV_FILE
        C.SITE_CONFIG_ENV_FILE = str(Path(self.tmp.name) / "site-config.env")

    def tearDown(self):
        C.SITE_CONFIG_ENV_FILE = self._orig_config_file
        self.tmp.cleanup()

    def test_default_key_when_file_missing(self):
        self.assertEqual(stream_info.get_stream_key(), C.DEFAULT_RTMP_STREAM_NAME)

    def test_set_and_get_roundtrip(self):
        stream_info.set_stream_key("myevent2026")
        self.assertEqual(stream_info.get_stream_key(), "myevent2026")

    def test_set_rejects_invalid_characters(self):
        for bad in ("has space", "slash/es", "", "a" * 65):
            with self.assertRaises(stream_info.StreamInfoError):
                stream_info.set_stream_key(bad)

    def test_set_overwrites_without_duplicating_line(self):
        stream_info.set_stream_key("first")
        stream_info.set_stream_key("second")
        text = Path(C.SITE_CONFIG_ENV_FILE).read_text(encoding="utf-8")
        self.assertEqual(text.count("RTMP_STREAM_NAME="), 1)
        self.assertEqual(stream_info.get_stream_key(), "second")

    def test_set_preserves_other_lines_in_the_file(self):
        """Файл не только наш — не должны стирать чужие строки при записи."""
        Path(C.SITE_CONFIG_ENV_FILE).write_text("SOME_OTHER_VAR=keep-me\n", encoding="utf-8")
        stream_info.set_stream_key("mykey")
        text = Path(C.SITE_CONFIG_ENV_FILE).read_text(encoding="utf-8")
        self.assertIn("SOME_OTHER_VAR=keep-me", text)
        self.assertIn("RTMP_STREAM_NAME=mykey", text)

    def test_obs_server_url_uses_configured_port_and_app(self):
        url = stream_info.obs_server_url()
        self.assertTrue(url.startswith("rtmp://"))
        self.assertTrue(url.endswith(f":{C.RTMP_PORT}/{C.RTMP_APP_NAME}"))


if __name__ == "__main__":
    unittest.main()
