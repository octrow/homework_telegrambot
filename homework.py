import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": "OAuth " + PRACTICUM_TOKEN}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

last_error = None


class SendError(Exception):
    """Объявление нового класса для исключений."""

    pass


class Not200Response(Exception):
    """Объявление нового класса для исключений в get_api_answer."""

    pass


class EmptyAnswerAPI(Exception):
    """Объявление нового класса для исключений в check_response."""

    pass


def check_tokens():
    """Проверяем токены, если нет - возвращаем False."""
    logging.info("Проверка токенов начата")
    token_names = ("PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
    token_values = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    result = True
    for name, value in zip(token_names, token_values):
        if not value:
            logging.critical(f"Требуемый токен: {name} недоступен.")
            raise ValueError(f"Не найден токен: {name}")
    return result


def send_message(bot: telegram.bot.Bot, message):
    """Отправление сообщения в Telegram бот."""
    logging.info("Старт отправки сообщения.")
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug("Сообщение отправлено")
        return True
    except telegram.error.TelegramError as error:
        text = "Ошибка отправки сообщения telegram: "
        logging.error(text + str(error))
        return False


def get_api_answer(fromdate):
    """
    Получает ответ от API на запрос json домашних работы.
    Проверяет наличие ответа и ожидаемые ключи в API.
    """
    params_api = {
        "url": ENDPOINT,
        "headers": HEADERS,
        "params": {"from_date": fromdate},
    }
    logging.info(
        "Начало отправки запроса API. Параметры: "
        + "{url} {headers} {params}".format(**params_api)
    )
    try:
        response = requests.get(**params_api)
        if response.status_code != HTTPStatus.OK:
            error_message = "Ответ сервера не 200, a {}".format(
                response.status_code
            )
            raise Not200Response(error_message)
        logging.info("Запрос GET API выполнен.")
        return response.json()
    except ConnectionError as error:
        text = (
            "Ошибка соединения: "
            + str(error)
            + "{url} {headers} {params}".format(**params_api)
        )
        raise ConnectionError(text)
    except requests.RequestException as error:  # для прохождения тестов!
        text = (
            "Ошибка запроса: "
            + str(error)
            + "{url} {headers} {params}".format(**params_api)
        )
        logging.error(text)


def check_response(response):
    """Проверяем ответ API на соответствие."""
    logging.info("Начало проверки check_response ответа от API.")
    if not isinstance(response, dict):
        text = "Ответ API не является словарем"
        raise TypeError(text)  # требование тестов!
    if "homeworks" not in response:
        text = "Ответ API не содержит ключа 'homeworks'"
        raise EmptyAnswerAPI(text)
    response = response.get("homeworks")
    if not isinstance(response, list):
        text = "API под ключом `homeworks` приходят не в виде списка"
        raise TypeError(text)
    return response


def parse_status(homework):
    """Извлекает инфо о статусе homework и в случае успеха возвращает."""
    homework_status = homework.get("status")
    homework_name = homework.get("homework_name")
    if homework_status not in HOMEWORK_VERDICTS:
        text = "homework_status нет в HOMEWORK_VERDICTS"
        raise ValueError(text)
    if homework_name is None:  # для прохождения тестов!
        text = "homework_name отсутствует"
        raise KeyError(text)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        info_message = "Проблемы с токенами. Программа прервана."
        logging.critical(info_message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.info("Бот запущен.")
    current_report = {"name": None, "messages": None}
    prev_report = {"name": None, "messages": None}
    fromdate = 0
    while True:
        try:
            response = get_api_answer(fromdate)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logging.debug("В homeworks пустой список")
            else:
                last_homework = homeworks[0]
                fromdate = 0
                message = parse_status(last_homework)
                current_report = {
                    "name": last_homework.get("name"),
                    "messages": message,
                }
            if current_report != prev_report:
                logging.info("Обнаружено изменение в статусе homework.")
                if send_message(bot, message):
                    prev_report = current_report.copy()
                    fromdate = response.get("current_date")
            else:
                logging.debug("Нет изменений в статусе дз. Ждём 10 мин.")
        except EmptyAnswerAPI as error:
            text = "пустой ответ от API " + str(error)
            logging.error(text)
        except Exception as error:
            text = "Сбой в работе программы: " + str(error)
            logging.error(text)
            send_message(bot, text)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        format=(
            "%(asctime)s - %(name)s - %(funcName)s - %(lineno)d - "
            "%(levelname)s - %(message)s"
        ),
        level=logging.DEBUG,
        handlers=[
            logging.FileHandler(
                os.path.abspath(__file__ + ".log"), mode="a", encoding="UTF-8"
            ),
            logging.StreamHandler(stream=sys.stdout),
        ],
    )
    main()
