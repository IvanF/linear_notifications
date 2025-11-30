"""Основной класс приложения Linear Notifier."""

import os
import sys
import threading
import time

# pystray несовместим с GTK 4.0, так как все его backends требуют GTK 3.0
# Системный трей будет отключен, приложение будет работать без иконки в трее

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Notify', '0.7')
# AyatanaAppIndicator3 импортируется лениво из-за конфликта версий GTK

from gi.repository import Gtk, Gio, Notify

# pystray импортируется лениво, чтобы избежать конфликта с GTK 4.0
PYSTRAY_AVAILABLE = None

from linear_notifier.keyring_manager import KeyringManager
from linear_notifier.linear_api import LinearAPI
from linear_notifier.settings_window import SettingsWindow
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
        self.settings_window = None
        self.main_window = None
        self.indicator = None
        self.tray_icon = None
        self.polling_thread = None
        self.polling_active = False
        self.last_notification_ids = set()
        
        # Получаем путь к UI файлам
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            # Путь относительно пакета
            base_path = os.path.dirname(os.path.abspath(__file__))
        self.ui_path = os.path.join(base_path, 'data', 'ui')
        
        # Инициализация уведомлений
        try:
            # Используем application_id для правильной работы с desktop файлом
            Notify.init("com.example.LinearNotifier")
        except Exception as e:
            print(f"Предупреждение: Не удалось инициализировать libnotify: {e}", file=sys.stderr)
    
    def do_activate(self):
        """Активация приложения."""
        token = self.keyring.get_token()
        
        if not token:
            # Первый запуск - показываем окно настроек
            self.show_settings_window()
        else:
            # Токен есть - запускаем основное приложение
            if not self.linear_api:
                self.linear_api = LinearAPI(token)
                self.setup_indicator()
                self.start_polling()
            
            # Если приложение уже запущено и вызывается do_activate (например, при клике на уведомление)
            # открываем главное окно
            if self.linear_api:
                self.on_open_action(None, None)
    
    def show_settings_window(self):
        """Показать окно настроек."""
        if self.settings_window:
            self.settings_window.present()
            return
        
        self.settings_window = SettingsWindow(self, self.ui_path)
        self.settings_window.connect("token-saved", self.on_token_saved)
        self.settings_window.present()
    
    def on_token_saved(self, window, token):
        """Обработчик сохранения токена."""
        self.linear_api = LinearAPI(token)
        if self.settings_window:
            self.settings_window.close()
            self.settings_window = None
        
        self.setup_indicator()
        self.start_polling()
        
        # Показываем уведомление о том, что приложение работает в фоне
        try:
            notify = Notify.Notification.new(
                "Linear Notifier",
                "Приложение запущено и работает в фоне. Откройте его через главное меню для просмотра уведомлений.",
                "linear-notifier"
            )
            notify.set_urgency(Notify.Urgency.LOW)
            notify.show()
        except Exception:
            pass  # Игнорируем ошибки уведомлений
    
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
        Gtk.idle_add(self.on_open_action, None, None)
    
    def _on_tray_settings(self, icon, item):
        """Обработчик выбора настроек в меню трея."""
        # Вызываем GTK функцию из главного потока
        Gtk.idle_add(self.on_settings_action, None, None)
    
    def _on_tray_quit(self, icon, item):
        """Обработчик выхода из приложения."""
        # Вызываем GTK функцию из главного потока
        Gtk.idle_add(self._do_quit)
    
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
    
    def _poll_loop(self):
        """Цикл polling уведомлений."""
        while self.polling_active:
            try:
                notifications = self.linear_api.get_notifications(first=25)
                
                if notifications:
                    # Фильтруем только непрочитанные
                    unread = [n for n in notifications if isinstance(n, dict) and n.get('archivedAt') is None]
                    
                    # Проверяем новые уведомления
                    current_ids = {n.get('id') for n in unread if n.get('id')}
                    new_ids = current_ids - self.last_notification_ids
                    
                    # Если есть новые уведомления, обновляем главное окно (если оно открыто)
                    if new_ids and self.main_window:
                        # Обновляем список уведомлений в главном окне через главный поток GTK
                        Gtk.idle_add(self._refresh_main_window_notifications)
                    
                    for notification in unread:
                        if notification.get('id') in new_ids:
                            self._show_desktop_notification(notification)
                    
                    self.last_notification_ids = current_ids
                else:
                    # Нет уведомлений
                    self.last_notification_ids = set()
                
            except Exception as e:
                print(f"Ошибка при polling: {e}", file=sys.stderr)
            
            # Ждем 60 секунд (1 минута) до следующего polling
            for _ in range(60):
                if not self.polling_active:
                    break
                time.sleep(1)
    
    def _show_desktop_notification(self, notification):
        """Показать desktop уведомление."""
        title = self._format_notification_title(notification)
        body = self._format_notification_body(notification)
        
        notify = Notify.Notification.new(title, body, "linear-notifier")
        notify.set_urgency(Notify.Urgency.NORMAL)
        
        # Устанавливаем app_name для правильной работы с desktop файлом
        # В GNOME клик по уведомлению открывает приложение через desktop файл
        try:
            notify.set_app_name("Linear Notifier")
        except:
            pass
        
        # Добавляем действие для открытия главного окна при клике
        # В libnotify действия обрабатываются через callback в add_action
        # "default" - это специальное действие, которое вызывается при клике на само уведомление
        notify.add_action("default", "Открыть", self._on_notification_clicked, None)
        
        # Подключаем сигнал "closed" для обработки клика по самому уведомлению
        # В GNOME клик по уведомлению обычно закрывает его, и мы обрабатываем это
        notify.connect("closed", self._on_notification_closed)
        
        # Сохраняем ссылку на уведомление для отслеживания
        notify._linear_notification = notification
        
        notify.show()
    
    def _on_notification_clicked(self, notification, action_name, user_data):
        """Обработчик клика на desktop уведомление (действие)."""
        print("Клик на уведомление (действие)", file=sys.stderr)
        # Вызываем GTK функцию из главного потока
        Gtk.idle_add(self._open_main_window)
    
    def _on_notification_closed(self, notification, reason):
        """Обработчик закрытия уведомления."""
        # Получаем числовое значение причины закрытия
        try:
            reason_value = int(reason)
        except (ValueError, TypeError):
            try:
                reason_value = int(str(reason))
            except:
                reason_value = None
        
        print(f"Уведомление закрыто, причина: {reason} (значение: {reason_value})", file=sys.stderr)
        
        # В libnotify:
        # 1 = EXPIRED (истекло)
        # 2 = DISMISSED (закрыто пользователем вручную или клик)
        # 3 = ACTION (клик на действие)
        
        # В GNOME клик по уведомлению обычно закрывает его с причиной DISMISSED (2)
        # Открываем главное окно при любом закрытии, кроме истечения времени
        if reason == Notify.NotificationClosedReason.EXPIRED or reason_value == 1:
            # Уведомление истекло - не открываем окно
            print("Уведомление истекло, не открываем окно", file=sys.stderr)
        else:
            # Уведомление было закрыто пользователем (клик по уведомлению или закрытие)
            # В GNOME клик по уведомлению обычно открывает приложение
            print("Открываем главное окно при закрытии уведомления", file=sys.stderr)
            # Используем idle_add для вызова из главного потока GTK
            Gtk.idle_add(self._open_main_window)
    
    def _refresh_main_window_notifications(self):
        """Обновить список уведомлений в главном окне (вызывается из главного потока GTK)."""
        try:
            if self.main_window and self.main_window.is_visible():
                self.main_window.refresh_notifications()
        except Exception as e:
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
            import traceback
            print(f"Ошибка при открытии главного окна: {e}", file=sys.stderr)
            print(f"Детали: {traceback.format_exc()}", file=sys.stderr)
        return False  # Удаляем из idle queue
    
    def _format_notification_title(self, notification):
        """Форматирование заголовка уведомления."""
        ntype = notification.get('type', 'Unknown')
        if ntype == 'IssueNotification':
            issue = notification.get('issue', {})
            identifier = issue.get('identifier', '')
            return f"Linear: {identifier}"
        elif ntype == 'ProjectNotification':
            project = notification.get('project', {})
            name = project.get('name', 'Project')
            return f"Linear: {name}"
        else:
            return "Linear: Новое уведомление"
    
    def _format_notification_body(self, notification):
        """Форматирование тела уведомления."""
        ntype = notification.get('type', 'Unknown')
        if ntype == 'IssueNotification':
            issue = notification.get('issue', {})
            title = issue.get('title', '')
            return title
        elif ntype == 'ProjectNotification':
            project = notification.get('project', {})
            name = project.get('name', 'Project')
            return f"Обновление проекта: {name}"
        else:
            return "Новое уведомление"

