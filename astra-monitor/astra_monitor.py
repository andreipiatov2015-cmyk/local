#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Astra Monitor - Точка входа в приложение
"""

import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gui.main_window import main

if __name__ == "__main__":
    main()