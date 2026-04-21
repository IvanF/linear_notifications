"""Окно настроек для ввода токена Linear API."""

import os
import sys
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject

from linear_notifier.keyring_manager import KeyringManager
from linear_notifier.linear_api import LinearAPI
from linear_notifier.i18n import tr

class SettingsWindow(Gtk.Window):
    """Окно настроек."""
    
    __gsignals__ = {
        "token-saved": (GObject.SignalFlags.RUN_FIRST, None, (str,))
    }
    
    def __init__(self, app, ui_path):
        """Инициализация окна настроек."""
        super().__init__(application=app, title=tr("settings_standalone_title"))
        self.ui_path = ui_path
        self.keyring = KeyringManager()
        
        self.set_default_size(400, 150)
        self.set_resizable(False)
        
        # Загружаем UI из файла
        builder = Gtk.Builder()
        ui_file = os.path.join(ui_path, "settings.ui")
        
        if os.path.exists(ui_file):
            try:
                builder.add_from_file(ui_file)
                settings_box = builder.get_object("settings_window")
                if settings_box:
                    self.set_child(settings_box)
                    self.token_entry = builder.get_object("token_entry")
                    self.save_button = builder.get_object("save_button")
                    self.status_label = builder.get_object("status_label")
                else:
                    self._create_ui()
            except Exception as e:
                print(f"Ошибка загрузки UI файла: {e}", file=sys.stderr)
                self._create_ui()
        else:
            # Fallback: создаем UI программно
            self._create_ui()
        
        # Подключаем сигналы
        if hasattr(self, 'save_button'):
            self.save_button.connect("clicked", self.on_save_clicked)
        
        # Загружаем существующий токен если есть
        existing_token = self.keyring.get_token()
        if existing_token and hasattr(self, 'token_entry'):
            self.token_entry.set_text(existing_token)
    
    def _create_ui(self):
        """Создать UI программно (fallback)."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=20, margin_end=20, margin_top=20, margin_bottom=20)
        self.set_child(box)
        
        label = Gtk.Label(label=tr("token_label"))
        label.set_halign(Gtk.Align.START)
        box.append(label)
        
        self.token_entry = Gtk.Entry()
        self.token_entry.set_placeholder_text(tr("token_placeholder"))
        self.token_entry.set_visibility(False)  # Скрываем пароль
        box.append(self.token_entry)
        
        self.status_label = Gtk.Label(label="")
        self.status_label.set_halign(Gtk.Align.START)
        box.append(self.status_label)
        
        self.save_button = Gtk.Button(label=tr("btn_save_token"))
        self.save_button.connect("clicked", self.on_save_clicked)
        box.append(self.save_button)
    
    def on_save_clicked(self, button):
        """Обработчик нажатия кнопки сохранения."""
        token = self.token_entry.get_text().strip()
        
        if not token:
            self._show_status(tr("token_err_empty"), is_error=True)
            return
        
        # Проверяем валидность токена
        self._show_status(tr("token_validating"), is_error=False)
        api = LinearAPI(token)
        is_valid, error_msg = api.validate_token()
        if not is_valid:
            self._show_status(tr("token_err_invalid", msg=error_msg or ""), is_error=True)
            return
        
        # Сохраняем токен
        if self.keyring.save_token(token):
            self._show_status(tr("token_saved"), is_error=False)
            # Эмитируем сигнал
            self.emit("token-saved", token)
        else:
            self._show_status(tr("token_save_failed"), is_error=True)
    
    def _show_status(self, message, is_error=False):
        """Показать статусное сообщение."""
        if hasattr(self, 'status_label'):
            self.status_label.set_text(message)
            if is_error:
                self.status_label.add_css_class("error")
            else:
                self.status_label.remove_css_class("error")
