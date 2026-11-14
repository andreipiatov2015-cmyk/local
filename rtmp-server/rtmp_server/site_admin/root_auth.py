"""Подтверждение действия паролем пользователя, который запустил приложение.

RTMP-server сам всегда работает от root (см. debian/local/units и
sudoers-правило для беспарольного запуска ярлыка — `sudo /usr/bin/rtmp-server`,
debian/local/rtmp-server.sudoers) — поэтому подтверждение здесь не про
повышение прав в ОС (их и так достаточно), а про явную проверку "это точно
тот, кто сейчас сидит за этой машиной" перед чувствительными действиями:
просмотром списка пользователей сайта, сбросом пароля, изменением роли и т.п.

Раньше здесь всегда спрашивался пароль root. На практике это оказалось
неудобно: пароль root меняется по отдельной организационной политике (раз
в 3 месяца, без предупреждения), и его обладателя — не каждый сотрудник,
которому нужно подтверждать такие действия в программе. Теперь спрашиваем
пароль ТОГО пользователя ОС, который запустил приложение через sudo-ярлык
(sudo сам выставляет переменную окружения SUDO_USER) — это и есть "я
авторизован и у меня есть sudo", а не "мне сообщили пароль root". Если
SUDO_USER не задан (например, автозапуск через systemd при старте
графической сессии, не через sudo-ярлык) — откатываемся на root: другого
кандидата на "кто подтверждает" в этом случае нет.

Проверка пароля — через PAM (pam_authenticate), а НЕ вручную по хешу из
/etc/shadow. Воспроизведено вживую на Astra Linux: пароли там хранятся по
ГОСТ-алгоритму (хеш начинается с "$gos..."), который модуль crypt() из
стандартной библиотеки Python не понимает — сравнение всегда не совпадало
бы, каким бы верным ни был введённый пароль. PAM использует тот же стек
аутентификации, что и сам логин в систему, поэтому корректно работает с
любым алгоритмом, который реально настроен на машине (ГОСТ, обычный
sha512 и т.п.), без необходимости знать о конкретном формате хеша.

Модуль PAM (пакет python3-pam, он же "PyPAM" — компилируемое под ABI
системного Python расширение, см. debian/control) импортируется ЛЕНИВО,
внутри verify_confirming_password, а не на верху файла: так этот модуль
(и confirming_username/AdminAuthError) можно свободно импортировать и
тестировать в обычном dev-окружении, где python3-pam не установлен."""

from __future__ import annotations

import os

PAM_SERVICE = "login"


class AdminAuthError(Exception):
    pass


def confirming_username() -> str:
    """Чьим паролем подтверждаются чувствительные действия в этом запуске."""
    return os.environ.get("SUDO_USER") or "root"


def verify_confirming_password(password: str) -> bool:
    """True, если password подходит пользователю из confirming_username().

    Явно возвращает False (не бросает) для пустого пароля — это не
    "неверный пароль", а отсутствие попытки вообще, нет смысла даже
    дёргать PAM."""
    if not password:
        return False

    try:
        import PAM
    except ImportError as exc:
        raise AdminAuthError(
            "Модуль PAM (пакет python3-pam) не установлен — проверка пароля невозможна."
        ) from exc

    username = confirming_username()

    def _conv(_auth, query_list, _user_data):
        return [(password, 0) for _ in query_list]

    auth = PAM.pam()
    try:
        auth.start(PAM_SERVICE)
        auth.set_item(PAM.PAM_USER, username)
        auth.set_item(PAM.PAM_CONV, _conv)
    except Exception as exc:
        # Ошибка настройки PAM-сессии (например, нет такого сервиса) — это
        # не "неверный пароль", а поломка самой проверки, об этом надо
        # явно сообщить, а не молча отклонять попытку.
        raise AdminAuthError(
            f"Не удалось подготовить проверку пароля через PAM для пользователя {username}: {exc}"
        ) from exc

    try:
        auth.authenticate()
    except PAM.error:
        return False
    except Exception as exc:
        raise AdminAuthError(
            f"Не удалось проверить пароль через PAM для пользователя {username}: {exc}"
        ) from exc
    return True
