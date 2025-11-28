#!/usr/bin/env python3
"""Скрипт для установки desktop файла и иконок."""

import os
import sys
import shutil
import subprocess

def install_desktop_and_icons():
    """Установить desktop файл и иконки.
    
    Returns:
        int: 0 при успехе, 1 при ошибке
    """
    # Используем функцию из main.py для единообразия
    try:
        from linear_notifier.main import ensure_desktop_file
        success = ensure_desktop_file(force=True)
        if success:
            print("✓ Desktop файл и иконки установлены в главное меню")
            print("Приложение теперь доступно в главном меню рабочего стола")
            return 0
        else:
            print("Ошибка: Не удалось установить desktop файл и иконки", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Ошибка при установке: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(install_desktop_and_icons())

