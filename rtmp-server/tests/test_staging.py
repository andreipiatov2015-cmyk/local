"""Юнит-тесты движка обновлений (updates/staging.py) на временных директориях
— без реального systemd/сети. Проверяют то, что нельзя было проверить в
старом приложении: что swap реально атомарен и откатывается при неудаче."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rtmp_server.updates.staging import StagedSwap


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


if __name__ == "__main__":
    unittest.main()
