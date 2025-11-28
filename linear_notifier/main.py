#!/usr/bin/env python3
"""Main entry point for Linear Notifier application."""

import sys
import os

# Пути к данным не используются напрямую в main.py,
# они определяются в app.py при инициализации

def check_dependencies():
    """Проверка системных зависимостей при запуске."""
    missing = []
    
    try:
        import gi
    except ImportError:
        missing.append("PyGObject (gi)")
        if missing:
            print("Ошибка: Отсутствуют необходимые системные зависимости:", file=sys.stderr)
            for dep in missing:
                print(f"  - {dep}", file=sys.stderr)
            print("\nУстановите зависимости командой:", file=sys.stderr)
            print("  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-ayatanaappindicator3-0.1 libnotify4", file=sys.stderr)
            sys.exit(1)
    
    # Проверяем GTK 4 сначала (основная зависимость)
    try:
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        if Gtk.get_major_version() < 4:
            missing.append("GTK 4 (требуется версия >= 4.0)")
    except ImportError:
        missing.append("PyGObject (gi)")
    except ValueError as e:
        missing.append(f"GTK 4: {e}")
    
    # Проверяем Notify
    try:
        gi.require_version('Notify', '0.7')
        from gi.repository import Notify
    except (ImportError, ValueError) as e:
        missing.append(f"libnotify (Notify): {e}")
    
    # AyatanaAppIndicator3 проверяется в app.py при использовании,
    # так как он требует GTK 3.0, а мы используем GTK 4.0
    # Это может вызвать конфликт, но проверка будет выполнена позже
    
    if missing:
        print("Ошибка: Отсутствуют необходимые системные зависимости:", file=sys.stderr)
        for dep in missing:
            print(f"  - {dep}", file=sys.stderr)
        print("\nУстановите зависимости командой:", file=sys.stderr)
        print("  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-ayatanaappindicator3-0.1 libnotify4", file=sys.stderr)
        sys.exit(1)

def ensure_desktop_file(force=False):
    """Убедиться, что desktop файл и иконки установлены в главное меню.
    
    Returns:
        bool: True если установка прошла успешно, False в противном случае
    """
    import shutil
    import subprocess
    
    home = os.path.expanduser('~')
    desktop_dest = os.path.join(home, '.local', 'share', 'applications', 'com.example.LinearNotifier.desktop')
    
    # Если файл уже существует и не требуется принудительная установка, пропускаем
    if not force and os.path.exists(desktop_dest):
        return True  # Уже установлен
    
    # Находим файлы в пакете
    if getattr(sys, 'frozen', False):
        package_path = sys._MEIPASS
    else:
        package_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    data_path = os.path.join(package_path, 'linear_notifier', 'data')
    if not os.path.exists(data_path):
        data_path = os.path.join(package_path, 'data')
    
    desktop_source = os.path.join(data_path, 'com.example.LinearNotifier.desktop')
    
    if not os.path.exists(desktop_source):
        return False  # Не найден
    
    # Устанавливаем desktop файл
    try:
        applications_dir = os.path.dirname(desktop_dest)
        os.makedirs(applications_dir, exist_ok=True)
        shutil.copy2(desktop_source, desktop_dest)
        
        # Устанавливаем иконки
        icons_source = os.path.join(data_path, 'icons')
        if os.path.exists(icons_source):
            icons_dest = os.path.join(home, '.local', 'share', 'icons')
            for root, dirs, files in os.walk(icons_source):
                for file in files:
                    if file.endswith(('.png', '.svg', '.xpm')):
                        src_file = os.path.join(root, file)
                        # Сохраняем структуру директорий
                        rel_path = os.path.relpath(src_file, icons_source)
                        dst_file = os.path.join(icons_dest, rel_path)
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.copy2(src_file, dst_file)
        
        # Обновляем кэш desktop файлов и иконок
        try:
            subprocess.run(['update-desktop-database', applications_dir], 
                         check=False, capture_output=True, timeout=5)
            subprocess.run(['gtk-update-icon-cache', '-f', '-t', os.path.join(home, '.local', 'share', 'icons', 'hicolor')],
                         check=False, capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass
        
        return True
    except Exception:
        return False  # Ошибка при установке

def main():
    """Главная функция приложения."""
    check_dependencies()
    
    # Убеждаемся, что desktop файл установлен
    ensure_desktop_file()
    
    from linear_notifier.app import LinearNotifierApp
    
    app = LinearNotifierApp()
    app.run(sys.argv)

if __name__ == "__main__":
    main()

