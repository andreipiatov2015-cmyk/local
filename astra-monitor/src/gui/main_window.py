#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главное окно приложения Astra Monitor
"""

import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QTextEdit, QSplitter, QGroupBox, QGridLayout,
    QStatusBar, QMessageBox, QDialog, QLineEdit, QCheckBox,
    QSpinBox, QComboBox, QProgressDialog, QApplication, QStyle,
    QToolButton, QFrame, QScrollArea, QSizePolicy, QSpacerItem,
    QWizard, QWizardPage, QTextBrowser, QListWidget, QListWidgetItem,
    QStackedWidget, QFormLayout, QDoubleSpinBox, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

from src.core import (
    SystemMonitor, SiteMonitor, GitUpdater, UpdateStatus,
    SiteDeployer, DeployStatus, ServiceManager, ServiceState
)
from src.core.git_updater import UpdateResult
from src.core.deployer import DeployResult

import threading
import time


class WorkerThread(QThread):
    """Поток для выполнения фоновых задач"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DeployWizard(QWizard):
    """Мастер развёртывания сайта"""
    
    def __init__(self, deployer: SiteDeployer, parent=None):
        super().__init__(parent)
        self.deployer = deployer
        self.setWindowTitle("Мастер установки сайта")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        
        # Страницы
        self.addPage(self.createIntroPage())
        self.addPage(self.createRequirementsPage())
        self.addPage(self.createDeployPage())
        self.addPage(self.createFinishPage())
        
        self.deploy_result = None
    
    def createIntroPage(self) -> QWizardPage:
        """Вводная страница"""
        page = QWizardPage()
        page.setTitle("Добро пожаловать в мастер установки")
        page.setSubTitle("Этот мастер поможет установить и настроить сайт на сервере.")
        
        layout = QVBoxLayout()
        
        text = QTextBrowser()
        text.setHtml("""
        <h3>Что будет установлено:</h3>
        <ul>
            <li><b>Nginx</b> - веб-сервер для обработки HTTP запросов</li>
            <li><b>Python приложения</b> - Flask серверы для работы сайта</li>
            <li><b>RTMP сервер</b> - для потокового видео</li>
            <li><b>Systemd сервисы</b> - для автозапуска приложений</li>
            <li><b>Файлы сайта</b> - все компоненты веб-приложения</li>
        </ul>
        
        <h3>Требования:</h3>
        <ul>
            <li>Права суперпользователя (root)</li>
            <li>Ubuntu/Debian или Astra Linux</li>
            <li>Подключение к интернету</li>
        </ul>
        
        <p><b>Внимание:</b> Установка может занять 10-15 минут.</p>
        """)
        layout.addWidget(text)
        
        page.setLayout(layout)
        return page
    
    def createRequirementsPage(self) -> QWizardPage:
        """Проверка требований"""
        page = QWizardPage()
        page.setTitle("Проверка системы")
        page.setSubTitle("Проверка системных требований...")
        
        layout = QVBoxLayout()
        
        self.requirements_label = QLabel("Проверка...")
        layout.addWidget(self.requirements_label)
        
        self.requirements_table = QTableWidget()
        self.requirements_table.setColumnCount(2)
        self.requirements_table.setHorizontalHeaderLabels(["Компонент", "Статус"])
        self.requirements_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.requirements_table)
        
        page.setLayout(layout)
        
        # Проверяем при показе страницы
        page.enterId = self.checkRequirements
        
        return page
    
    def checkRequirements(self):
        """Проверить требования"""
        can_deploy, info = self.deployer.check_system()
        
        self.requirements_table.setRowCount(5)
        checks = [
            ("Операционная система", "✓ " + info['os'] if info['is_root'] else "✗"),
            ("Права root", "✓ Доступны" if info['is_root'] else "✗ Требуются"),
            ("Python", info['python_version']),
            ("Отсутствующие пакеты", str(len(info['missing_packages'])) if info['missing_packages'] else "Нет"),
            ("Готов к установке", "✓ Да" if can_deploy else "✗ Нет"),
        ]
        
        for i, (comp, status) in enumerate(checks):
            self.requirements_table.setItem(i, 0, QTableWidgetItem(comp))
            item = QTableWidgetItem(status)
            if "✗" in status:
                item.setBackground(QColor(255, 182, 193))
            elif "✓" in status:
                item.setBackground(QColor(144, 238, 144))
            self.requirements_table.setItem(i, 1, item)
        
        self.requirements_label.setText(
            "Система готова к установке!" if can_deploy 
            else "Для продолжения необходимо устранить проблемы"
        )
        
        return can_deploy
    
    def createDeployPage(self) -> QWizardPage:
        """Страница развёртывания"""
        page = QWizardPage()
        page.setTitle("Установка")
        page.setSubTitle("Идёт установка сайта...")
        
        layout = QVBoxLayout()
        
        self.deploy_progress = QProgressBar()
        self.deploy_progress.setRange(0, 100)
        layout.addWidget(self.deploy_progress)
        
        self.deploy_log = QTextEdit()
        self.deploy_log.setReadOnly(True)
        self.deploy_log.setMaximumHeight(200)
        layout.addWidget(self.deploy_log)
        
        self.deploy_status_label = QLabel("Готов к установке")
        layout.addWidget(self.deploy_status_label)
        
        page.setLayout(layout)
        return page
    
    def createFinishPage(self) -> QWizardPage:
        """Финальная страница"""
        page = QWizardPage()
        page.setTitle("Установка завершена")
        page.setSubTitle("Результат установки")
        
        layout = QVBoxLayout()
        
        self.finish_label = QLabel("")
        self.finish_label.setWordWrap(True)
        layout.addWidget(self.finish_label)
        
        page.setLayout(layout)
        return page
    
    def runDeployment(self):
        """Запустить развёртывание"""
        self.deployer.progress_callback = self.onDeployProgress
        self.deploy_result = self.deployer.deploy()
        
        if self.deploy_result.success:
            self.deployer.start_services()
        
        return self.deploy_result
    
    def onDeployProgress(self, message: str, step: str = None):
        """Обработчик прогресса"""
        self.deploy_log.append(message)
        
        # Обновляем прогресс бар
        if step:
            steps = ['dependencies', 'directories', 'files', 'nginx', 'nginx_rtmp']
            if step in steps:
                progress = (steps.index(step) + 1) * 15
                self.deploy_progress.setValue(progress)


class DeployTab(QWidget):
    """Вкладка установки сайта"""
    
    def __init__(self, deployer: SiteDeployer):
        super().__init__()
        self.deployer = deployer
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Статус
        status_group = QGroupBox("Статус развёртывания")
        status_layout = QGridLayout()
        
        self.status_label = QLabel("Проверка...")
        status_layout.addWidget(QLabel("Состояние:"), 0, 0)
        status_layout.addWidget(self.status_label, 0, 1)
        
        self.site_path_label = QLabel("-")
        status_layout.addWidget(QLabel("Путь к сайту:"), 1, 0)
        status_layout.addWidget(self.site_path_label, 1, 1)
        
        self.install_btn = QPushButton("🖥️ Установить сайт")
        self.install_btn.clicked.connect(self.start_install)
        status_layout.addWidget(self.install_btn, 2, 0, 1, 2)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Детали
        details_group = QGroupBox("Компоненты для установки")
        details_layout = QVBoxLayout()
        
        components = [
            ("📦", "Системные пакеты", "Nginx, Python, ffmpeg и др."),
            ("📁", "Директории", "/var/www, /var/log, /var/mount_point"),
            ("📋", "Файлы сайта", "Flask приложения, статика, конфиги"),
            ("🌐", "Nginx", "Веб-сервер с proxy на Flask"),
            ("📺", "Nginx RTMP", "Сервер потокового видео"),
            ("⚙️", "Systemd сервисы", "Автозапуск приложений"),
        ]
        
        for icon, name, desc in components:
            row = QHBoxLayout()
            row.addWidget(QLabel(icon))
            row.addWidget(QLabel(f"<b>{name}</b>"))
            row.addWidget(QLabel(desc))
            row.addStretch()
            details_layout.addLayout(row)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Лог
        log_group = QGroupBox("Лог установки")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
    
    def check_status(self):
        """Проверить статус"""
        status = self.deployer.get_deploy_status()
        
        # Показываем найденный путь
        site_path = status.get('site_path', 'Не найден')
        self.site_path_label.setText(site_path if site_path else "Не найден")
        
        if status['site_files']:
            self.status_label.setText("✓ Сайт обнаружен")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.install_btn.setText("🔄 Переустановить сайт")
        else:
            self.status_label.setText("○ Сайт не установлен")
            self.status_label.setStyleSheet("")
            self.install_btn.setText("🖥️ Установить сайт")
    
    def start_install(self):
        """Начать установку"""
        reply = QMessageBox.question(
            self, 'Подтверждение',
            'Начать установку сайта? Это может занять 10-15 минут.',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.install_btn.setEnabled(False)
            self.log_text.clear()
            
            self.thread = WorkerThread(self._install_worker)
            self.thread.finished.connect(self._on_install_finished)
            self.thread.error.connect(self._on_install_error)
            self.thread.start()
    
    def _install_worker(self) -> DeployResult:
        return self.deployer.deploy()
    
    def _on_install_finished(self, result: DeployResult):
        self.install_btn.setEnabled(True)
        
        if result.success:
            self.log_text.append("\n=== Запуск сервисов ===")
            success, errors = self.deployer.start_services()
            
            QMessageBox.information(
                self, "Успех",
                "Сайт успешно установлен и запущен!"
            )
        else:
            QMessageBox.warning(
                self, "Ошибки",
                f"Установка завершена с ошибками:\n{result.message}"
            )
        
        self.check_status()
    
    def _on_install_error(self, error: str):
        self.install_btn.setEnabled(True)
        self.log_text.append(f"Ошибка: {error}")
        QMessageBox.critical(self, "Ошибка", f"Критическая ошибка: {error}")


class ServiceTab(QWidget):
    """Вкладка управления сервисами"""
    
    def __init__(self, service_manager: ServiceManager):
        super().__init__()
        self.manager = service_manager
        self.init_ui()
        
        # Таймер обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(3000)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Сводка
        summary_group = QGroupBox("Сводка")
        summary_layout = QGridLayout()
        
        self.total_label = QLabel("-")
        self.running_label = QLabel("-")
        self.stopped_label = QLabel("-")
        
        summary_layout.addWidget(QLabel("Всего сервисов:"), 0, 0)
        summary_layout.addWidget(self.total_label, 0, 1)
        summary_layout.addWidget(QLabel("Работает:"), 0, 2)
        summary_layout.addWidget(self.running_label, 0, 3)
        summary_layout.addWidget(QLabel("Остановлено:"), 0, 4)
        summary_layout.addWidget(self.stopped_label, 0, 5)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # Таблица сервисов
        table_group = QGroupBox("Сервисы")
        table_layout = QVBoxLayout()
        
        self.services_table = QTableWidget()
        self.services_table.setColumnCount(6)
        self.services_table.setHorizontalHeaderLabels([
            "Сервис", "Описание", "Статус", "PID", "Порт", "Uptime"
        ])
        self.services_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.services_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.services_table.setColumnWidth(0, 120)
        
        table_layout.addWidget(self.services_table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        
        start_all_btn = QPushButton("▶ Запустить все")
        start_all_btn.clicked.connect(self.start_all)
        
        stop_all_btn = QPushButton("⏹ Остановить все")
        stop_all_btn.clicked.connect(self.stop_all)
        
        restart_all_btn = QPushButton("🔄 Перезапустить все")
        restart_all_btn.clicked.connect(self.restart_all)
        
        refresh_btn = QPushButton("🔍 Обновить")
        refresh_btn.clicked.connect(self.refresh_data)
        
        btn_layout.addWidget(start_all_btn)
        btn_layout.addWidget(stop_all_btn)
        btn_layout.addWidget(restart_all_btn)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def refresh_data(self):
        """Обновить данные"""
        try:
            summary = self.manager.get_site_status_summary()
            
            self.total_label.setText(str(summary['total']))
            
            running = summary['running']
            self.running_label.setText(f"<span style='color: green'>{running}</span>")
            
            stopped = summary['stopped']
            self.stopped_label.setText(f"<span style='color: red'>{stopped}</span>")
            
            # Таблица
            self.services_table.setRowCount(len(summary['services']))
            for i, svc in enumerate(summary['services']):
                self.services_table.setItem(i, 0, QTableWidgetItem(svc['display_name']))
                self.services_table.setItem(i, 1, QTableWidgetItem(svc['description']))
                
                state_item = QTableWidgetItem(svc['state'].upper())
                if svc['state'] == 'running':
                    state_item.setBackground(QColor(144, 238, 144))
                elif svc['state'] == 'stopped':
                    state_item.setBackground(QColor(255, 182, 193))
                self.services_table.setItem(i, 2, state_item)
                
                self.services_table.setItem(i, 3, QTableWidgetItem(
                    str(svc['pid']) if svc['pid'] else "-"
                ))
                self.services_table.setItem(i, 4, QTableWidgetItem(
                    str(svc['port']) if svc['port'] else "-"
                ))
                self.services_table.setItem(i, 5, QTableWidgetItem(svc['uptime'] or "-"))
                
        except Exception as e:
            print(f"Ошибка обновления сервисов: {e}")
    
    def start_all(self):
        """Запустить все сервисы"""
        self.thread = WorkerThread(self.manager.start_all_site_services)
        self.thread.finished.connect(lambda r: self._on_action_finished(r, "Запуск"))
        self.thread.start()
    
    def stop_all(self):
        """Остановить все сервисы"""
        reply = QMessageBox.question(
            self, 'Подтверждение',
            'Остановить все сервисы сайта?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.thread = WorkerThread(self.manager.stop_all_site_services)
            self.thread.finished.connect(lambda r: self._on_action_finished(r, "Остановка"))
            self.thread.start()
    
    def restart_all(self):
        """Перезапустить все сервисы"""
        self.thread = WorkerThread(self.manager.restart_all_site_services)
        self.thread.finished.connect(lambda r: self._on_action_finished(r, "Перезапуск"))
        self.thread.start()
    
    def _on_action_finished(self, result, action):
        success, errors = result
        if success:
            QMessageBox.information(self, "Успех", f"{action} завершён!")
        else:
            QMessageBox.warning(self, "Внимание", f"{action} завершён с ошибками: {errors}")
        self.refresh_data()


class SystemTab(QWidget):
    """Вкладка системного мониторинга"""
    
    def __init__(self, system_monitor: SystemMonitor):
        super().__init__()
        self.monitor = system_monitor
        self.init_ui()
        
        # Таймер обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(2000)  # Обновление каждые 2 секунды
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Общая статистика ---
        stats_group = QGroupBox("Системная статистика")
        stats_layout = QGridLayout()
        
        # CPU
        self.cpu_label = QLabel("CPU: 0%")
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setMaximum(100)
        self.cpu_count_label = QLabel("Ядер: -")
        
        stats_layout.addWidget(QLabel("Процессор:"), 0, 0)
        stats_layout.addWidget(self.cpu_label, 0, 1)
        stats_layout.addWidget(self.cpu_bar, 0, 2)
        stats_layout.addWidget(self.cpu_count_label, 0, 3)
        
        # Память
        self.mem_label = QLabel("Память: 0 GB / 0 GB (0%)")
        self.mem_bar = QProgressBar()
        self.mem_bar.setMaximum(100)
        
        stats_layout.addWidget(QLabel("Память:"), 1, 0)
        stats_layout.addWidget(self.mem_label, 1, 1, 1, 2)
        stats_layout.addWidget(self.mem_bar, 1, 3)
        
        # Диск
        self.disk_label = QLabel("Диск: 0 GB / 0 GB (0%)")
        self.disk_bar = QProgressBar()
        self.disk_bar.setMaximum(100)
        
        stats_layout.addWidget(QLabel("Диск:"), 2, 0)
        stats_layout.addWidget(self.disk_label, 2, 1, 1, 2)
        stats_layout.addWidget(self.disk_bar, 2, 3)
        
        # Load Average
        self.load_label = QLabel("Load Avg: -")
        self.uptime_label = QLabel("Uptime: -")
        
        stats_layout.addWidget(QLabel("Нагрузка:"), 3, 0)
        stats_layout.addWidget(self.load_label, 3, 1)
        stats_layout.addWidget(QLabel("Работает:"), 3, 2)
        stats_layout.addWidget(self.uptime_label, 3, 3)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # --- Сплиттер для таблиц ---
        splitter = QSplitter(Qt.Horizontal)
        
        # --- Порты ---
        ports_group = QGroupBox("Открытые порты")
        ports_layout = QVBoxLayout()
        
        self.ports_table = QTableWidget()
        self.ports_table.setColumnCount(5)
        self.ports_table.setHorizontalHeaderLabels(["Порт", "Протокол", "Адрес", "Процесс", "Сервис"])
        self.ports_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.ports_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.ports_table.setColumnWidth(0, 60)
        self.ports_table.setColumnWidth(1, 70)
        self.ports_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.ports_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.ports_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.ports_table.setMaximumHeight(200)
        
        ports_layout.addWidget(self.ports_table)
        ports_group.setLayout(ports_layout)
        splitter.addWidget(ports_group)
        
        # --- Процессы ---
        proc_group = QGroupBox("Топ процессов (по CPU)")
        proc_layout = QVBoxLayout()
        
        self.proc_table = QTableWidget()
        self.proc_table.setColumnCount(5)
        self.proc_table.setHorizontalHeaderLabels(["PID", "Имя", "CPU%", "MEM%", "RAM (MB)"])
        self.proc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.proc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in [2, 3, 4]:
            self.proc_table.setColumnWidth(i, 60)
        self.proc_table.setMaximumHeight(200)
        
        proc_layout.addWidget(self.proc_table)
        proc_group.setLayout(proc_layout)
        splitter.addWidget(proc_group)
        
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
        
        # --- Сеть ---
        net_group = QGroupBox("Сетевая статистика")
        net_layout = QGridLayout()
        
        self.net_sent_label = QLabel("Отправлено: -")
        self.net_recv_label = QLabel("Получено: -")
        self.net_err_label = QLabel("Ошибки: -")
        
        net_layout.addWidget(self.net_sent_label, 0, 0)
        net_layout.addWidget(self.net_recv_label, 0, 1)
        net_layout.addWidget(self.net_err_label, 0, 2)
        
        net_group.setLayout(net_layout)
        layout.addWidget(net_group)
        
        # Кнопка обновления
        refresh_btn = QPushButton("Обновить сейчас")
        refresh_btn.clicked.connect(self.refresh_data)
        layout.addWidget(refresh_btn)
    
    def refresh_data(self):
        """Обновить данные"""
        try:
            stats = self.monitor.get_system_stats()
            
            # CPU
            self.cpu_label.setText(f"CPU: {stats.cpu_percent:.1f}%")
            self.cpu_bar.setValue(int(stats.cpu_percent))
            self.cpu_count_label.setText(f"Ядер: {stats.cpu_count}")
            
            # Memory
            mem_str = f"Память: {stats.memory_used_gb:.1f} / {stats.memory_total_gb:.1f} GB ({stats.memory_percent:.1f}%)"
            self.mem_label.setText(mem_str)
            self.mem_bar.setValue(int(stats.memory_percent))
            
            # Disk
            disk_str = f"Диск: {stats.disk_used_gb:.1f} / {stats.disk_total_gb:.1f} GB ({stats.disk_percent:.1f}%)"
            self.disk_label.setText(disk_str)
            self.disk_bar.setValue(int(stats.disk_percent))
            
            # Load & Uptime
            self.load_label.setText(f"Load Avg: {stats.load_average[0]:.2f} {stats.load_average[1]:.2f} {stats.load_average[2]:.2f}")
            self.uptime_label.setText(f"Uptime: {stats.uptime}")
            
            # Ports
            self._update_ports()
            
            # Processes
            self._update_processes()
            
            # Network
            net = self.monitor.get_network_stats()
            self.net_sent_label.setText(f"Отправлено: {self._format_bytes(net.get('bytes_sent', 0))}")
            self.net_recv_label.setText(f"Получено: {self._format_bytes(net.get('bytes_recv', 0))}")
            self.net_err_label.setText(f"Ошибки: {net.get('errin', 0)} / {net.get('errout', 0)}")
            
        except Exception as e:
            print(f"Ошибка обновления системных данных: {e}")
    
    def _update_ports(self):
        """Обновить таблицу портов"""
        ports = self.monitor.get_listening_ports()
        
        # Фильтруем только веб-порты
        web_ports = [p for p in ports if p.port in [80, 443, 8080, 8082, 8083, 8084, 1935, 3000, 5000, 6080, 5901] or p.service]
        
        self.ports_table.setRowCount(len(web_ports))
        for i, port in enumerate(web_ports):
            self.ports_table.setItem(i, 0, QTableWidgetItem(str(port.port)))
            self.ports_table.setItem(i, 1, QTableWidgetItem(port.protocol.upper()))
            self.ports_table.setItem(i, 2, QTableWidgetItem(port.local_address))
            self.ports_table.setItem(i, 3, QTableWidgetItem(port.name or str(port.pid)))
            self.ports_table.setItem(i, 4, QTableWidgetItem(port.service or "-"))
    
    def _update_processes(self):
        """Обновить таблицу процессов"""
        processes = self.monitor.get_processes(15)
        
        self.proc_table.setRowCount(len(processes))
        for i, proc in enumerate(processes):
            self.proc_table.setItem(i, 0, QTableWidgetItem(str(proc.pid)))
            self.proc_table.setItem(i, 1, QTableWidgetItem(proc.name[:30]))
            self.proc_table.setItem(i, 2, QTableWidgetItem(f"{proc.cpu_percent:.1f}"))
            self.proc_table.setItem(i, 3, QTableWidgetItem(f"{proc.memory_percent:.1f}"))
            self.proc_table.setItem(i, 4, QTableWidgetItem(f"{proc.memory_mb:.0f}"))
    
    def _format_bytes(self, num):
        """Форматировать байты в читаемый вид"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if num < 1024:
                return f"{num:.1f} {unit}"
            num /= 1024
        return f"{num:.1f} PB"


class SiteTab(QWidget):
    """Вкладка мониторинга сайта"""
    
    def __init__(self, site_monitor: SiteMonitor):
        super().__init__()
        self.monitor = site_monitor
        self.init_ui()
        
        # Таймер обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(5000)  # Обновление каждые 5 секунд
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Общая статистика ---
        stats_group = QGroupBox("Статистика сайта")
        stats_layout = QGridLayout()
        
        self.total_components_label = QLabel("Всего компонентов: -")
        self.active_components_label = QLabel("Активных: -")
        self.inactive_components_label = QLabel("Неактивных: -")
        self.entries_label = QLabel("Записей: -")
        self.db_size_label = QLabel("Размер БД: -")
        self.log_size_label = QLabel("Размер логов: -")
        
        stats_layout.addWidget(self.total_components_label, 0, 0)
        stats_layout.addWidget(self.active_components_label, 0, 1)
        stats_layout.addWidget(self.inactive_components_label, 0, 2)
        stats_layout.addWidget(self.entries_label, 1, 0)
        stats_layout.addWidget(self.db_size_label, 1, 1)
        stats_layout.addWidget(self.log_size_label, 1, 2)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # --- Компоненты ---
        components_group = QGroupBox("Компоненты сайта")
        comp_layout = QVBoxLayout()
        
        self.components_table = QTableWidget()
        self.components_table.setColumnCount(5)
        self.components_table.setHorizontalHeaderLabels(["Компонент", "Тип", "Статус", "Используется", "Путь"])
        self.components_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.components_table.setColumnWidth(0, 150)
        self.components_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.components_table.setColumnWidth(1, 80)
        self.components_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.components_table.setColumnWidth(2, 80)
        self.components_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.components_table.setColumnWidth(3, 80)
        self.components_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        
        comp_layout.addWidget(self.components_table)
        components_group.setLayout(comp_layout)
        layout.addWidget(components_group)
        
        # --- HTTP сервисы ---
        http_group = QGroupBox("HTTP сервисы")
        http_layout = QGridLayout()
        
        self.http_live_label = QLabel("live-server (8083): -")
        self.http_reboot_label = QLabel("reboot-server (8084): -")
        self.http_rtmp_hls_label = QLabel("nginx-rtmp HLS (8082): -")
        self.http_rtmp_http_label = QLabel("nginx-rtmp HTTP (8080): -")
        
        http_layout.addWidget(self.http_live_label, 0, 0)
        http_layout.addWidget(self.http_reboot_label, 0, 1)
        http_layout.addWidget(self.http_rtmp_hls_label, 1, 0)
        http_layout.addWidget(self.http_rtmp_http_label, 1, 1)
        
        http_group.setLayout(http_layout)
        layout.addWidget(http_group)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_data)
        restart_btn = QPushButton("Перезапустить сервисы")
        restart_btn.clicked.connect(self.restart_services)
        
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(restart_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def refresh_data(self):
        """Обновить данные"""
        try:
            stats = self.monitor.get_site_stats()
            
            self.total_components_label.setText(f"Всего компонентов: {stats.total_components}")
            self.active_components_label.setText(f"Активных: {stats.active_components}")
            self.inactive_components_label.setText(f"Неактивных: {stats.inactive_components}")
            self.entries_label.setText(f"Записей: {stats.total_entries}")
            self.db_size_label.setText(f"Размер БД: {stats.database_size_kb:.1f} KB")
            self.log_size_label.setText(f"Размер логов: {stats.log_size_mb:.1f} MB")
            
            # Компоненты
            self._update_components()
            
            # HTTP сервисы
            self._update_http_services()
            
        except Exception as e:
            print(f"Ошибка обновления данных сайта: {e}")
    
    def _update_components(self):
        """Обновить таблицу компонентов"""
        components = self.monitor.get_all_components()
        
        self.components_table.setRowCount(len(components))
        for i, comp in enumerate(components):
            self.components_table.setItem(i, 0, QTableWidgetItem(comp.name))
            self.components_table.setItem(i, 1, QTableWidgetItem(comp.type))
            
            status_item = QTableWidgetItem(comp.status)
            if comp.status == "active":
                status_item.setBackground(QColor(144, 238, 144))  # Зелёный
            elif comp.status == "inactive":
                status_item.setBackground(QColor(255, 182, 193))  # Красный
            self.components_table.setItem(i, 2, status_item)
            
            self.components_table.setItem(i, 3, QTableWidgetItem("Да" if comp.is_used else "Нет"))
            self.components_table.setItem(i, 4, QTableWidgetItem(comp.path))
    
    def _update_http_services(self):
        """Обновить статус HTTP сервисов"""
        services = self.monitor.check_http_services()
        
        for name, info in services.items():
            status = info.get('status', 'unknown')
            http_status = info.get('http_status')
            
            if name == "live-server":
                status_text = f"live-server (8083): {status.upper()}" + (f" ({http_status})" if http_status else "")
                self.http_live_label.setText(status_text)
            elif name == "reboot-server":
                status_text = f"reboot-server (8084): {status.upper()}" + (f" ({http_status})" if http_status else "")
                self.http_reboot_label.setText(status_text)
            elif name == "nginx-rtmp-hls":
                status_text = f"nginx-rtmp HLS (8082): {status.upper()}" + (f" ({http_status})" if http_status else "")
                self.http_rtmp_hls_label.setText(status_text)
            elif name == "nginx-rtmp-http":
                status_text = f"nginx-rtmp HTTP (8080): {status.upper()}" + (f" ({http_status})" if http_status else "")
                self.http_rtmp_http_label.setText(status_text)
    
    def restart_services(self):
        """Перезапустить сервисы"""
        reply = QMessageBox.question(
            self, 'Подтверждение',
            'Перезапустить все сервисы сайта?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Запускаем в отдельном потоке
                self.thread = WorkerThread(self._restart_services_worker)
                self.thread.finished.connect(self._on_restart_finished)
                self.thread.error.connect(self._on_restart_error)
                self.thread.start()
                
                QMessageBox.information(self, "Информация", "Сервисы перезапускаются...")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось перезапустить сервисы: {e}")
    
    def _restart_services_worker(self):
        """Worker для перезапуска сервисов"""
        import subprocess
        result = subprocess.run(
            ['/bin/bash', '/var/www/restart_astra.sh'],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0
    
    def _on_restart_finished(self, success):
        if success:
            QMessageBox.information(self, "Успех", "Сервисы успешно перезапущены!")
            self.refresh_data()
        else:
            QMessageBox.warning(self, "Внимание", "Сервисы перезапущены, но возможны ошибки.")
    
    def _on_restart_error(self, error):
        QMessageBox.critical(self, "Ошибка", f"Ошибка перезапуска: {error}")


class UpdateTab(QWidget):
    """Вкладка обновления"""
    
    def __init__(self, repo_path: str = "/var/www"):
        super().__init__()
        self.repo_path = repo_path
        self.updater = GitUpdater(repo_path)
        self.init_ui()
        self.refresh_data()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Информация о репозитории ---
        repo_group = QGroupBox("Информация о репозитории")
        repo_layout = QGridLayout()
        
        self.branch_label = QLabel("Ветка: -")
        self.commit_label = QLabel("Коммит: -")
        self.update_status_label = QLabel("Статус обновлений: -")
        
        repo_layout.addWidget(QLabel("Текущая ветка:"), 0, 0)
        repo_layout.addWidget(self.branch_label, 0, 1)
        repo_layout.addWidget(QLabel("Текущий коммит:"), 1, 0)
        repo_layout.addWidget(self.commit_label, 1, 1)
        repo_layout.addWidget(QLabel("Обновления:"), 2, 0)
        repo_layout.addWidget(self.update_status_label, 2, 1)
        
        repo_group.setLayout(repo_layout)
        layout.addWidget(repo_group)
        
        # --- Управление ---
        control_group = QGroupBox("Управление обновлениями")
        control_layout = QHBoxLayout()
        
        self.check_btn = QPushButton("Проверить обновления")
        self.check_btn.clicked.connect(self.check_updates)
        
        self.update_btn = QPushButton("Обновить сайт")
        self.update_btn.clicked.connect(self.do_update)
        self.update_btn.setEnabled(False)
        
        self.pull_btn = QPushButton("Pull изменения")
        self.pull_btn.clicked.connect(self.do_pull)
        
        control_layout.addWidget(self.check_btn)
        control_layout.addWidget(self.update_btn)
        control_layout.addWidget(self.pull_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # --- Лог ---
        log_group = QGroupBox("Лог операций")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # --- История коммитов ---
        commits_group = QGroupBox("Последние коммиты")
        commits_layout = QVBoxLayout()
        
        self.commits_table = QTableWidget()
        self.commits_table.setColumnCount(4)
        self.commits_table.setHorizontalHeaderLabels(["Хеш", "Автор", "Дата", "Сообщение"])
        self.commits_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.commits_table.setMaximumHeight(150)
        
        commits_layout.addWidget(self.commits_table)
        commits_group.setLayout(commits_layout)
        layout.addWidget(commits_group)
        
        layout.addStretch()
    
    def log_message(self, msg: str):
        """Добавить сообщение в лог"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")
    
    def refresh_data(self):
        """Обновить данные о репозитории"""
        if not self.updater.is_git_repo():
            self.log_message("Папка не является git репозиторием")
            return
        
        info = self.updater.get_repo_info()
        
        self.branch_label.setText(info.get('branch', '-'))
        self.commit_label.setText(info.get('head', '-'))
        
        if info.get('has_update'):
            self.update_status_label.setText(f"Есть обновления!")
            self.update_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.update_btn.setEnabled(True)
        else:
            self.update_status_label.setText("Обновлений нет")
            self.update_status_label.setStyleSheet("")
            self.update_btn.setEnabled(False)
        
        # Коммиты
        commits = self.updater.get_commits(10)
        self.commits_table.setRowCount(len(commits))
        for i, commit in enumerate(commits):
            self.commits_table.setItem(i, 0, QTableWidgetItem(commit.short_hash))
            self.commits_table.setItem(i, 1, QTableWidgetItem(commit.author))
            self.commits_table.setItem(i, 2, QTableWidgetItem(commit.date[:10]))
            self.commits_table.setItem(i, 3, QTableWidgetItem(commit.message[:60]))
    
    def check_updates(self):
        """Проверить обновления"""
        self.log_message("Проверка обновлений...")
        self.check_btn.setEnabled(False)
        
        self.thread = WorkerThread(self._check_updates_worker)
        self.thread.finished.connect(self._on_check_finished)
        self.thread.start()
    
    def _check_updates_worker(self):
        return self.updater.check_for_updates()
    
    def _on_check_finished(self, result):
        has_update, message, remote = result
        self.log_message(message)
        self.check_btn.setEnabled(True)
        self.refresh_data()
    
    def do_update(self):
        """Выполнить обновление"""
        reply = QMessageBox.question(
            self, 'Подтверждение',
            'Обновить сайт до последней версии из репозитория?',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.log_message("Начинаю обновление...")
            self.update_btn.setEnabled(False)
            
            self.thread = WorkerThread(self._update_worker)
            self.thread.finished.connect(self._on_update_finished)
            self.thread.error.connect(self._on_update_error)
            self.thread.start()
    
    def _update_worker(self) -> UpdateResult:
        return self.updater.pull_changes()
    
    def _on_update_finished(self, result: UpdateResult):
        self.log_message(result.message)
        if result.status == UpdateStatus.SUCCESS:
            self.log_message(f"Было: {result.old_version} -> Стало: {result.new_version}")
            if result.files_updated:
                self.log_message(f"Обновлено файлов: {len(result.files_updated)}")
        else:
            self.log_message(f"Ошибка: {result.error}")
        
        self.update_btn.setEnabled(True)
        self.refresh_data()
    
    def _on_update_error(self, error: str):
        self.log_message(f"Критическая ошибка: {error}")
        self.update_btn.setEnabled(True)
    
    def do_pull(self):
        """Выполнить git pull"""
        self.log_message("Выполняю git pull...")
        self.pull_btn.setEnabled(False)
        
        self.thread = WorkerThread(self._pull_worker)
        self.thread.finished.connect(self._on_pull_finished)
        self.thread.start()
    
    def _pull_worker(self):
        return self.updater._run_git(['pull'])
    
    def _on_pull_finished(self, result):
        if result.returncode == 0:
            self.log_message("Pull выполнен успешно")
        else:
            self.log_message(f"Ошибка pull: {result.stderr}")
        
        self.pull_btn.setEnabled(True)
        self.refresh_data()


class SettingsDialog(QDialog):
    """Диалог настроек"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Путь к репозиторию
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Путь к сайту:"))
        self.path_edit = QLineEdit("/var/www")
        path_layout.addWidget(self.path_edit)
        layout.addLayout(path_layout)
        
        # Интервал обновления
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Интервал обновления (сек):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setMinimum(1)
        self.interval_spin.setMaximum(300)
        self.interval_spin.setValue(5)
        interval_layout.addWidget(self.interval_spin)
        layout.addLayout(interval_layout)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Сохранить")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        
        self.site_path = "/var/www"
        self.update_interval = 5
        
        # Инициализация мониторов и управляющих модулей
        self.system_monitor = SystemMonitor()
        self.site_monitor = SiteMonitor(self.site_path)
        self.git_updater = GitUpdater(self.site_path)
        self.deployer = SiteDeployer(self.site_path)
        self.service_manager = ServiceManager()
        
        self.init_ui()
        self.setStyleSheet(self._get_stylesheet())
    
    def init_ui(self):
        self.setWindowTitle("Astra Monitor - Панель управления сайтом")
        self.setMinimumSize(1100, 750)
        
        # Центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Табы
        self.tabs = QTabWidget()
        
        # 1. Вкладка установки
        self.deploy_tab = DeployTab(self.deployer)
        self.tabs.addTab(self.deploy_tab, "🚀 Установка")
        
        # 2. Вкладка управления сервисами
        self.service_tab = ServiceTab(self.service_manager)
        self.tabs.addTab(self.service_tab, "⚙️ Сервисы")
        
        # 3. Вкладка мониторинга
        self.system_tab = SystemTab(self.system_monitor)
        self.tabs.addTab(self.system_tab, "💻 Система")
        
        # 4. Вкладка сайта
        self.site_tab = SiteTab(self.site_monitor)
        self.tabs.addTab(self.site_tab, "🌐 Сайт")
        
        # 5. Вкладка обновлений
        self.update_tab = UpdateTab(self.site_path)
        self.tabs.addTab(self.update_tab, "🔄 Обновления")
        
        layout.addWidget(self.tabs)
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")
        
        # Меню
        self._create_menu()
        
        # Начальная проверка статуса
        QTimer.singleShot(500, self.deploy_tab.check_status)
    
    def _create_menu(self):
        menubar = self.menuBar()
        
        # Файл
        file_menu = menubar.addMenu("📁 Файл")
        
        refresh_action = file_menu.addAction("🔄 Обновить все")
        refresh_action.triggered.connect(self.refresh_all)
        
        wizard_action = file_menu.addAction("🚀 Мастер установки...")
        wizard_action.triggered.connect(self.show_install_wizard)
        
        file_menu.addSeparator()
        
        settings_action = file_menu.addAction("⚙️ Настройки...")
        settings_action.triggered.connect(self.show_settings)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("🚪 Выход")
        exit_action.triggered.connect(self.close)
        
        # Управление
        control_menu = menubar.addMenu("⚡ Управление")
        
        start_all_action = control_menu.addAction("▶ Запустить все сервисы")
        start_all_action.triggered.connect(lambda: self.service_tab.start_all())
        
        stop_all_action = control_menu.addAction("⏹ Остановить все сервисы")
        stop_all_action.triggered.connect(lambda: self.service_tab.stop_all())
        
        restart_all_action = control_menu.addAction("🔄 Перезапустить все сервисы")
        restart_all_action.triggered.connect(lambda: self.service_tab.restart_all())
        
        # Вид
        view_menu = menubar.addMenu("👁 Вид")
        
        tabs = [
            ("🚀 Установка", 0),
            ("⚙️ Сервисы", 1),
            ("💻 Система", 2),
            ("🌐 Сайт", 3),
            ("🔄 Обновления", 4),
        ]
        
        for name, idx in tabs:
            action = view_menu.addAction(name)
            action.triggered.connect(lambda _, i=idx: self.tabs.setCurrentIndex(i))
        
        # Справка
        help_menu = menubar.addMenu("❓ Справка")
        
        about_action = help_menu.addAction("ℹ️ О программе")
        about_action.triggered.connect(self.show_about)
    
    def show_install_wizard(self):
        """Показать мастер установки"""
        wizard = DeployWizard(self.deployer, self)
        wizard.exec_()
    
    def refresh_all(self):
        """Обновить все данные"""
        self.status_bar.showMessage("Обновление...")
        try:
            self.deploy_tab.check_status()
            self.service_tab.refresh_data()
            self.system_tab.refresh_data()
            self.site_tab.refresh_data()
            self.update_tab.refresh_data()
            self.status_bar.showMessage("Готово", 3000)
        except Exception as e:
            self.status_bar.showMessage(f"Ошибка: {e}")
    
    def show_settings(self):
        """Показать настройки"""
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self.site_path = dialog.path_edit.text()
            self.update_interval = dialog.interval_spin.value()
            self.status_bar.showMessage("Настройки сохранены", 3000)
    
    def show_about(self):
        """Показать о программе"""
        QMessageBox.about(
            self,
            "О программе",
            "<h3>Astra Monitor</h3>"
            "<p>Версия: 1.0.0</p>"
            "<p>Система мониторинга и управления сайтом для Astra Linux</p>"
            "<p>© 2024</p>"
        )
    
    def _get_stylesheet(self) -> str:
        """Получить таблицу стилей для Astra Linux"""
        return """
        QMainWindow {
            background-color: #f5f5f5;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            min-width: 100px;
            padding: 5px 15px;
            border: 1px solid #999;
            border-radius: 4px;
            background-color: #e8e8e8;
        }
        QPushButton:hover {
            background-color: #d8d8d8;
        }
        QPushButton:pressed {
            background-color: #c8c8c8;
        }
        QPushButton:disabled {
            background-color: #f0f0f0;
            color: #999;
        }
        QTableWidget {
            border: 1px solid #ccc;
            gridline-color: #ddd;
            background-color: white;
        }
        QHeaderView::section {
            background-color: #e8e8e8;
            padding: 4px;
            border: 1px solid #ccc;
            font-weight: bold;
        }
        QTabWidget::pane {
            border: 1px solid #ccc;
            background-color: white;
        }
        QTabBar::tab {
            padding: 8px 20px;
            background-color: #e8e8e8;
            border: 1px solid #ccc;
            border-bottom: none;
        }
        QTabBar::tab:selected {
            background-color: white;
        }
        QProgressBar {
            border: 1px solid #999;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #4CAF50;
        }
        QTextEdit {
            border: 1px solid #ccc;
            background-color: white;
        }
        """


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Astra Monitor")
    app.setOrganizationName("Astra")
    
    # Установка шрифта для совместимости с Astra Linux
    font = QFont()
    font.setFamily("Sans Serif")
    font.setPointSize(10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()