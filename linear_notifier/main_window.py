"""Главное окно приложения с отображением уведомлений."""

import os
from datetime import datetime, timezone

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib

from linear_notifier.linear_api import LinearAPI

class MainWindow(Gtk.Window):
    """Главное окно с уведомлениями."""
    
    def __init__(self, app, linear_api: LinearAPI, ui_path):
        """Инициализация главного окна."""
        super().__init__(application=app, title="Linear Notifier")
        self.linear_api = linear_api
        self.ui_path = ui_path
        self.workspace_url_key = None
        
        self.set_default_size(600, 500)
        
        # Всегда создаем UI программно с вкладками
        # UI файл может не существовать или не содержать нужные элементы
        self._create_ui()
        
        # Получаем workspace urlKey асинхронно после создания UI
        # Это не блокирует открытие окна
        self._load_workspace_url_key()
    
    def _create_ui(self):
        """Создать UI программно (fallback)."""
        # Создаем Notebook для вкладок
        notebook = Gtk.Notebook()
        self.set_child(notebook)
        
        # Вкладка 1: Уведомления
        notifications_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)
        
        # ScrolledWindow для списка уведомлений
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        notifications_box.append(scrolled)
        
        # ListBox для уведомлений
        self.notifications_list = Gtk.ListBox()
        self.notifications_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.notifications_list)
        
        # Добавляем вкладку уведомлений
        notifications_label = Gtk.Label(label="Уведомления")
        notebook.append_page(notifications_box, notifications_label)
        
        # Вкладка 2: Лог запросов
        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)
        
        # ScrolledWindow для списка логов
        log_scrolled = Gtk.ScrolledWindow()
        log_scrolled.set_vexpand(True)
        log_box.append(log_scrolled)
        
        # ListBox для логов
        self.log_list = Gtk.ListBox()
        self.log_list.set_selection_mode(Gtk.SelectionMode.NONE)
        log_scrolled.set_child(self.log_list)
        
        # Добавляем вкладку лога
        log_label = Gtk.Label(label="Лог запросов")
        log_page_index = notebook.append_page(log_box, log_label)
        
        # Сохраняем индекс вкладки лога для автоматического обновления
        self.log_page_index = log_page_index
        
        # Подключаем сигнал переключения вкладок для автоматического обновления лога
        notebook.connect("switch-page", self.on_notebook_switch_page)
        
        self._auto_refresh_source_id = None
        self.connect("destroy", self._on_destroy)
        self.connect("notify::visible", self._on_visible_changed)
        
        # Запускаем автоматическое обновление уведомлений
        self._start_auto_refresh()
    
    def _load_workspace_url_key(self):
        """Загрузить workspace urlKey асинхронно."""
        def load_in_background():
            try:
                self.workspace_url_key = self.linear_api.get_workspace_url_key()
                if self.workspace_url_key:
                    import sys
                    print(f"Workspace urlKey загружен: {self.workspace_url_key}", file=sys.stderr)
            except Exception as e:
                import sys
                print(f"Предупреждение: Не удалось получить workspace urlKey: {e}", file=sys.stderr)
        
        # Запускаем в отдельном потоке, чтобы не блокировать UI
        import threading
        thread = threading.Thread(target=load_in_background, daemon=True)
        thread.start()
    
    def _start_auto_refresh(self):
        """Запустить автоматическое обновление уведомлений."""
        if self._auto_refresh_source_id is not None:
            GLib.source_remove(self._auto_refresh_source_id)
            self._auto_refresh_source_id = None
        
        # Обновляем сразу при открытии окна
        self.refresh_notifications()
        
        # Таймер не останавливаем при скрытии окна: иначе после закрытия окна
        # обратный отсчёт «N мин. назад» замирает до пересоздания окна.
        self._auto_refresh_source_id = GLib.timeout_add_seconds(
            60, self._auto_refresh_callback
        )
    
    def _auto_refresh_callback(self):
        """Callback для автоматического обновления."""
        if self.is_visible():
            self.refresh_notifications()
        return True
    
    def _on_visible_changed(self, obj, pspec):
        """Сразу обновить подписи времени при показе окна (после скрытия)."""
        if self.get_visible():
            self.refresh_notifications()
    
    def _on_destroy(self, widget):
        if self._auto_refresh_source_id is not None:
            GLib.source_remove(self._auto_refresh_source_id)
            self._auto_refresh_source_id = None
    
    def refresh_notifications(self):
        """Обновить список уведомлений."""
        import sys
        
        # Проверяем, что notifications_list существует
        if not hasattr(self, 'notifications_list') or self.notifications_list is None:
            print("Ошибка: notifications_list не инициализирован", file=sys.stderr)
            return
        
        # Проверяем, что linear_api существует
        if not self.linear_api:
            print("Ошибка: linear_api не инициализирован", file=sys.stderr)
            error_row = Gtk.ListBoxRow()
            error_label = Gtk.Label(label="Ошибка: API не инициализирован")
            error_label.set_margin_start(10)
            error_label.set_margin_end(10)
            error_label.set_margin_top(10)
            error_label.set_margin_bottom(10)
            error_row.set_child(error_label)
            self.notifications_list.append(error_row)
            return
        
        # Обновляем workspace_url_key, если еще не получен (не блокируем, если еще загружается)
        if self.workspace_url_key is None:
            try:
                # Пробуем получить, но не ждем долго
                self.workspace_url_key = self.linear_api.get_workspace_url_key()
            except Exception as e:
                print(f"Предупреждение: Не удалось получить workspace urlKey: {e}", file=sys.stderr)
                # Продолжаем работу без workspace - ссылки будут формироваться без него
        
        # Очищаем список
        while True:
            row = self.notifications_list.get_row_at_index(0)
            if row is None:
                break
            self.notifications_list.remove(row)
        
        try:
            print("Загружаем уведомления...", file=sys.stderr)
            notifications = self.linear_api.get_notifications(first=25)
            print(f"Получено уведомлений: {len(notifications) if notifications else 0}", file=sys.stderr)
            
            if not notifications:
                # Показываем сообщение об отсутствии уведомлений
                empty_row = Gtk.ListBoxRow()
                empty_label = Gtk.Label(label="Нет уведомлений")
                empty_label.set_margin_start(10)
                empty_label.set_margin_end(10)
                empty_label.set_margin_top(10)
                empty_label.set_margin_bottom(10)
                empty_row.set_child(empty_label)
                self.notifications_list.append(empty_row)
            else:
                for notification in notifications:
                    row = self._create_notification_row(notification)
                    self.notifications_list.append(row)
        except Exception as e:
            import traceback
            print(f"Ошибка при загрузке уведомлений: {e}", file=sys.stderr)
            print(f"Детали: {traceback.format_exc()}", file=sys.stderr)
            # Показываем ошибку
            error_row = Gtk.ListBoxRow()
            error_label = Gtk.Label(label=f"Ошибка загрузки: {e}")
            error_label.set_margin_start(10)
            error_label.set_margin_end(10)
            error_label.set_margin_top(10)
            error_label.set_margin_bottom(10)
            error_row.set_child(error_label)
            self.notifications_list.append(error_row)
    
    def _create_notification_row(self, notification):
        """Создать строку для уведомления."""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)
        row.set_child(box)
        
        # Заголовок
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.append(header_box)
        
        ntype = notification.get('type', 'Unknown')
        type_label = Gtk.Label(label=ntype)
        type_label.set_halign(Gtk.Align.START)
        type_label.add_css_class("notification-type")
        header_box.append(type_label)
        
        # Статус прочитанности
        is_unread = notification.get('archivedAt') is None
        status_label = Gtk.Label(label="●" if is_unread else "○")
        status_label.set_halign(Gtk.Align.END)
        status_label.add_css_class("unread" if is_unread else "read")
        header_box.append(status_label)
        
        # Время
        created_at = notification.get('createdAt')
        if created_at:
            relative_time = self._format_relative_time(created_at)
            absolute_time = self._format_absolute_time(created_at)
            time_str = f"{relative_time} ({absolute_time})"
            time_label = Gtk.Label(label=time_str)
            time_label.set_halign(Gtk.Align.END)
            time_label.add_css_class("time")
            header_box.append(time_label)
        
        # Содержимое в зависимости от типа
        if ntype == 'IssueNotification' or 'issue' in notification:
            issue = notification.get('issue', {})
            identifier = issue.get('identifier', '')
            title = issue.get('title', '')
            
            # Создаем контейнер для заголовка и ссылки
            content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            content_box.set_halign(Gtk.Align.START)
            
            # Заголовок задачи
            if title:
                title_label = Gtk.Label(label=title)
                title_label.set_halign(Gtk.Align.START)
                title_label.set_wrap(True)
                title_label.set_xalign(0)
                title_label.add_css_class("issue-title")
                content_box.append(title_label)
            
            # Ссылка на задачу
            if identifier:
                if self.workspace_url_key:
                    url = f"https://linear.app/{self.workspace_url_key}/issue/{identifier}"
                else:
                    # Fallback: используем только identifier, если workspace неизвестен
                    url = f"https://linear.app/issue/{identifier}"
                
                # Создаем кнопку-ссылку
                link_button = Gtk.LinkButton(uri=url, label=identifier)
                link_button.set_halign(Gtk.Align.START)
                link_button.add_css_class("issue-link")
                content_box.append(link_button)
            else:
                # Если нет identifier, показываем просто текст
                no_id_label = Gtk.Label(label="Идентификатор не найден")
                no_id_label.set_halign(Gtk.Align.START)
                content_box.append(no_id_label)
            
            box.append(content_box)
        elif ntype == 'ProjectNotification':
            project = notification.get('project', {})
            name = project.get('name', 'Project')
            content_label = Gtk.Label(label=f"Проект: {name}")
            content_label.set_halign(Gtk.Align.START)
            content_label.set_wrap(True)
            content_label.set_xalign(0)
            box.append(content_label)
        elif ntype == 'OauthClientApprovalNotification':
            # OAuth уведомления обрабатываются без деталей клиента
            content_label = Gtk.Label(label="OAuth клиент: запрос на одобрение")
            content_label.set_halign(Gtk.Align.START)
            content_label.set_wrap(True)
            content_label.set_xalign(0)
            box.append(content_label)
        elif ntype == 'TeamNotification':
            # TeamNotification не существует в API, обрабатываем как общий тип
            content_label = Gtk.Label(label="Уведомление команды")
            content_label.set_halign(Gtk.Align.START)
            content_label.set_wrap(True)
            content_label.set_xalign(0)
            box.append(content_label)
        else:
            content_label = Gtk.Label(label="Неизвестный тип уведомления")
            content_label.set_halign(Gtk.Align.START)
            content_label.set_wrap(True)
            content_label.set_xalign(0)
            box.append(content_label)
        
        return row
    
    def _format_relative_time(self, iso_string):
        """Форматировать время относительно текущего."""
        try:
            # Парсим ISO строку
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            total = int((now - dt).total_seconds())
            if total < 0:
                return "в будущем"
            if total < 60:
                return "только что"
            if total < 3600:
                return f"{total // 60} мин. назад"
            if total < 86400:
                return f"{total // 3600} ч. назад"
            return f"{total // 86400} дн. назад"
        except Exception:
            return iso_string
    
    def _format_absolute_time(self, iso_string):
        """Форматировать конкретное время в локальном часовом поясе."""
        try:
            # Парсим ISO строку (UTC)
            dt_utc = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            
            # Убеждаемся, что время в UTC
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            elif dt_utc.tzinfo != timezone.utc:
                # Конвертируем в UTC если нужно
                dt_utc = dt_utc.astimezone(timezone.utc)
            
            # Преобразуем в локальный часовой пояс
            dt_local = dt_utc.astimezone()
            
            # Форматируем: "14:30" или "14:30 28.11" если не сегодня
            now_local = datetime.now(dt_local.tzinfo)
            
            if dt_local.date() == now_local.date():
                # Сегодня - показываем только время
                return dt_local.strftime("%H:%M")
            else:
                # Не сегодня - показываем дату и время
                return dt_local.strftime("%H:%M %d.%m")
        except Exception as e:
            import sys
            print(f"Ошибка при форматировании времени: {e}", file=sys.stderr)
            return iso_string[:16]  # Fallback: первые 16 символов ISO строки
    
    def on_notebook_switch_page(self, notebook, page, page_num):
        """Обработчик переключения вкладок."""
        # Автоматически обновляем лог при переключении на вкладку лога
        if hasattr(self, 'log_page_index') and page_num == self.log_page_index:
            self.refresh_log()
    
    def refresh_log(self):
        """Обновить список логов."""
        # Очищаем список
        while True:
            row = self.log_list.get_row_at_index(0)
            if row is None:
                break
            self.log_list.remove(row)
        
        try:
            logs = self.linear_api.get_request_log()
            
            if not logs:
                # Показываем сообщение об отсутствии логов
                empty_row = Gtk.ListBoxRow()
                empty_label = Gtk.Label(label="Лог пуст")
                empty_label.set_margin_start(10)
                empty_label.set_margin_end(10)
                empty_label.set_margin_top(10)
                empty_label.set_margin_bottom(10)
                empty_row.set_child(empty_label)
                self.log_list.append(empty_row)
            else:
                for log_entry in logs:
                    row = self._create_log_row(log_entry)
                    self.log_list.append(row)
        except Exception as e:
            # Показываем ошибку
            error_row = Gtk.ListBoxRow()
            error_label = Gtk.Label(label=f"Ошибка загрузки лога: {e}")
            error_label.set_margin_start(10)
            error_label.set_margin_end(10)
            error_label.set_margin_top(10)
            error_label.set_margin_bottom(10)
            error_row.set_child(error_label)
            self.log_list.append(error_row)
    
    def _create_log_row(self, log_entry):
        """Создать строку для лога."""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10)
        row.set_child(box)
        
        # Заголовок с временем и статусом
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.append(header_box)
        
        timestamp = log_entry.get('timestamp', '')
        status_code = log_entry.get('status_code', 'N/A')
        error = log_entry.get('error')
        
        header_text = f"[{timestamp}] Status: {status_code}"
        if error:
            header_text += f" | Ошибка: {error}"
        
        header_label = Gtk.Label(label=header_text)
        header_label.set_halign(Gtk.Align.START)
        header_label.add_css_class("log-header")
        header_box.append(header_label)
        
        # Запрос
        request_label = Gtk.Label(label=f"Запрос:\n{log_entry.get('request', 'N/A')}")
        request_label.set_halign(Gtk.Align.START)
        request_label.set_wrap(True)
        request_label.set_xalign(0)
        request_label.set_selectable(True)
        request_label.add_css_class("log-request")
        box.append(request_label)
        
        # Ответ
        response = log_entry.get('response', 'N/A')
        if response:
            response_label = Gtk.Label(label=f"Ответ:\n{response}")
            response_label.set_halign(Gtk.Align.START)
            response_label.set_wrap(True)
            response_label.set_xalign(0)
            response_label.set_selectable(True)
            response_label.add_css_class("log-response")
            box.append(response_label)
        
        return row

