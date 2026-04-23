"""Главное окно приложения с отображением уведомлений."""

import sys
from datetime import datetime, timezone
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, GLib, GObject

from linear_notifier import __version__
from linear_notifier.config_store import save_config
from linear_notifier.i18n import (
    LANG_CODES,
    LANG_NAMES_UI,
    get_language,
    restart_application,
    translate_notification_type,
    tr,
)
from linear_notifier.keyring_manager import KeyringManager
from linear_notifier.linear_api import LinearAPI, is_transient_linear_error

# Ширина полей на вкладке «Настройки» (не растягиваются при ресайзе окна)
_SETTINGS_FORM_WIDTH = 480


class MainWindow(Gtk.Window):
    """Главное окно с уведомлениями и вкладкой настроек."""

    __gsignals__ = {
        "token-saved": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, app, linear_api: Optional[LinearAPI], ui_path):
        super().__init__(application=app, title=tr("app_title"))
        self._app = app
        self.linear_api = linear_api
        self.ui_path = ui_path
        self.workspace_url_key = None
        self._keyring = KeyringManager()
        self._notebook = None
        self.settings_page_index = 0
        self.log_page_index = 0

        self.set_default_size(600, 520)

        self._create_ui()

        if self.linear_api:
            self._load_workspace_url_key()

    def set_linear_api(self, api: LinearAPI) -> None:
        """После сохранения токена подключить API и обновить списки."""
        self.linear_api = api
        self.workspace_url_key = None
        self._load_workspace_url_key()
        self.refresh_notifications()
        self.refresh_log()
        self._sync_token_field()

    def focus_settings_tab(self) -> None:
        if self._notebook is not None:
            self._notebook.set_current_page(self.settings_page_index)

    def _sync_token_field(self) -> None:
        if not hasattr(self, "_token_entry") or self._token_entry is None:
            return
        t = self._keyring.get_token()
        if t:
            self._token_entry.set_text(t)

    def _create_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        notebook = Gtk.Notebook()
        notebook.set_vexpand(True)
        notebook.set_hexpand(True)
        self._notebook = notebook
        root.append(notebook)

        # --- Уведомления ---
        notifications_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=10,
        )
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        notifications_box.append(scrolled)
        self.notifications_list = Gtk.ListBox()
        self.notifications_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.notifications_list)
        notifications_tab_lbl = Gtk.Label(label=tr("tab_notifications"))
        notebook.append_page(notifications_box, notifications_tab_lbl)

        # --- Лог ---
        log_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=10,
        )
        log_scrolled = Gtk.ScrolledWindow()
        log_scrolled.set_vexpand(True)
        log_box.append(log_scrolled)
        self.log_list = Gtk.ListBox()
        self.log_list.set_selection_mode(Gtk.SelectionMode.NONE)
        log_scrolled.set_child(self.log_list)
        log_label = Gtk.Label(label=tr("tab_request_log"))
        self.log_page_index = notebook.append_page(log_box, log_label)

        # --- Настройки ---
        settings_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_start=16,
            margin_end=16,
            margin_top=16,
            margin_bottom=16,
        )
        settings_box.set_hexpand(False)
        settings_box.set_size_request(_SETTINGS_FORM_WIDTH, -1)
        # Иначе ScrolledWindow растянет колонку на всю ширину вкладки
        settings_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        settings_row.set_hexpand(True)
        settings_row.append(settings_box)
        settings_row_spacer = Gtk.Box()
        settings_row_spacer.set_hexpand(True)
        settings_row.append(settings_row_spacer)
        settings_scroll = Gtk.ScrolledWindow()
        settings_scroll.set_vexpand(True)
        settings_scroll.set_child(settings_row)
        settings_tab_lbl = Gtk.Label(label=tr("tab_settings"))
        self.settings_page_index = notebook.append_page(settings_scroll, settings_tab_lbl)

        tok_title = Gtk.Label(label=tr("token_label"))
        tok_title.set_halign(Gtk.Align.START)
        settings_box.append(tok_title)

        self._token_entry = Gtk.Entry()
        self._token_entry.set_placeholder_text(tr("token_placeholder"))
        self._token_entry.set_visibility(False)
        self._token_entry.set_hexpand(False)
        self._token_entry.set_size_request(_SETTINGS_FORM_WIDTH, -1)
        settings_box.append(self._token_entry)

        self._token_status = Gtk.Label(label="")
        self._token_status.set_halign(Gtk.Align.START)
        self._token_status.set_wrap(True)
        self._token_status.set_hexpand(False)
        self._token_status.set_size_request(_SETTINGS_FORM_WIDTH, -1)
        settings_box.append(self._token_status)

        save_tok_btn = Gtk.Button(label=tr("btn_save_token"))
        save_tok_btn.set_hexpand(False)
        save_tok_btn.set_halign(Gtk.Align.START)
        save_tok_btn.connect("clicked", self._on_save_token_clicked)
        settings_box.append(save_tok_btn)

        lang_title = Gtk.Label(label=tr("language_label"))
        lang_title.set_halign(Gtk.Align.START)
        lang_title.set_margin_top(12)
        settings_box.append(lang_title)

        self._lang_combo = Gtk.ComboBoxText()
        for code in LANG_CODES:
            self._lang_combo.append(code, LANG_NAMES_UI[code])
        cur = get_language()
        if cur in LANG_CODES:
            self._lang_combo.set_active_id(cur)
        else:
            self._lang_combo.set_active(0)
        self._lang_combo.set_hexpand(False)
        self._lang_combo.set_size_request(_SETTINGS_FORM_WIDTH, -1)
        settings_box.append(self._lang_combo)

        self._lang_status = Gtk.Label(label="")
        self._lang_status.set_halign(Gtk.Align.START)
        self._lang_status.set_wrap(True)
        self._lang_status.set_hexpand(False)
        self._lang_status.set_size_request(_SETTINGS_FORM_WIDTH, -1)
        settings_box.append(self._lang_status)

        save_lang_btn = Gtk.Button(label=tr("btn_save_language"))
        save_lang_btn.set_hexpand(False)
        save_lang_btn.set_halign(Gtk.Align.START)
        save_lang_btn.connect("clicked", self._on_save_language_clicked)
        settings_box.append(save_lang_btn)

        self._sync_token_field()

        notebook.connect("switch-page", self.on_notebook_switch_page)

        self._auto_refresh_source_id = None
        self.connect("destroy", self._on_destroy)
        self.connect("notify::visible", self._on_visible_changed)

        self._start_auto_refresh()

        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer_box.set_margin_start(12)
        footer_box.set_margin_end(12)
        footer_box.set_margin_top(4)
        footer_box.set_margin_bottom(8)
        footer_left = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._status_dot = Gtk.Label()
        self._status_dot.set_markup('<span foreground="#9a9a9a">●</span>')
        self._status_dot.set_tooltip_text(tr("tooltip_conn_unknown"))
        self._status_dot_click = Gtk.GestureClick.new()
        self._status_dot_click.connect("released", self._on_status_dot_released)
        self._status_dot.add_controller(self._status_dot_click)
        footer_left.append(self._status_dot)
        footer_box.append(footer_left)
        self._version_label = Gtk.Label(label=tr("footer_version", version=__version__))
        self._version_label.set_halign(Gtk.Align.END)
        self._version_label.set_hexpand(True)
        self._version_label.set_opacity(0.65)
        footer_box.append(self._version_label)
        root.append(footer_box)

        connected = getattr(self._app, "_linear_connected", None)
        self.set_linear_reachable(connected)

    def _on_save_token_clicked(self, _btn) -> None:
        token = self._token_entry.get_text().strip()
        if not token:
            self._token_status.set_text(tr("token_err_empty"))
            return
        self._token_status.set_text(tr("token_validating"))
        api = LinearAPI(token)
        ok, err = api.validate_token()
        if not ok:
            self._token_status.set_text(tr("token_err_invalid", msg=err or ""))
            return
        if not self._keyring.save_token(token):
            self._token_status.set_text(tr("token_save_failed"))
            return
        self._token_status.set_text(tr("token_saved"))
        self.emit("token-saved", token)

    def _on_save_language_clicked(self, _btn) -> None:
        code = self._lang_combo.get_active_id()
        if not code:
            return
        if code == get_language():
            self._lang_status.set_text("")
            return
        save_config({"language": code})
        self._lang_status.set_text(tr("lang_saved_restart"))

        def _idle_restart():
            restart_application()
            return False

        GLib.idle_add(_idle_restart)

    def _load_workspace_url_key(self) -> None:
        if not self.linear_api:
            return

        def load_in_background():
            try:
                self.workspace_url_key = self.linear_api.get_workspace_url_key()
            except Exception as e:
                print(f"Предупреждение: workspace urlKey: {e}", file=sys.stderr)

        import threading

        threading.Thread(target=load_in_background, daemon=True).start()

    def _start_auto_refresh(self) -> None:
        if self._auto_refresh_source_id is not None:
            GLib.source_remove(self._auto_refresh_source_id)
            self._auto_refresh_source_id = None
        if self.linear_api:
            self.refresh_notifications()
        self._auto_refresh_source_id = GLib.timeout_add_seconds(60, self._auto_refresh_callback)

    def _auto_refresh_callback(self) -> bool:
        if self.is_visible() and self.linear_api:
            self.refresh_notifications()
        return True

    def _on_visible_changed(self, _obj, _pspec) -> None:
        if self.get_visible() and self.linear_api:
            self.refresh_notifications()

    def _on_destroy(self, _widget) -> None:
        if self._auto_refresh_source_id is not None:
            GLib.source_remove(self._auto_refresh_source_id)
            self._auto_refresh_source_id = None

    def set_linear_reachable(self, ok: Optional[bool]) -> None:
        if not hasattr(self, "_status_dot") or self._status_dot is None:
            return
        if ok is True:
            self._status_dot.set_markup('<span foreground="#2ec27e">●</span>')
            self._status_dot.set_tooltip_text(tr("tooltip_conn_ok"))
            self._status_dot.set_cursor(None)
        elif ok is False:
            self._status_dot.set_markup('<span foreground="#e01b24">●</span>')
            self._status_dot.set_tooltip_text(tr("tooltip_conn_bad"))
            try:
                ptr = Gdk.Cursor.new_from_name("pointer", None)
                if ptr:
                    self._status_dot.set_cursor(ptr)
            except Exception:
                pass
        else:
            self._status_dot.set_markup('<span foreground="#9a9a9a">●</span>')
            self._status_dot.set_tooltip_text(tr("tooltip_conn_unknown"))
            self._status_dot.set_cursor(None)

    def _on_status_dot_released(self, _gesture, n_press: int, _x: float, _y: float) -> None:
        if n_press != 1:
            return
        if getattr(self._app, "_linear_connected", None) is False and hasattr(
            self._app, "force_reconnect"
        ):
            self._app.force_reconnect()

    def _on_reconnect_clicked(self, _btn) -> None:
        if hasattr(self._app, "force_reconnect"):
            self._app.force_reconnect()

    def refresh_notifications(self) -> None:
        if not hasattr(self, "notifications_list") or self.notifications_list is None:
            return

        if not self.linear_api:
            while True:
                row = self.notifications_list.get_row_at_index(0)
                if row is None:
                    break
                self.notifications_list.remove(row)
            row = Gtk.ListBoxRow()
            lab = Gtk.Label(label=tr("no_token_hint"))
            lab.set_margin_start(10)
            lab.set_margin_end(10)
            lab.set_margin_top(10)
            lab.set_margin_bottom(10)
            row.set_child(lab)
            self.notifications_list.append(row)
            return

        if self.workspace_url_key is None:
            try:
                self.workspace_url_key = self.linear_api.get_workspace_url_key()
            except Exception as e:
                print(f"Предупреждение: workspace urlKey: {e}", file=sys.stderr)

        while True:
            row = self.notifications_list.get_row_at_index(0)
            if row is None:
                break
            self.notifications_list.remove(row)

        try:
            notifications = self.linear_api.get_notifications(first=25)
            if not notifications:
                empty_row = Gtk.ListBoxRow()
                empty_label = Gtk.Label(label=tr("empty_notifications"))
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
            if is_transient_linear_error(e):
                print(
                    f"Предупреждение: временная ошибка сети при загрузке уведомлений: {e}",
                    file=sys.stderr,
                )
            else:
                import traceback
                print(f"Ошибка при загрузке уведомлений: {e}", file=sys.stderr)
                print(f"Детали: {traceback.format_exc()}", file=sys.stderr)
            error_row = Gtk.ListBoxRow()
            err_text = (
                tr("load_error_network")
                if is_transient_linear_error(e)
                else tr("load_error", err=str(e))
            )
            err_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            err_box.set_margin_start(10)
            err_box.set_margin_end(10)
            err_box.set_margin_top(10)
            err_box.set_margin_bottom(10)
            error_label = Gtk.Label(label=err_text)
            error_label.set_wrap(True)
            error_label.set_xalign(0)
            err_box.append(error_label)
            reconnect_btn = Gtk.Button(label=tr("btn_reconnect"))
            reconnect_btn.set_halign(Gtk.Align.START)
            reconnect_btn.connect("clicked", self._on_reconnect_clicked)
            err_box.append(reconnect_btn)
            error_row.set_child(err_box)
            self.notifications_list.append(error_row)

    def _create_notification_row(self, notification):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=5,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=10,
        )
        row.set_child(box)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.append(header_box)

        ntype = notification.get("type", "Unknown")
        type_label = Gtk.Label(label=translate_notification_type(ntype))
        type_label.set_halign(Gtk.Align.START)
        type_label.add_css_class("notification-type")
        header_box.append(type_label)

        is_unread = notification.get("archivedAt") is None
        status_label = Gtk.Label(label="●" if is_unread else "○")
        status_label.set_halign(Gtk.Align.END)
        status_label.add_css_class("unread" if is_unread else "read")
        header_box.append(status_label)

        created_at = notification.get("createdAt")
        if created_at:
            relative_time = self._format_relative_time(created_at)
            absolute_time = self._format_absolute_time(created_at)
            time_str = f"{relative_time} ({absolute_time})"
            time_label = Gtk.Label(label=time_str)
            time_label.set_halign(Gtk.Align.END)
            time_label.add_css_class("time")
            header_box.append(time_label)

        if ntype == "IssueNotification" or "issue" in notification:
            issue = notification.get("issue", {})
            identifier = issue.get("identifier", "")
            title = issue.get("title", "")
            content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            content_box.set_halign(Gtk.Align.START)
            if title:
                title_label = Gtk.Label(label=title)
                title_label.set_halign(Gtk.Align.START)
                title_label.set_wrap(True)
                title_label.set_xalign(0)
                title_label.add_css_class("issue-title")
                content_box.append(title_label)
            if identifier:
                if self.workspace_url_key:
                    url = f"https://linear.app/{self.workspace_url_key}/issue/{identifier}"
                else:
                    url = f"https://linear.app/issue/{identifier}"
                link_button = Gtk.LinkButton(uri=url, label=identifier)
                link_button.set_halign(Gtk.Align.START)
                link_button.add_css_class("issue-link")
                content_box.append(link_button)
            else:
                no_id_label = Gtk.Label(label=tr("id_not_found"))
                no_id_label.set_halign(Gtk.Align.START)
                content_box.append(no_id_label)
            box.append(content_box)
        elif ntype == "ProjectNotification":
            project = notification.get("project", {})
            name = project.get("name", tr("project_fallback"))
            content_label = Gtk.Label(label=tr("project_prefix", name=name))
            content_label.set_halign(Gtk.Align.START)
            content_label.set_wrap(True)
            content_label.set_xalign(0)
            box.append(content_label)
        elif ntype == "OauthClientApprovalNotification":
            content_label = Gtk.Label(label=tr("oauth_client"))
            content_label.set_halign(Gtk.Align.START)
            content_label.set_wrap(True)
            content_label.set_xalign(0)
            box.append(content_label)
        elif ntype == "TeamNotification":
            content_label = Gtk.Label(label=tr("team_notif"))
            content_label.set_halign(Gtk.Align.START)
            content_label.set_wrap(True)
            content_label.set_xalign(0)
            box.append(content_label)
        else:
            content_label = Gtk.Label(label=tr("unknown_type"))
            content_label.set_halign(Gtk.Align.START)
            content_label.set_wrap(True)
            content_label.set_xalign(0)
            box.append(content_label)

        return row

    def _format_relative_time(self, iso_string):
        try:
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            total = int((now - dt).total_seconds())
            if total < 0:
                return tr("time_future")
            if total < 60:
                return tr("time_just_now")
            if total < 3600:
                return tr("time_minutes", n=total // 60)
            if total < 86400:
                return tr("time_hours", n=total // 3600)
            return tr("time_days", n=total // 86400)
        except Exception:
            return iso_string

    def _format_absolute_time(self, iso_string):
        try:
            dt_utc = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            elif dt_utc.tzinfo != timezone.utc:
                dt_utc = dt_utc.astimezone(timezone.utc)
            dt_local = dt_utc.astimezone()
            now_local = datetime.now(dt_local.tzinfo)
            if dt_local.date() == now_local.date():
                return dt_local.strftime("%H:%M")
            return dt_local.strftime("%H:%M %d.%m")
        except Exception as e:
            print(f"Ошибка при форматировании времени: {e}", file=sys.stderr)
            return iso_string[:16]

    def on_notebook_switch_page(self, notebook, page, page_num):
        if hasattr(self, "log_page_index") and page_num == self.log_page_index:
            self.refresh_log()

    def refresh_log(self) -> None:
        while True:
            row = self.log_list.get_row_at_index(0)
            if row is None:
                break
            self.log_list.remove(row)
        if not self.linear_api:
            return
        try:
            logs = self.linear_api.get_request_log()
            if not logs:
                empty_row = Gtk.ListBoxRow()
                empty_label = Gtk.Label(label=tr("log_empty"))
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
            error_row = Gtk.ListBoxRow()
            error_label = Gtk.Label(label=tr("log_load_error", err=str(e)))
            error_label.set_margin_start(10)
            error_label.set_margin_end(10)
            error_label.set_margin_top(10)
            error_label.set_margin_bottom(10)
            error_row.set_child(error_label)
            self.log_list.append(error_row)

    def _create_log_row(self, log_entry):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=5,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=10,
        )
        row.set_child(box)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.append(header_box)
        timestamp = log_entry.get("timestamp", "")
        status_code = log_entry.get("status_code", "N/A")
        error = log_entry.get("error")
        header_text = tr("log_status", ts=timestamp, code=status_code)
        if error:
            header_text += tr("log_err_part", err=error)
        header_label = Gtk.Label(label=header_text)
        header_label.set_halign(Gtk.Align.START)
        header_label.add_css_class("log-header")
        header_box.append(header_label)
        request_label = Gtk.Label(label=tr("log_request", body=log_entry.get("request", "N/A")))
        request_label.set_halign(Gtk.Align.START)
        request_label.set_wrap(True)
        request_label.set_xalign(0)
        request_label.set_selectable(True)
        request_label.add_css_class("log-request")
        box.append(request_label)
        response = log_entry.get("response", "N/A")
        if response:
            response_label = Gtk.Label(label=tr("log_response", body=response))
            response_label.set_halign(Gtk.Align.START)
            response_label.set_wrap(True)
            response_label.set_xalign(0)
            response_label.set_selectable(True)
            response_label.add_css_class("log-response")
            box.append(response_label)
        return row
