"""Основной класс приложения Linear Notifier."""

import os
import sys
import threading
import time
from typing import Optional

# pystray несовместим с GTK 4.0, так как все его backends требуют GTK 3.0
# Системный трей будет отключен, приложение будет работать без иконки в трее

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
# AyatanaAppIndicator3 импортируется лениво из-за конфликта версий GTK

from gi.repository import Gtk, Gio, GLib, Gdk

# pystray импортируется лениво, чтобы избежать конфликта с GTK 4.0
PYSTRAY_AVAILABLE = None

from linear_notifier.keyring_manager import KeyringManager
from linear_notifier.linear_api import LinearAPI, is_transient_linear_error
from linear_notifier.i18n import tr, translate_notification_type
from linear_notifier.main_window import MainWindow


class LinearNotifierApp(Gtk.Application):
    """Главное приложение Linear Notifier."""
    
    def __init__(self):
        super().__init__(
            application_id="com.example.LinearNotifier",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        # Регистрируем действие для открытия главного окна
        # Это позволит открывать окно при клике на уведомление через desktop файл
        action = Gio.SimpleAction.new("open", None)
        action.connect("activate", self.on_open_action)
        self.add_action(action)
        # Держим приложение живым даже когда все окна закрыты
        self.hold()
        
        self.keyring = KeyringManager()
        self.linear_api = None
        self.main_window = None
        self.indicator = None
        self.tray_icon = None
        self.polling_thread = None
        self.polling_active = False
        self.last_notification_ids = set()
        self._linear_connected = None
        self._connectivity_source_id = None
        self._disconnect_notified = False
        self._cached_notify_icon_name = None
        
        # Получаем путь к UI файлам
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            # Путь относительно пакета
            base_path = os.path.dirname(os.path.abspath(__file__))
        self.ui_path = os.path.join(base_path, 'data', 'ui')
    
    def do_activate(self):
        """Активация приложения."""
        token = self.keyring.get_token()
        
        if not token:
            if not self.main_window:
                self.main_window = MainWindow(self, None, self.ui_path)
                self.main_window.connect("token-saved", self.on_token_saved)
            self.main_window.present()
            self.main_window.focus_settings_tab()
            return
        
        if not self.linear_api:
            self.linear_api = LinearAPI(token)
            self.setup_indicator()
            self.start_polling()
        
        if self.linear_api:
            self.on_open_action(None, None)
    
    def show_settings_window(self):
        """Открыть главное окно на вкладке настроек."""
        if not self.main_window:
            self.main_window = MainWindow(self, self.linear_api, self.ui_path)
            self.main_window.connect("token-saved", self.on_token_saved)
        self.main_window.present()
        self.main_window.focus_settings_tab()
    
    def on_token_saved(self, window, token):
        """Обработчик сохранения токена."""
        self.linear_api = LinearAPI(token)
        self.setup_indicator()
        self.start_polling()
        if self.main_window:
            self.main_window.set_linear_api(self.linear_api)
        
        self._send_app_notification(
            "startup",
            tr("startup_notify_title"),
            tr("startup_notify_body"),
            priority=Gio.NotificationPriority.LOW,
        )
    
    def setup_indicator(self):
        """Настройка системного трея."""
        # Используем pystray для создания иконки в системном трее (совместимо с GTK 4)
        # Импортируем pystray лениво, чтобы избежать конфликта с GTK 4.0
        global PYSTRAY_AVAILABLE
        
        # pystray несовместим с GTK 4.0 (все его backends требуют GTK 3.0)
        # Отключаем системный трей
        PYSTRAY_AVAILABLE = False
        self.tray_icon = None
        print("Примечание: Системный трей недоступен из-за несовместимости pystray с GTK 4.0", file=sys.stderr)
        print("Приложение будет работать без иконки в трее. Откройте его через главное меню.", file=sys.stderr)
        return
        
        if not PYSTRAY_AVAILABLE:
            self.tray_icon = None
            return
        
        try:
            from pystray import Icon, Menu, MenuItem
            from PIL import Image, ImageDraw
            
            # Создаем иконку для трея
            icon_image = self._create_tray_icon()
            if icon_image is None:
                print("Ошибка: Не удалось создать изображение иконки", file=sys.stderr)
                self.tray_icon = None
                return
            
            # Создаем меню для трея
            # Первый пункт меню будет вызываться при клике левой кнопкой мыши
            menu = Menu(
                MenuItem("Открыть", self._on_tray_open, default=True),
                MenuItem("Настройки", self._on_tray_settings),
                Menu.SEPARATOR,
                MenuItem("Выход", self._on_tray_quit)
            )
            
            # Создаем иконку в трее
            self.tray_icon = Icon("linear-notifier", icon_image, "Linear Notifier", menu)
            
            # Запускаем иконку в отдельном потоке
            def run_tray():
                try:
                    self.tray_icon.run()
                except Exception as e:
                    print(f"Ошибка при запуске иконки в трее: {e}", file=sys.stderr)
            
            tray_thread = threading.Thread(target=run_tray, daemon=True)
            tray_thread.start()
            
            # Даем немного времени на инициализацию
            time.sleep(0.1)
            
            print("Иконка в системном трее создана", file=sys.stderr)
            
        except Exception as e:
            import traceback
            print(f"Предупреждение: Не удалось создать системный трей: {e}", file=sys.stderr)
            print(f"Детали ошибки: {traceback.format_exc()}", file=sys.stderr)
            self.tray_icon = None
        
        # Подключаем действия для использования через главное меню
        action_open = Gio.SimpleAction.new("open", None)
        action_open.connect("activate", self.on_open_action)
        self.add_action(action_open)
        
        action_settings = Gio.SimpleAction.new("settings", None)
        action_settings.connect("activate", self.on_settings_action)
        self.add_action(action_settings)
        
        action_quit = Gio.SimpleAction.new("quit", None)
        action_quit.connect("activate", self.on_quit_action)
        self.add_action(action_quit)
    
    def _create_tray_icon(self):
        """Создать изображение иконки для системного трея."""
        try:
            from PIL import Image, ImageDraw
            
            # Создаем простое изображение иконки (синий круг с буквой L)
            # Используем RGBA для поддержки прозрачности
            image = Image.new('RGBA', (64, 64), (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)
            
            # Рисуем синий круг
            draw.ellipse([8, 8, 56, 56], fill=(59, 130, 246, 255), outline=(37, 99, 235, 255), width=2)
            
            # Рисуем белую букву L
            try:
                from PIL import ImageFont
                # Пытаемся использовать системный шрифт
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            except:
                # Fallback на стандартный шрифт
                font = None
            draw.text((20, 16), "L", fill=(255, 255, 255, 255), font=font)
            
            return image
        except Exception as e:
            print(f"Ошибка при создании иконки: {e}", file=sys.stderr)
            import traceback
            print(f"Детали: {traceback.format_exc()}", file=sys.stderr)
            return None
    
    def _on_tray_open(self, icon, item):
        """Обработчик клика на иконку в трее (левая кнопка мыши)."""
        # Вызываем GTK функцию из главного потока
        GLib.idle_add(self.on_open_action, None, None)
    
    def _on_tray_settings(self, icon, item):
        """Обработчик выбора настроек в меню трея."""
        # Вызываем GTK функцию из главного потока
        GLib.idle_add(self.on_settings_action, None, None)
    
    def _on_tray_quit(self, icon, item):
        """Обработчик выхода из приложения."""
        # Вызываем GTK функцию из главного потока
        GLib.idle_add(self._do_quit)
    
    def _do_quit(self):
        """Выполнить выход из приложения."""
        if self.tray_icon:
            self.tray_icon.stop()
        self.on_quit_action(None, None)
    
    def on_open_action(self, action, param):
        """Открыть главное окно."""
        if not self.linear_api:
            # Если токен еще не установлен, показываем окно настроек
            self.show_settings_window()
            return
        
        if not self.main_window:
            self.main_window = MainWindow(self, self.linear_api, self.ui_path)
            self.main_window.connect("token-saved", self.on_token_saved)
        self.main_window.present()
        # Небольшая задержка, чтобы окно успело отобразиться
        import time
        time.sleep(0.1)
        self.main_window.refresh_notifications()
        # Также обновляем лог при открытии окна
        if hasattr(self.main_window, 'refresh_log'):
            self.main_window.refresh_log()
    
    def on_settings_action(self, action, param):
        """Открыть настройки."""
        self.show_settings_window()
    
    def on_quit_action(self, action, param):
        """Выход из приложения."""
        self.polling_active = False
        if self._connectivity_source_id is not None:
            GLib.source_remove(self._connectivity_source_id)
            self._connectivity_source_id = None
        if self.polling_thread:
            self.polling_thread.join(timeout=2)
        # Останавливаем иконку в трее
        if self.tray_icon:
            self.tray_icon.stop()
        # Освобождаем hold перед выходом
        self.release()
        self.quit()
    
    def start_polling(self):
        """Запуск фонового polling."""
        if self.polling_active:
            return
        
        self.polling_active = True
        self.polling_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.polling_thread.start()
        self.start_connectivity_monitor()
    
    def _notify_icon_name(self) -> str:
        """Иконка для desktop-уведомлений: облако (своя или из темы)."""
        if self._cached_notify_icon_name:
            return self._cached_notify_icon_name
        for candidate in ("com.example.LinearNotifier.notify", "weather-clouds-symbolic"):
            try:
                display = Gdk.Display.get_default()
                if display:
                    theme = Gtk.IconTheme.get_for_display(display)
                    if theme.has_icon(candidate):
                        self._cached_notify_icon_name = candidate
                        return candidate
            except Exception:
                continue
        self._cached_notify_icon_name = "weather-clouds-symbolic"
        return self._cached_notify_icon_name

    def _send_app_notification(
        self,
        notif_id: str,
        title: str,
        body: str,
        *,
        priority=Gio.NotificationPriority.NORMAL,
        icon_name: Optional[str] = None,
    ) -> None:
        """Показать уведомление через Gio: клик запускает действие app.open (главное окно)."""
        try:
            n = Gio.Notification()
            n.set_title(title)
            n.set_body(body)
            n.set_default_action("app.open")
            name = icon_name if icon_name else self._notify_icon_name()
            n.set_icon(Gio.ThemedIcon.new(name))
            n.set_priority(priority)
            self.send_notification(notif_id, n)
        except Exception as e:
            print(f"Предупреждение: не удалось показать уведомление: {e}", file=sys.stderr)
    
    def start_connectivity_monitor(self):
        """Периодическая проверка связи с Linear (каждые 30 с)."""
        if self._connectivity_source_id is not None:
            return
        GLib.idle_add(self._schedule_connectivity_ping)
        self._connectivity_source_id = GLib.timeout_add_seconds(
            30, self._connectivity_timer_cb
        )
    
    def _schedule_connectivity_ping(self):
        self._spawn_connectivity_ping()
        return False
    
    def _connectivity_timer_cb(self):
        self._spawn_connectivity_ping()
        return True
    
    def _spawn_connectivity_ping(self):
        if not self.linear_api or not self.polling_active:
            return
        self._spawn_immediate_ping()

    def _spawn_immediate_ping(self) -> None:
        """Проверка Linear API в фоне; обновляет индикатор связи."""
        if not self.linear_api:
            return

        def worker():
            try:
                self.linear_api.ping()
                GLib.idle_add(self._idle_apply_connectivity, True)
            except Exception as e:
                # Временный сбой сети не переводит индикатор в «нет связи» и не триггерит push
                if is_transient_linear_error(e):
                    return
                GLib.idle_add(self._idle_apply_connectivity, False)

        threading.Thread(target=worker, daemon=True).start()

    def force_reconnect(self) -> None:
        """Немедленный ping и обновление списка уведомлений (без ожидания таймера опроса)."""
        if not self.linear_api:
            return
        self._spawn_immediate_ping()
        GLib.idle_add(self._idle_refresh_notifications_after_reconnect)

    def _idle_refresh_notifications_after_reconnect(self):
        if self.main_window:
            self.main_window.refresh_notifications()
        return False
    
    def _idle_apply_connectivity(self, ok: bool):
        self._apply_connectivity_result(ok)
        return False
    
    def _apply_connectivity_result(self, ok: bool):
        """Обновить состояние связи и при необходимости показать пуш об обрыве."""
        prev = self._linear_connected
        self._linear_connected = ok
        if self.main_window:
            self.main_window.set_linear_reachable(ok)
        if prev is True and not ok:
            if not self._disconnect_notified:
                self._disconnect_notified = True
                self._show_disconnect_notification()
        if ok:
            self._disconnect_notified = False
    
    def _show_disconnect_notification(self):
        """Пуш: нет связи с Linear."""
        self._send_app_notification(
            "linear-disconnect",
            tr("startup_notify_title"),
            tr("disconnect_notify_body"),
            priority=Gio.NotificationPriority.HIGH,
            icon_name="network-offline-symbolic",
        )
    
    def _poll_loop(self):
        """Цикл polling уведомлений."""
        while self.polling_active:
            try:
                notifications = self.linear_api.get_notifications(first=25)
                GLib.idle_add(self._idle_apply_connectivity, True)
                
                if notifications:
                    # Фильтруем только непрочитанные
                    unread = [n for n in notifications if isinstance(n, dict) and n.get('archivedAt') is None]
                    
                    # Проверяем новые уведомления
                    current_ids = {n.get('id') for n in unread if n.get('id')}
                    new_ids = current_ids - self.last_notification_ids
                    
                    # Если есть новые уведомления, обновляем главное окно (если оно открыто)
                    if new_ids and self.main_window:
                        # Обновляем список уведомлений в главном окне через главный поток GTK
                        GLib.idle_add(self._refresh_main_window_notifications)
                    
                    for notification in unread:
                        if notification.get('id') in new_ids:
                            # Уведомления/GTK не потокобезопасны: show из polling-потока
                            # в GNOME часто не показывает баблы — только главный поток.
                            GLib.idle_add(self._idle_show_desktop_notification, notification)
                    
                    self.last_notification_ids = current_ids
                else:
                    # Нет уведомлений
                    self.last_notification_ids = set()
                
            except Exception as e:
                if is_transient_linear_error(e):
                    print(f"Предупреждение: временный сбой polling: {e}", file=sys.stderr)
                else:
                    print(f"Ошибка при polling: {e}", file=sys.stderr)
                    GLib.idle_add(self._idle_apply_connectivity, False)
            
            # Ждем 60 секунд (1 минута) до следующего polling
            for _ in range(60):
                if not self.polling_active:
                    break
                time.sleep(1)
    
    def _idle_show_desktop_notification(self, notification):
        """Вызов _show_desktop_notification из главного потока (через GLib.idle_add)."""
        try:
            self._show_desktop_notification(notification)
        except Exception as e:
            print(f"Ошибка при показе desktop уведомления: {e}", file=sys.stderr)
        return False  # однократный idle callback

    def _show_desktop_notification(self, notification):
        """Показать desktop-уведомление; клик по баблу открывает главное окно (Gio + app.open)."""
        title = self._format_notification_title(notification)
        body = self._format_notification_body(notification)
        nid = notification.get("id")
        notif_id = f"linear-{nid}" if nid is not None else f"linear-{id(notification)}"
        self._send_app_notification(
            notif_id,
            title,
            body,
            priority=Gio.NotificationPriority.NORMAL,
        )
    
    def _refresh_main_window_notifications(self):
        """Обновить список уведомлений в главном окне (вызывается из главного потока GTK)."""
        try:
            if self.main_window and self.main_window.is_visible():
                self.main_window.refresh_notifications()
        except Exception as e:
            if is_transient_linear_error(e):
                print(f"Предупреждение: не удалось обновить список: {e}", file=sys.stderr)
            else:
                import traceback
                print(f"Ошибка при обновлении списка уведомлений: {e}", file=sys.stderr)
                print(f"Детали: {traceback.format_exc()}", file=sys.stderr)
        return False  # Удаляем из idle queue
    
    def _open_main_window(self):
        """Открыть главное окно (вызывается из главного потока GTK)."""
        print("Открываем главное окно со списком уведомлений", file=sys.stderr)
        try:
            if not self.linear_api:
                print("Ошибка: linear_api не инициализирован", file=sys.stderr)
                return False
            
            if not self.main_window:
                print("Создаем новое главное окно", file=sys.stderr)
                self.main_window = MainWindow(self, self.linear_api, self.ui_path)
                self.main_window.connect("token-saved", self.on_token_saved)
            else:
                print("Используем существующее главное окно", file=sys.stderr)
            
            self.main_window.present()
            print("Обновляем список уведомлений (25 последних)", file=sys.stderr)
            # Небольшая задержка, чтобы окно успело отобразиться
            import time
            time.sleep(0.1)
            self.main_window.refresh_notifications()
            # Лог будет обновляться автоматически при переключении на вкладку
        except Exception as e:
            if is_transient_linear_error(e):
                print(f"Предупреждение: не удалось обновить данные окна: {e}", file=sys.stderr)
            else:
                import traceback
                print(f"Ошибка при открытии главного окна: {e}", file=sys.stderr)
                print(f"Детали: {traceback.format_exc()}", file=sys.stderr)
        return False  # Удаляем из idle queue
    
    def _format_notification_title(self, notification):
        """Форматирование заголовка уведомления (тип + номер задачи, если есть)."""
        ntype = notification.get("type") or "Unknown"
        type_label = translate_notification_type(ntype)
        issue = notification.get("issue")
        if isinstance(issue, dict):
            ident = (issue.get("identifier") or "").strip()
            if ident:
                return tr("linear_dot", a=type_label, b=ident)
        if ntype == "ProjectNotification":
            project = notification.get("project", {})
            name = (project.get("name") or tr("project_fallback")).strip()
            return tr("linear_dot", a=type_label, b=name)
        return tr("linear_dot_two", a=type_label)
    
    def _format_notification_body(self, notification):
        """Форматирование тела уведомления (название задачи / суть)."""
        ntype = notification.get("type") or "Unknown"
        issue = notification.get("issue")
        if isinstance(issue, dict):
            title = (issue.get("title") or "").strip()
            if title:
                return title
            ident = (issue.get("identifier") or "").strip()
            return ident or translate_notification_type(ntype)
        if ntype == "ProjectNotification":
            project = notification.get("project", {})
            name = project.get("name", tr("project_fallback"))
            return tr("project_update_body", name=name)
        return translate_notification_type(ntype)

