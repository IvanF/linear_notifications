"""Клиент для работы с Linear API."""

import requests
from typing import List, Dict, Optional, Tuple


def is_transient_linear_error(exc: BaseException) -> bool:
    """Таймауты и сетевые сбои — не печатать полный traceback в консоль."""
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    msg = str(exc).lower()
    needles = (
        "превышено время",
        "timeout",
        "timed out",
        "подключения",
        "connection",
        "handshake",
        "ssl",
        "read timed out",
    )
    return any(n in msg for n in needles)


class LinearAPI:
    """Клиент для Linear GraphQL API."""
    
    ENDPOINT = "https://api.linear.app/graphql"
    
    def __init__(self, token: str):
        """Инициализация API клиента."""
        # Убираем лишние пробелы и переносы строк из токена
        self.token = token.strip() if token else ""
        if not self.token:
            raise ValueError("Токен не может быть пустым")
        
        # Для Personal API Key Linear использует формат без Bearer
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": self.token
        }
        # Лог запросов/ответов (последние 20)
        self.request_log: List[Dict] = []
        self.max_log_size = 20
        # Кэш для workspace urlKey
        self._workspace_url_key: Optional[str] = None
    
    def _log_if(self, request_data: Dict, log_request: bool) -> None:
        if log_request:
            self._add_to_log(request_data)
    
    def _query(self, query: str, variables: Optional[Dict] = None, log_request: bool = True) -> Dict:
        """Выполнить GraphQL запрос."""
        import json
        from datetime import datetime
        
        # Убираем лишние пробелы и переносы строк из запроса
        query = query.strip()
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        # Логируем запрос
        request_data = {
            "timestamp": datetime.now().isoformat(),
            "request": json.dumps(payload, indent=2, ensure_ascii=False),
            "response": None,
            "status_code": None,
            "error": None
        }
        
        try:
            response = requests.post(
                self.ENDPOINT,
                json=payload,
                headers=self.headers,
                timeout=30  # Увеличиваем таймаут для более медленных соединений
            )
            
            request_data["status_code"] = response.status_code
            
            # Проверяем статус код перед парсингом JSON
            if response.status_code == 400:
                # Пытаемся получить детали ошибки из ответа
                try:
                    error_data = response.json()
                    error_msg = error_data.get("errors", [{}])[0].get("message", response.text[:200]) if isinstance(error_data.get("errors"), list) else response.text[:200]
                    request_data["error"] = f"400 Bad Request: {error_msg}"
                    request_data["response"] = response.text[:1000]  # Первые 1000 символов
                    self._log_if(request_data, log_request)
                    raise Exception(f"400 Bad Request: {error_msg}")
                except (ValueError, KeyError, IndexError):
                    request_data["error"] = f"400 Bad Request: {response.text[:200]}"
                    request_data["response"] = response.text[:1000]
                    self._log_if(request_data, log_request)
                    raise Exception(f"400 Bad Request: {response.text[:200]}")
            elif response.status_code == 401:
                request_data["error"] = "401 Unauthorized - Неверный токен"
                request_data["response"] = response.text[:1000]
                self._log_if(request_data, log_request)
                raise Exception("401 Unauthorized - Неверный токен")
            elif response.status_code == 403:
                request_data["error"] = "403 Forbidden - Доступ запрещен"
                request_data["response"] = response.text[:1000]
                self._log_if(request_data, log_request)
                raise Exception("403 Forbidden - Доступ запрещен")
            
            response.raise_for_status()
            data = response.json()
            
            # Логируем успешный ответ
            request_data["response"] = json.dumps(data, indent=2, ensure_ascii=False)[:2000]  # Первые 2000 символов
            self._log_if(request_data, log_request)
        except requests.exceptions.Timeout:
            request_data["error"] = "Превышено время ожидания ответа от Linear API"
            self._log_if(request_data, log_request)
            raise Exception("Превышено время ожидания ответа от Linear API")
        except requests.exceptions.ConnectionError:
            request_data["error"] = "Ошибка подключения к Linear API. Проверьте интернет-соединение"
            self._log_if(request_data, log_request)
            raise Exception("Ошибка подключения к Linear API. Проверьте интернет-соединение")
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                request_data["status_code"] = status_code
                if status_code == 400:
                    try:
                        error_data = e.response.json()
                        error_msg = error_data.get("errors", [{}])[0].get("message", e.response.text[:200]) if isinstance(error_data.get("errors"), list) else e.response.text[:200]
                        request_data["error"] = f"400 Bad Request: {error_msg}"
                        request_data["response"] = e.response.text[:1000]
                        self._log_if(request_data, log_request)
                        raise Exception(f"400 Bad Request: {error_msg}")
                    except (ValueError, KeyError, IndexError):
                        request_data["error"] = f"400 Bad Request: {e.response.text[:200]}"
                        request_data["response"] = e.response.text[:1000]
                        self._log_if(request_data, log_request)
                        raise Exception(f"400 Bad Request: {e.response.text[:200]}")
                elif status_code == 401:
                    request_data["error"] = "401 Unauthorized - Неверный токен"
                    request_data["response"] = e.response.text[:1000] if hasattr(e.response, 'text') else ""
                    self._log_if(request_data, log_request)
                    raise Exception("401 Unauthorized - Неверный токен")
                elif status_code == 403:
                    request_data["error"] = "403 Forbidden - Доступ запрещен"
                    request_data["response"] = e.response.text[:1000] if hasattr(e.response, 'text') else ""
                    self._log_if(request_data, log_request)
                    raise Exception("403 Forbidden - Доступ запрещен")
            request_data["error"] = f"HTTP ошибка: {e}"
            self._log_if(request_data, log_request)
            raise Exception(f"HTTP ошибка: {e}")
        except requests.exceptions.RequestException as e:
            request_data["error"] = f"Ошибка запроса: {e}"
            self._log_if(request_data, log_request)
            raise Exception(f"Ошибка запроса: {e}")
        except ValueError as e:
            request_data["error"] = f"Ошибка парсинга ответа: {e}"
            self._log_if(request_data, log_request)
            raise Exception(f"Ошибка парсинга ответа: {e}")
        except Exception as e:
            # Логируем любые другие ошибки
            if "error" not in request_data:
                request_data["error"] = str(e)
            self._log_if(request_data, log_request)
            raise
        
        # Проверяем GraphQL ошибки
        if "errors" in data:
            errors = data["errors"]
            if isinstance(errors, list) and len(errors) > 0:
                error_msg = errors[0].get("message", str(errors[0]))
                request_data["error"] = f"GraphQL ошибка: {error_msg}"
                self._log_if(request_data, log_request)
                raise Exception(f"GraphQL ошибка: {error_msg}")
            request_data["error"] = f"GraphQL ошибка: {errors}"
            self._log_if(request_data, log_request)
            raise Exception(f"GraphQL ошибка: {errors}")
        
        return data.get("data", {})
    
    def _add_to_log(self, log_entry: Dict):
        """Добавить запись в лог запросов."""
        self.request_log.insert(0, log_entry)  # Добавляем в начало
        # Ограничиваем размер лога
        if len(self.request_log) > self.max_log_size:
            self.request_log = self.request_log[:self.max_log_size]
    
    def get_request_log(self) -> List[Dict]:
        """Получить лог запросов."""
        return self.request_log.copy()
    
    def ping(self) -> None:
        """Лёгкий запрос к API для проверки доступности (сеть, Linear)."""
        self._query("query { viewer { id } }", log_request=False)
    
    def validate_token(self) -> Tuple[bool, str]:
        """Проверить валидность токена.
        
        Returns:
            tuple[bool, str]: (успех, сообщение_об_ошибке)
        """
        # Используем компактный формат GraphQL запроса
        query = "query { viewer { id } }"
        try:
            data = self._query(query)
            # Проверяем наличие viewer и его id
            if "viewer" in data:
                viewer = data["viewer"]
                if viewer is None:
                    return False, "Токен не авторизован. API вернул null для viewer."
                elif isinstance(viewer, dict) and "id" in viewer and viewer["id"]:
                    return True, ""
                else:
                    return False, "Неверный формат ответа от API (viewer не содержит id)"
            else:
                return False, "API не вернул данные viewer"
        except Exception as e:
            error_msg = str(e)
            # Улучшаем сообщение об ошибке
            if "400" in error_msg or "Bad Request" in error_msg:
                # Ошибка уже содержит детали от сервера
                return False, error_msg
            elif "401" in error_msg or "Unauthorized" in error_msg:
                return False, "Токен не авторизован. Проверьте правильность токена."
            elif "403" in error_msg or "Forbidden" in error_msg:
                return False, "Доступ запрещен. Проверьте права токена."
            elif "Connection" in error_msg or "timeout" in error_msg.lower():
                return False, "Ошибка подключения. Проверьте интернет-соединение."
            else:
                return False, f"Ошибка валидации: {error_msg}"
    
    def get_workspace_url_key(self) -> Optional[str]:
        """Получить urlKey workspace (кэшируется)."""
        if self._workspace_url_key is not None:
            return self._workspace_url_key
        
        # Пробуем получить через organization (workspace - это organization)
        query = "query { viewer { organization { urlKey } } }"
        try:
            data = self._query(query)
            if "viewer" in data and data["viewer"]:
                organization = data["viewer"].get("organization")
                if organization and isinstance(organization, dict):
                    url_key = organization.get("urlKey")
                    if url_key:
                        self._workspace_url_key = url_key
                        return url_key
        except Exception as e:
            import sys
            # Не выводим ошибку, если это просто отсутствие поля - пробуем fallback
            error_str = str(e)
            if "400" not in error_str and "Cannot query" not in error_str:
                if is_transient_linear_error(e):
                    print(
                        f"Предупреждение: не удалось запросить workspace (organization): {e}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"Ошибка при получении workspace urlKey через organization: {e}",
                        file=sys.stderr,
                    )
        
        # Fallback: пробуем получить из первого уведомления через issue.team.organization
        # Только если есть уведомления
        try:
            query_issue = """
            query {
                notifications(first: 1) {
                    nodes {
                        ... on IssueNotification {
                            issue {
                                team {
                                    organization {
                                        urlKey
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
            data = self._query(query_issue)
            notifications = data.get("notifications", {})
            if notifications and isinstance(notifications, dict):
                nodes = notifications.get("nodes", [])
                if nodes and isinstance(nodes, list) and len(nodes) > 0:
                    notification = nodes[0]
                    issue = notification.get('issue', {})
                    if issue:
                        team = issue.get('team', {})
                        if team and isinstance(team, dict):
                            organization = team.get("organization", {})
                            if organization and isinstance(organization, dict):
                                url_key = organization.get("urlKey")
                                if url_key:
                                    self._workspace_url_key = url_key
                                    return url_key
        except Exception as e:
            import sys
            # Не выводим ошибку, если это просто отсутствие уведомлений
            error_str = str(e)
            if "400" not in error_str and "Cannot query" not in error_str:
                if is_transient_linear_error(e):
                    print(
                        f"Предупреждение: не удалось запросить workspace (issue→team): {e}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"Ошибка при получении workspace urlKey через issue.team.organization: {e}",
                        file=sys.stderr,
                    )
        
        return None
    
    def get_notifications(self, first: int = 25) -> List[Dict]:
        """Получить уведомления."""
        # Запрашиваем уведомления с issue
        # Используем IssueNotification - это основной тип для уведомлений о задачах
        # Другие типы (например, issueNewComment) могут не поддерживаться в GraphQL фрагментах,
        # но мы обработаем их в UI, проверяя наличие поля 'issue' в ответе
        query = """
        query($first: Int!) {
            notifications(first: $first) {
                nodes {
                    id
                    type
                    createdAt
                    archivedAt
                    ... on IssueNotification {
                        issue {
                            identifier
                            title
                        }
                    }
                }
            }
        }
        """
        
        variables = {"first": first}
        data = self._query(query, variables)
        
        # Безопасное извлечение уведомлений
        notifications = data.get("notifications", {})
        if notifications and isinstance(notifications, dict):
            nodes = notifications.get("nodes", [])
            result = nodes if isinstance(nodes, list) else []
            
            # Для уведомлений, которые не попали в IssueNotification фрагмент,
            # но могут содержать issue, пытаемся запросить issue отдельно
            # Это нужно для типов типа issueNewComment, которые не поддерживаются в фрагментах
            for notification in result:
                if notification.get('type') != 'IssueNotification' and 'issue' not in notification:
                    # Пробуем получить issue для этого уведомления отдельным запросом
                    # Но это может быть неэффективно, поэтому пока просто пропускаем
                    pass
            
            return result
        return []

