#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты Astra Monitor
"""

from .helpers import (
    is_root, require_root, check_dependency,
    install_dependencies, get_resource_path,
    ensure_directories, get_desktop_entry, get_systemd_service
)

__all__ = [
    'is_root', 'require_root', 'check_dependency',
    'install_dependencies', 'get_resource_path',
    'ensure_directories', 'get_desktop_entry', 'get_systemd_service'
]