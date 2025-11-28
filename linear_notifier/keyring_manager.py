"""Управление хранением токена в GNOME Keyring."""

import sys
import keyring
import secretstorage
from secretstorage.exceptions import SecretServiceNotAvailableException

class KeyringManager:
    """Менеджер для работы с GNOME Keyring."""
    
    SERVICE_NAME = "linear-notifier"
    USERNAME = "api_token"
    
    def __init__(self):
        """Инициализация менеджера keyring."""
        # Убеждаемся, что используется libsecret backend
        self._collection = None
        self._use_secretstorage = False
        try:
            bus = secretstorage.dbus_init()
            collection = secretstorage.get_default_collection(bus)
            self._collection = collection
            self._use_secretstorage = True
        except (SecretServiceNotAvailableException, Exception):
            # Fallback на keyring, но предупреждаем
            self._use_secretstorage = False
            print("Предупреждение: SecretService недоступен, используется fallback keyring", file=sys.stderr)
    
    def get_token(self):
        """Получить токен из keyring."""
        try:
            if self._use_secretstorage and hasattr(self, '_collection') and self._collection:
                # Используем secretstorage напрямую
                items = self._collection.search_items({"service": self.SERVICE_NAME, "username": self.USERNAME})
                for item in items:
                    return item.get_secret().decode('utf-8')
                return None
            else:
                # Fallback на keyring
                return keyring.get_password(self.SERVICE_NAME, self.USERNAME)
        except Exception as e:
            print(f"Ошибка при получении токена: {e}", file=sys.stderr)
            return None
    
    def save_token(self, token):
        """Сохранить токен в keyring."""
        try:
            if self._use_secretstorage and hasattr(self, '_collection') and self._collection:
                # Удаляем старый токен если есть
                items = self._collection.search_items({"service": self.SERVICE_NAME, "username": self.USERNAME})
                for item in items:
                    item.delete()
                
                # Создаем новый
                attributes = {
                    "service": self.SERVICE_NAME,
                    "username": self.USERNAME
                }
                self._collection.create_item(
                    f"Linear API Token",
                    attributes,
                    token.encode('utf-8')
                )
            else:
                # Fallback на keyring
                keyring.set_password(self.SERVICE_NAME, self.USERNAME, token)
            return True
        except Exception as e:
            print(f"Ошибка при сохранении токена: {e}", file=sys.stderr)
            return False
    
    def delete_token(self):
        """Удалить токен из keyring."""
        try:
            if self._use_secretstorage and hasattr(self, '_collection') and self._collection:
                items = self._collection.search_items({"service": self.SERVICE_NAME, "username": self.USERNAME})
                for item in items:
                    item.delete()
            else:
                keyring.delete_password(self.SERVICE_NAME, self.USERNAME)
            return True
        except Exception as e:
            print(f"Ошибка при удалении токена: {e}", file=sys.stderr)
            return False

