import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from exceptions import Not200Response, EmptyAnswerAPI


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


def check_tokens():
    """Проверяем токены, если нет - возвращаем False."""
    logging.info("Проверка токенов начата")
    tokens = (
        ("PRACTICUM_TOKEN", PRACTICUM_TOKEN), 
        ("TELEGRAM_TOKEN", TELEGRAM_TOKEN),
        ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
    )
    missing_tokens = []
    for name, value in tokens:
        if not value:
            logging.critical(f"Требуемый токен: {name} недоступен.")
            missing_tokens.append(name)
    if missing_tokens:
        raise ValueError(f"Не найдены токены: {', '.join(missing_tokens)}")
    return True


def send_message(bot: telegram.bot.Bot, message):
    """Отправление сообщения в Telegram бот."""
    logging.info("Старт отправки сообщения: " + message)
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug("Сообщение отправлено, текст: " + message)
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
        logging.info("Запрос GET API выполнен.")
    except Exception as error:
        raise ConnectionError(
            "Ошибка: "
            + str(error)
            + "{url} {headers} {params}".format(**params_api)
        )
    else:
        if response.status_code != HTTPStatus.OK:
            error_message = "Ответ сервера не 200, a {}".format(
                response.status_code
            )
            raise Not200Response(error_message)
        return response.json()


def check_response(response):
    """Проверяем ответ API на соответствие."""
    logging.info("Начало проверки check_response ответа от API.")
    if not isinstance(response, dict):
        raise TypeError("Ответ API не является словарем")  # требование тестов!
    if "homeworks" not in response:
        raise EmptyAnswerAPI("Ответ API не содержит ключа 'homeworks'")
    response = response.get("homeworks")
    if not isinstance(response, list):
        raise TypeError("API под ключом `homeworks` приходят не в виде списка")
    return response


def parse_status(homework):
    """Извлекает инфо о статусе homework и в случае успеха возвращает."""
    homework_status = homework.get("status")
    homework_name = homework.get("homework_name")
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError("homework_status нет в HOMEWORK_VERDICTS")
    if homework_name is None:  # для прохождения тестов!
        raise KeyError("homework_name отсутствует")
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.info("Бот запущен.")
    current_report = {"name": None, "messages": None}
    prev_report = {"name": None, "messages": None}
    fromdate = 0
    while True:
        try:
            response = get_api_answer(fromdate)
            homeworks = check_response(response)
            if not homeworks:
                current_report = {
                    "name": None,
                    "messages": "В homeworks пустой список",
                }
            else:
                last_homework = homeworks[0]
                message = parse_status(last_homework)
                current_report = {
                    "name": last_homework.get("name"),
                    "messages": message,
                }
            if current_report != prev_report:
                if send_message(bot, current_report["messages"]):
                    prev_report = current_report.copy()
                    fromdate = response.get("current_date", int(time.time()))
            else:
                logging.debug("Нет изменений в статусе дз. Ждём 10 мин.")
        except EmptyAnswerAPI as error:
            logging.error("пустой ответ от API " + str(error))
        except Exception as error:
            current_report["messages"] = "Сбой в работе программы: " + str(
                error
            )
            logging.error(current_report["messages"])
            if current_report != prev_report:
                send_message(bot, current_report["messages"])
                prev_report = current_report.copy()
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
