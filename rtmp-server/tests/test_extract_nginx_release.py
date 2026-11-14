"""Поведенческий тест debian/local/lib/extract_nginx_release.sh.

Регрессия, которая реально уронила сайт при обновлении до 1.0.25: tar -xzf
при установке нового бинарника nginx затирал уже руками правленный
conf/nginx.conf (с 8082/1936/kem-sirius.ru/формой регистрации) дефолтным
файлом из чистой сборки, если nginx на момент установки оказывался не
запущен. Проверяем именно этот скрипт, с настоящим tar, без systemd/apt."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "debian" / "local" / "lib" / "extract_nginx_release.sh"


def _make_release_tarball(path: Path, nginx_conf_body: str) -> None:
    build_dir = path.parent / "release-contents"
    (build_dir / "conf").mkdir(parents=True)
    (build_dir / "sbin").mkdir()
    (build_dir / "conf" / "nginx.conf").write_text(nginx_conf_body)
    (build_dir / "sbin" / "nginx").write_text("#!/bin/sh\necho fake nginx binary\n")
    with tarfile.open(path, "w:gz") as tar:
        for item in build_dir.rglob("*"):
            tar.add(item, arcname=item.relative_to(build_dir))


import subprocess


class ExtractNginxReleaseTests(unittest.TestCase):
    def test_preserves_existing_handedited_conf(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dest = tmp_path / "usr-local-nginx"
            (dest / "conf").mkdir(parents=True)
            handedited = "# боевой конфиг: 8082, 1936, kem-sirius.ru\n"
            (dest / "conf" / "nginx.conf").write_text(handedited)

            asset = tmp_path / "nginx-rtmp-1.0.25.tar.gz"
            _make_release_tarball(asset, "# дефолтный конфиг из чистой сборки\n")

            subprocess.run(["sh", str(SCRIPT), str(asset), str(dest)], check=True)

            self.assertEqual((dest / "conf" / "nginx.conf").read_text(), handedited)
            # Новый бинарник при этом всё равно должен распаковаться.
            self.assertTrue((dest / "sbin" / "nginx").exists())

    def test_installs_default_conf_on_first_install(self):
        """Если nginx.conf ещё никогда не было (самая первая установка на
        новой машине) — брать дефолтный конфиг из сборки, не ломать установку
        попыткой восстановить несуществующий бэкап."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dest = tmp_path / "usr-local-nginx"

            asset = tmp_path / "nginx-rtmp-1.0.25.tar.gz"
            default_conf = "# дефолтный конфиг из чистой сборки\n"
            _make_release_tarball(asset, default_conf)

            subprocess.run(["sh", str(SCRIPT), str(asset), str(dest)], check=True)

            self.assertEqual((dest / "conf" / "nginx.conf").read_text(), default_conf)


if __name__ == "__main__":
    unittest.main()
