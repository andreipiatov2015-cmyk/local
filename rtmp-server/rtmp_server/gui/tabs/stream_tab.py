"""Вкладка "Трансляция" — параметры входящего RTMP-потока и настройка
исходящего пуша в VK/OK.

Честное ограничение (см. также site_admin/stream_info.py): разрешение и
битрейт ВХОДЯЩЕГО потока сервер не может менять — это настройки
кодировщика у стримера (OBS), сервер только показывает, что реально
приходит. Управлять реально можно только перекодированием при пуше в
VK — там сервер сам гоняет ffmpeg и может задать целевой битрейт/масштаб."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rtmp_server.gui.root_confirm import confirm_root_password
from rtmp_server.gui.workers import WorkerThread
from rtmp_server.services.definitions import get_service
from rtmp_server.site_admin import stream_info

TARGET_COLUMNS = ["Название", "URL", "Включена"]
RESOLUTION_OPTIONS = [
    ("Без изменений (как на входе)", None),
    ("1080p", 1080),
    ("720p", 720),
    ("480p", 480),
    ("360p", 360),
]


class TargetFormDialog(QDialog):
    def __init__(self, parent=None, *, name="", url="", enabled=True):
        super().__init__(parent)
        self.setWindowTitle("Площадка вещания")
        layout = QFormLayout(self)

        self.name_edit = QLineEdit(name)
        layout.addRow("Название:", self.name_edit)

        self.url_edit = QLineEdit(url)
        self.url_edit.setPlaceholderText("rtmp://.../input/...")
        layout.addRow("RTMP URL (с ключом):", self.url_edit)

        self.enabled_combo = QComboBox()
        self.enabled_combo.addItems(["включена", "выключена"])
        self.enabled_combo.setCurrentIndex(0 if enabled else 1)
        layout.addRow("Статус:", self.enabled_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "url": self.url_edit.text().strip(),
            "enabled": self.enabled_combo.currentIndex() == 0,
        }


class StreamTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: WorkerThread | None = None
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_incoming)
        self._timer.start(5000)
        self.refresh_incoming()
        self._load_vk_settings()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        incoming_box = QGroupBox("Входящий поток (от стримера)")
        incoming_layout = QVBoxLayout(incoming_box)
        self.incoming_label = QLabel("Проверяю...")
        self.incoming_label.setWordWrap(True)
        incoming_layout.addWidget(self.incoming_label)
        incoming_note = QLabel(
            "<i>Разрешение и битрейт входящего потока сервер задать не может — "
            "это настройки кодировщика (OBS и т.п.) у самого стримера. "
            "Здесь только то, что реально приходит сейчас.</i>"
        )
        incoming_note.setWordWrap(True)
        incoming_layout.addWidget(incoming_note)
        btn_refresh_incoming = QPushButton("Обновить сейчас")
        btn_refresh_incoming.clicked.connect(self.refresh_incoming)
        incoming_layout.addWidget(btn_refresh_incoming)
        layout.addWidget(incoming_box)

        bandwidth_box = QGroupBox("Канал сервера наружу")
        bandwidth_layout = QVBoxLayout(bandwidth_box)
        bandwidth_layout.addWidget(QLabel(
            "<i>Тест канала САМОГО СЕРВЕРА (важно для раздачи зрителям и пуша в VK) — "
            "канал стримера с сервера проверить нельзя.</i>"
        ))
        self.bandwidth_label = QLabel("Не проверялось")
        bandwidth_layout.addWidget(self.bandwidth_label)
        btn_test_bandwidth = QPushButton("Проверить канал сервера")
        btn_test_bandwidth.clicked.connect(self._on_test_bandwidth)
        self.btn_test_bandwidth = btn_test_bandwidth
        bandwidth_layout.addWidget(btn_test_bandwidth)
        layout.addWidget(bandwidth_box)

        vk_box = QGroupBox("Трансляция в VK / OK")
        vk_layout = QVBoxLayout(vk_box)

        self.vk_status_label = QLabel()
        vk_layout.addWidget(self.vk_status_label)

        form = QFormLayout()
        self.vk_bitrate_edit = QLineEdit()
        self.vk_bitrate_edit.setPlaceholderText("пусто = без ограничения (как сейчас)")
        form.addRow("Битрейт для VK (кбит/с):", self.vk_bitrate_edit)

        self.vk_resolution_combo = QComboBox()
        for label, _ in RESOLUTION_OPTIONS:
            self.vk_resolution_combo.addItem(label)
        form.addRow("Разрешение для VK:", self.vk_resolution_combo)
        vk_layout.addLayout(form)

        vk_buttons = QHBoxLayout()
        btn_save_vk = QPushButton("Сохранить настройки VK")
        btn_save_vk.clicked.connect(self._on_save_vk_settings)
        vk_buttons.addWidget(btn_save_vk)
        btn_restart_vk = QPushButton("Перезапустить трансляцию в VK")
        btn_restart_vk.clicked.connect(self._on_restart_vk)
        vk_buttons.addWidget(btn_restart_vk)
        vk_layout.addLayout(vk_buttons)

        vk_layout.addWidget(QLabel("Площадки вещания:"))
        self.targets_table = QTableWidget(0, len(TARGET_COLUMNS))
        self.targets_table.setHorizontalHeaderLabels(TARGET_COLUMNS)
        self.targets_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.targets_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.targets_table.setSelectionMode(QTableWidget.SingleSelection)
        vk_layout.addWidget(self.targets_table)

        target_buttons = QHBoxLayout()
        btn_add_target = QPushButton("Добавить площадку")
        btn_add_target.clicked.connect(self._on_add_target)
        target_buttons.addWidget(btn_add_target)
        btn_edit_target = QPushButton("Редактировать")
        btn_edit_target.clicked.connect(self._on_edit_target)
        target_buttons.addWidget(btn_edit_target)
        btn_delete_target = QPushButton("Удалить")
        btn_delete_target.clicked.connect(self._on_delete_target)
        target_buttons.addWidget(btn_delete_target)
        vk_layout.addLayout(target_buttons)

        layout.addWidget(vk_box)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Входящий поток
    # ------------------------------------------------------------------

    def refresh_incoming(self) -> None:
        def do_refresh():
            streams = stream_info.list_live_streams()
            if not streams:
                return None
            name = streams[0]
            info = stream_info.probe_incoming_stream(name)
            bitrate = stream_info.measure_segment_bitrate(name)
            return info, bitrate

        worker = WorkerThread(do_refresh)
        worker.finished_ok.connect(self._on_incoming_refreshed)
        worker.finished_error.connect(lambda err: self.incoming_label.setText(f"Ошибка проверки: {err}"))
        self._worker = worker
        worker.start()

    def _on_incoming_refreshed(self, result) -> None:
        if result is None:
            self.incoming_label.setText("Активной трансляции сейчас нет (нет .m3u8 в HLS-директории).")
            return
        info, bitrate = result
        if not info.live:
            self.incoming_label.setText(f"Поток {info.stream_name}: недоступен ({info.error})")
            return

        lines = [
            f"Поток: {info.stream_name}",
            f"Разрешение: {info.width}x{info.height}" if info.width else "Разрешение: неизвестно",
            f"FPS: {info.fps}" if info.fps else "FPS: неизвестно",
            f"Видео: {info.video_codec}, аудио: {info.audio_codec} ({info.audio_sample_rate} Гц)" if info.audio_codec else f"Видео: {info.video_codec}",
        ]
        if bitrate.segments_measured:
            lines.append(
                f"Битрейт (по последним {bitrate.segments_measured} сегментам): "
                f"~{bitrate.avg_kbps} кбит/с (мин {bitrate.min_kbps}, макс {bitrate.max_kbps})"
            )
        self.incoming_label.setText("\n".join(lines))

    # ------------------------------------------------------------------
    # Тест канала сервера
    # ------------------------------------------------------------------

    def _on_test_bandwidth(self) -> None:
        self.btn_test_bandwidth.setEnabled(False)
        self.bandwidth_label.setText("Проверяю канал сервера...")

        def do_test():
            return stream_info.test_server_bandwidth()

        worker = WorkerThread(do_test)
        worker.finished_ok.connect(self._on_bandwidth_done)
        worker.finished_error.connect(lambda err: self._on_bandwidth_done(stream_info.BandwidthTestResult(ok=False, error=err)))
        self._worker = worker
        worker.start()

    def _on_bandwidth_done(self, result) -> None:
        self.btn_test_bandwidth.setEnabled(True)
        if result.ok:
            self.bandwidth_label.setText(f"Канал сервера наружу: ~{result.mbps} Мбит/с")
        else:
            self.bandwidth_label.setText(f"Не удалось проверить: {result.error}")

    # ------------------------------------------------------------------
    # Настройки VK
    # ------------------------------------------------------------------

    def _load_vk_settings(self) -> None:
        settings = stream_info.get_vk_settings()
        self.vk_bitrate_edit.setText(str(settings.bitrate_kbps) if settings.bitrate_kbps else "")
        index = next((i for i, (_, h) in enumerate(RESOLUTION_OPTIONS) if h == settings.resolution_height), 0)
        self.vk_resolution_combo.setCurrentIndex(index)

        vk_service = get_service("vk_pusher")
        status = vk_service.status()
        self.vk_status_label.setText(f"Статус пуша в VK: {status.state.value} — {status.detail}")

        self._reload_targets_table()

    def _reload_targets_table(self) -> None:
        targets = stream_info.list_stream_targets()
        self._targets = targets
        self.targets_table.setRowCount(len(targets))
        for row, target in enumerate(targets):
            self.targets_table.setItem(row, 0, QTableWidgetItem(target.name))
            self.targets_table.setItem(row, 1, QTableWidgetItem(target.url))
            self.targets_table.setItem(row, 2, QTableWidgetItem("да" if target.enabled else "нет"))

    def _selected_target_index(self) -> int | None:
        row = self.targets_table.currentRow()
        return row if row >= 0 else None

    def _on_save_vk_settings(self) -> None:
        if not confirm_root_password(self, "изменение настроек трансляции в VK"):
            return

        bitrate_text = self.vk_bitrate_edit.text().strip()
        bitrate_kbps = None
        if bitrate_text:
            try:
                bitrate_kbps = int(bitrate_text)
                if bitrate_kbps <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Некорректный битрейт", "Битрейт должен быть положительным числом (кбит/с)")
                return

        _, resolution_height = RESOLUTION_OPTIONS[self.vk_resolution_combo.currentIndex()]

        current = stream_info.get_vk_settings()
        current.bitrate_kbps = bitrate_kbps
        current.resolution_height = resolution_height
        current.target_ids = [t.id for t in stream_info.list_stream_targets() if t.enabled]

        stream_info.save_vk_settings(current)
        QMessageBox.information(self, "Готово", "Настройки VK сохранены. Применятся при следующем запуске трансляции.")

    def _on_restart_vk(self) -> None:
        if not confirm_root_password(self, "перезапуск трансляции в VK"):
            return

        streams = stream_info.list_live_streams()
        if not streams:
            QMessageBox.warning(self, "Нет трансляции", "Сейчас нет активного входящего потока — перезапускать нечего.")
            return

        def do_restart():
            stream_info.restart_vk_push(streams[0])
            return None

        worker = WorkerThread(do_restart)
        worker.finished_ok.connect(lambda _r: self._load_vk_settings())
        worker.finished_error.connect(lambda err: QMessageBox.critical(self, "Ошибка", err))
        self._worker = worker
        worker.start()

    def _on_add_target(self) -> None:
        if not confirm_root_password(self, "добавление площадки вещания"):
            return
        dialog = TargetFormDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.values()
        if not values["name"] or not values["url"]:
            QMessageBox.warning(self, "Не заполнено", "Название и URL обязательны")
            return

        import secrets

        targets = stream_info.list_stream_targets()
        targets.append(stream_info.VkTarget(id=secrets.token_hex(4), name=values["name"], url=values["url"], enabled=values["enabled"]))
        stream_info.save_stream_targets(targets)
        self._reload_targets_table()

    def _on_edit_target(self) -> None:
        index = self._selected_target_index()
        if index is None:
            QMessageBox.warning(self, "Не выбрано", "Выберите площадку в таблице")
            return
        if not confirm_root_password(self, "редактирование площадки вещания"):
            return
        target = self._targets[index]
        dialog = TargetFormDialog(self, name=target.name, url=target.url, enabled=target.enabled)
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.values()
        target.name, target.url, target.enabled = values["name"], values["url"], values["enabled"]
        stream_info.save_stream_targets(self._targets)
        self._reload_targets_table()

    def _on_delete_target(self) -> None:
        index = self._selected_target_index()
        if index is None:
            QMessageBox.warning(self, "Не выбрано", "Выберите площадку в таблице")
            return
        if QMessageBox.question(self, "Удалить?", f"Удалить площадку «{self._targets[index].name}»?") != QMessageBox.Yes:
            return
        if not confirm_root_password(self, "удаление площадки вещания"):
            return
        del self._targets[index]
        stream_info.save_stream_targets(self._targets)
        self._reload_targets_table()
