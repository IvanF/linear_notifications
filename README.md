# Linear Notifier

*Documentation: [English](#english) · [Русский](#русский)*

---

## English

Native Linux desktop app for Ubuntu/GNOME (GTK 4) that connects to the **Linear API** and shows **system notifications** for new activity, plus a simple UI with a notification list and a request log.

### Requirements

- Python 3.10+
- Linux with GTK 4 (tested on GNOME)
- System packages for PyGObject, GTK 4, and libnotify:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 libnotify4
```

Optional (for future/experimental tray support via pystray on X11):

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1 python3-xlib
```

**Important:** PyGObject (`python3-gi`) and GTK 4 typelibs must be installed with **apt**, not pip. Without them, `pip`/`pipx` install will fail when importing `gi`.

### Installation

1. Clone the repository and `cd` into the project directory.
2. Install system dependencies (see above).
3. Install the app using one of the options below.

#### Option 1: pipx (good for end users)

```bash
sudo apt install pipx
pipx ensurepath

pipx install --system-site-packages .

linear-notifier-install-desktop
```

- `--system-site-packages` is required so the app can use the system `python3-gi`.
- After a pipx install, run **`linear-notifier-install-desktop`** to copy the `.desktop` file and icons into `~/.local/share/...` (pipx does not do this automatically).

#### Option 2: virtual environment (development)

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -e .
```

`--system-site-packages` is required for system PyGObject.

#### Option 3: `--break-system-packages` (not recommended)

```bash
pip install --user -e . --break-system-packages
```

#### Desktop file and icons

- Manual install: run **`linear-notifier-install-desktop`** (recommended after pipx).
- On **first launch**, `linear-notifier` runs **`ensure_desktop_file()`** in `main.py`: if the launcher is missing from `~/.local/share/applications/`, it and the icons are copied automatically (same effect as the install script).

After installation, the command is available as `linear-notifier` (with pipx, typically `~/.local/bin/linear-notifier`).

### Usage

```bash
linear-notifier
```

If needed:

```bash
export PATH="$HOME/.local/bin:$PATH"
linear-notifier
```

#### First run and token

1. If no **Linear API token** is saved yet, the **main window** opens on the **Settings** tab.
2. Paste your [Personal API Key](https://linear.app/settings/account/security) into the token field and click **Save token**. The token is stored in **GNOME Keyring** (via libsecret/keyring).
3. After validation, the app runs in the background; the notification list and API polling start automatically.

#### Main window (three tabs)

| Tab | Content |
|-----|---------|
| **Notifications** | Up to 25 latest items from Linear; for issues — type, time, title, link. Refreshes every minute while the window is open; also when new items appear in the background. |
| **Request log** | Recent GraphQL requests and responses (debugging). |
| **Settings** | **Linear API token** field and save button; **interface language** (Russian, English, Chinese, Korean, Hindi, Spanish) and a separate save button. Changing language **restarts** the app (`~/.config/linear-notifier/config.json`). |

At the bottom: Linear connectivity indicator (colored dot) and **version** number.

#### Background behaviour and notifications

- New **unread** notifications are polled about **once per minute** (HTTP polling to Linear API, not server push — delay up to one poll interval).
- A separate **lightweight API reachability check** runs more often; on connection loss a desktop notification is shown and the window indicator updates.
- System notification text includes **event type** and **issue identifier** where applicable. Notification icon: cloud (bundled or from the theme).

#### Limitations

- **System tray** icon is **disabled** in this version (pystray vs GTK 4); open the app from the menu or from a notification.
- Linear items not returned on the first API “page” may not appear in the list until a later fetch.

### Getting a Linear API token

1. In Linear: **Settings** → **Security & access** (or your workspace’s API key section).
2. Create a **Personal API Key** and copy it.
3. Paste it under **Settings** in the app and save.

### Uninstall

#### pipx

```bash
pipx uninstall linear-notifier
```

Optionally clean up manually:

```bash
rm ~/.local/share/applications/com.example.LinearNotifier.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/com.example.LinearNotifier*.svg
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor
```

Remove the token in **Passwords and Keys** (Seahorse). Config file: `~/.config/linear-notifier/config.json`.

#### venv

```bash
rm -rf venv
```

#### pip with `--break-system-packages`

```bash
pip uninstall linear-notifier
```

### Features (summary)

- Secure token storage (keyring / Secret Service).
- UI in 6 languages; language config under `~/.config/linear-notifier/`.
- Desktop notifications via libnotify; extra notification when the API is unreachable.
- Main window: notifications, request log, settings.

### Project layout

```
linear_notifications/
├── pyproject.toml
├── README.md
└── linear_notifier/
    ├── __init__.py
    ├── main.py              # Entry point, ensure_desktop_file, language load
    ├── app.py               # Gtk.Application, polling, notifications
    ├── main_window.py       # Window: notifications / log / settings tabs
    ├── linear_api.py        # Linear GraphQL API client
    ├── keyring_manager.py   # Token in GNOME Keyring
    ├── config_store.py      # ~/.config/linear-notifier/config.json
    ├── i18n.py              # UI strings and notification type labels
    ├── settings_window.py   # Legacy standalone window (optional, .ui)
    ├── install_desktop.py   # Installs .desktop and icons
    └── data/
        ├── com.example.LinearNotifier.desktop
        ├── ui/                # settings.ui, main.ui (optional, e.g. Cambalache)
        └── icons/hicolor/.../  # com.example.LinearNotifier.svg, …notify.svg
```

### Development

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -e .
linear-notifier
```

Code changes are picked up without reinstall (editable). Add new UI strings to every language block in `i18n.py`.

Before committing:

```bash
python3 -m compileall -q linear_notifier
```

---

## Русский

Нативное Linux desktop-приложение для Ubuntu/GNOME (GTK 4), которое подключается к **Linear API** и показывает **системные уведомления** о новых событиях, плюс простой интерфейс со списком уведомлений и логом запросов.

### Требования

- Python 3.10+
- Linux с GTK 4 (протестировано в среде GNOME)
- Системные пакеты для PyGObject, GTK 4 и libnotify:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 libnotify4
```

Опционально (для будущей/экспериментальной поддержки трея через pystray на X11):

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1 python3-xlib
```

**Важно:** PyGObject (`python3-gi`) и typelibs GTK 4 должны быть установлены через **apt**, не через pip. Без них установка пакета через pip/pipx завершится ошибкой при импорте `gi`.

### Установка

1. Клонируйте репозиторий и перейдите в каталог проекта.

2. Установите системные зависимости (см. выше).

3. Установите приложение одним из способов ниже.

#### Вариант 1: pipx (удобно для конечного пользователя)

```bash
sudo apt install pipx
pipx ensurepath

pipx install --system-site-packages .

linear-notifier-install-desktop
```

- Флаг `--system-site-packages` нужен, чтобы приложение видело системный `python3-gi`.
- После установки через pipx выполните **`linear-notifier-install-desktop`**, чтобы скопировать `.desktop` и иконки в `~/.local/share/...` (pipx это не делает сам).

#### Вариант 2: виртуальное окружение (разработка)

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -e .
```

Флаг `--system-site-packages` обязателен для доступа к системному PyGObject.

#### Вариант 3: `--break-system-packages` (не рекомендуется)

```bash
pip install --user -e . --break-system-packages
```

#### Desktop-файл и иконки

- Явная установка: команда **`linear-notifier-install-desktop`** (рекомендуется после pipx).
- При **первом запуске** `linear-notifier` вызывается **`ensure_desktop_file()`** в `main.py`: при отсутствии файла в `~/.local/share/applications/` он и иконки копируются автоматически (аналогично скрипту установки).

После установки команда доступна как `linear-notifier` (pipx: обычно `~/.local/bin/linear-notifier`).

### Использование

```bash
linear-notifier
```

При необходимости:

```bash
export PATH="$HOME/.local/bin:$PATH"
linear-notifier
```

#### Первый запуск и токен

1. Если **Linear API token** ещё не сохранён, откроется **главное окно** сразу на вкладке **«Настройки»**.
2. Вставьте [Personal API Key](https://linear.app/settings/account/security) в поле токена и нажмите **«Сохранить токен»**. Токен сохраняется в **GNOME Keyring** (через libsecret/keyring).
3. После успешной проверки токена приложение работает в фоне; список уведомлений и опрос API активируются автоматически.

#### Главное окно (три вкладки)

| Вкладка | Содержимое |
|--------|------------|
| **Уведомления** | До 25 последних записей из Linear; для задач — тип, время, заголовок, ссылка на issue. Обновление раз в минуту, пока окно открыто; также при появлении новых событий в фоне. |
| **Лог запросов** | Последние GraphQL-запросы и ответы (отладка). |
| **Настройки** | Поле **Linear API token** и кнопка сохранения; выбор **языка интерфейса** (русский, английский, китайский, корейский, хинди, испанский) и отдельная кнопка сохранения языка. При смене языка приложение **перезапускается** (`~/.config/linear-notifier/config.json`). |

Внизу окна: индикатор связи с Linear (цветной кружок) и номер **версии**.

#### Фоновая работа и уведомления

- Новые **непрочитанные** уведомления опрашиваются примерно **раз в минуту** (это polling к Linear API, не push с сервера Linear — возможна задержка до интервала опроса).
- Отдельная **лёгкая проверка доступности API** выполняется чаще; при потере связи показывается desktop-уведомление, индикатор в окне меняется.
- Текст системных уведомлений включает **тип события** и **идентификатор задачи** (где применимо). Иконка уведомления — облако (своя или из темы).

#### Ограничения

- Иконка в **системном трее** в текущей версии **отключена** (несовместимость pystray с GTK 4); открывайте приложение из меню или после уведомления.
- Уведомления Linear, не попавшие в первую «страницу» ответа API, могут не отразиться в списке до следующих запросов.

### Получение Linear API токена

1. Linear → **Settings** → **Security & access** (или аналог для API keys).
2. Создайте **Personal API Key** и скопируйте его.
3. Вставьте в **Настройки** приложения и сохраните.

### Удаление

#### pipx

```bash
pipx uninstall linear-notifier
```

Вручную при желании:

```bash
rm ~/.local/share/applications/com.example.LinearNotifier.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/com.example.LinearNotifier*.svg
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor
```

Токен в связке ключей удалите через **Пароли и ключи** (Seahorse). Файл настроек: `~/.config/linear-notifier/config.json`.

#### venv

```bash
rm -rf venv
```

#### pip с `--break-system-packages`

```bash
pip uninstall linear-notifier
```

### Особенности (кратко)

- Безопасное хранение токена (keyring / Secret Service).
- Локализация UI на 6 языков, конфиг языка в `~/.config/linear-notifier/`.
- Desktop-уведомления через libnotify; отдельное уведомление при обрыве связи с API.
- Главное окно: список уведомлений, лог запросов, настройки.

### Структура проекта

```
linear_notifications/
├── pyproject.toml
├── README.md
└── linear_notifier/
    ├── __init__.py
    ├── main.py              # Точка входа, ensure_desktop_file, загрузка языка
    ├── app.py               # Gtk.Application, polling, уведомления
    ├── main_window.py       # Окно: вкладки уведомления / лог / настройки
    ├── linear_api.py        # Клиент Linear GraphQL API
    ├── keyring_manager.py   # Токен в GNOME Keyring
    ├── config_store.py      # ~/.config/linear-notifier/config.json
    ├── i18n.py              # Строки интерфейса и подписи типов уведомлений
    ├── settings_window.py   # Устаревшее отдельное окно (опционально, UI из .ui)
    ├── install_desktop.py   # Скрипт установки .desktop и иконок
    └── data/
        ├── com.example.LinearNotifier.desktop
        ├── ui/                # settings.ui, main.ui (опционально для Cambalache)
        └── icons/hicolor/.../  # com.example.LinearNotifier.svg, …notify.svg
```

### Разработка

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -e .
linear-notifier
```

Изменения в коде подхватываются без переустановки (editable). Новые строки интерфейса добавляйте во все языковые блоки в `i18n.py`.

Перед коммитом имеет смысл проверить:

```bash
python3 -m compileall -q linear_notifier
```
