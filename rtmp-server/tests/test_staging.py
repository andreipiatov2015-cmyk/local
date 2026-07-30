"""Юнит-тесты движка обновлений (updates/staging.py) на временных директориях
— без реального systemd/сети. Проверяют то, что нельзя было проверить в
старом приложении: что swap реально атомарен и откатывается при неудаче."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rtmp_server.updates.staging import StagedSwap, extract_tarball


class StagedSwapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.target = self.root / "target"
        self.staging = self.root / "staging"
        self.backup = self.root / "backup"

        self.target.mkdir()
        (self.target / "old.txt").write_text("old version")

        self.staging.mkdir()
        (self.staging / "new.txt").write_text("new version")

    def tearDown(self):
        self.tmp.cleanup()

    def test_successful_swap(self):
        swap = StagedSwap(target_dir=self.target, staging_dir=self.staging, backup_dir=self.backup)
        result = swap.apply()

        self.assertTrue(result.applied)
        self.assertTrue((self.target / "new.txt").exists())
        self.assertFalse((self.target / "old.txt").exists())
        self.assertFalse(self.backup.exists())  # бэкап удалён после успешного апдейта

    def test_failed_smoke_test_rolls_back(self):
        swap = StagedSwap(
            target_dir=self.target,
            staging_dir=self.staging,
            backup_dir=self.backup,
            smoke_test=lambda: False,
        )
        result = swap.apply()

        self.assertFalse(result.applied)
        self.assertTrue(result.rolled_back)
        self.assertTrue((self.target / "old.txt").exists())
        self.assertFalse((self.target / "new.txt").exists())

    def test_failed_post_swap_rolls_back(self):
        def boom():
            raise RuntimeError("рестарт сервиса упал")

        swap = StagedSwap(
            target_dir=self.target,
            staging_dir=self.staging,
            backup_dir=self.backup,
            post_swap=boom,
        )
        result = swap.apply()

        self.assertFalse(result.applied)
        self.assertTrue(result.rolled_back)
        self.assertTrue((self.target / "old.txt").exists())

    def test_no_prior_target_is_removed_on_rollback(self):
        # чистая установка: target ещё не существует
        import shutil

        shutil.rmtree(self.target)
        swap = StagedSwap(
            target_dir=self.target,
            staging_dir=self.staging,
            backup_dir=self.backup,
            smoke_test=lambda: False,
        )
        result = swap.apply()

        self.assertFalse(result.applied)
        self.assertFalse(self.target.exists())


class ExtractTarballFilterCompatTests(unittest.TestCase):
    """Тот же баг/фикс, что и в site_updater._extractall_compat: filter="data"
    (PEP 706) не поддерживается на системном python3 реального сервера."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive = self.root / "test.tar"
        payload = self.root / "payload.txt"
        payload.write_text("content")
        with tarfile.open(self.archive, "w") as tar:
            tar.add(payload, arcname="payload.txt")

    def tearDown(self):
        self.tmp.cleanup()

    def test_falls_back_when_filter_kwarg_unsupported(self):
        dest = self.root / "out"

        real_extractall = tarfile.TarFile.extractall

        def flaky_extractall(self, path=".", members=None, *, numeric_owner=False, filter=None):
            if filter is not None:
                raise TypeError("extractall() got an unexpected keyword argument 'filter'")
            return real_extractall(self, path, members, numeric_owner=numeric_owner)

        with mock.patch.object(tarfile.TarFile, "extractall", flaky_extractall):
            extract_tarball(self.archive, dest)  # не должно бросить исключение

        self.assertEqual((dest / "payload.txt").read_text(), "content")


if __name__ == "__main__":
    unittest.main()
