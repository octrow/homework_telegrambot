import datetime
import logging
import os
import sys
import time

# import pickle #v.2
import jsonschema
import requests
import telegram
# from dotenv import load_dotenv, set_key, find_dotenv #v.3
from dotenv import load_dotenv

# dotenv_file = find_dotenv() #v.3
# load_dotenv(dotenv_file, override=True) #v.3
load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": "OAuth " + PRACTICUM_TOKEN}

# FILENAME = "last_status.pkl" #v.2

DAYSNUM = 30

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}
SHEMA = {
    "type": "object",
    "properties": {
        "homeworks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "homework_name": {"type": "string"},
                },
            },
        },
        "current_date": {"type": "integer"},
    },
}

last_error = None


class SendError(Exception):
    """Объявление нового класса для исключений в handle_error."""

    pass

# def save_last_status(last_status): #v.2
#     """Сохранение последнего статуса используя pickle."""
#     with open(FILENAME, "wb") as file:
#         pickle.dump(last_status, file)

# def load_last_status(): #v.2
#     """Подгрузка последнего статуса используя pickle."""
#     try:
#         with open(FILENAME, "rb") as file:
#             last_status = pickle.load(file)
#     except FileNotFoundError:
#         last_status = None
#     return last_status

def handle_error(bot: telegram.bot.Bot, error, message):
    """Отправка сообщений и логирование о исключениях и ошибках."""
    global last_error
    logging.error(f"{message}: {error}")
    if error != last_error:
        try:
            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message.format(error),
            )
            logging.debug(f"Сообщение ошибки отправлено: {error}")
            last_error = error
        except Exception as send_error:
            logging.error(f"Ошибка отправки сообщения: {send_error}")
            raise SendError(
                f"Ошибка отправки сообщения: {send_error}"
            ) from send_error
    return last_error


def number_days(number):
    """Возвращает дату на number дней назад в unix time."""
    logging.info("Расчёт даты начался")
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(days=number)
    return int(start_time.timestamp())


def check_tokens():
    """Проверяем токены, если нет - возвращаем False."""
    logging.info("Проверка токенов начата")
    required_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if all(required_tokens):
        logging.info("Проверка токенов успешно закончена.")
        return True
    logging.critical("Необходимые токены отсутствуют.")
    return False


def send_message(bot: telegram.bot.Bot, message):
    """Отправление сообщения в Telegram бот."""
    try:
        logging.info("Старт отправки сообщения.")
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug("Сообщение отправлено")
    except telegram.error.TelegramError as error:
        handle_error(bot, error, "Ошибка отправки сообщения tg: {}")
    except Exception as error:
        handle_error(bot, error, "Доп ошибка отправки сообщения tg: {}")
    finally:
        logging.info("Функция send_message завершена")


def get_api_answer(days_num):
    """
    Получает ответ от API на запрос json домашних работы.
    Проверяет наличие ответа и ожидаемые ключи в API.
    """
    params_api = {
        "url": ENDPOINT,
        "headers": HEADERS,
        "params": {"from_date": days_num},
    }
    try:
        logging.info(
            "Начало отправки запроса API. Параметры: "
            + "{url} {headers} {params}".format(**params_api)
        )
        response = requests.get(**params_api)
        if response.status_code != 200:
            error_message = "Ответ сервера не 200, a {}".format(
                response.status_code
            )
            handle_error(bot, error_message, "Ошибка сервера")
            raise Exception(error_message)
        logging.info("Запрос GET API выполнен.")
        return response.json()
    except (
        requests.exceptions.HTTPError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.RequestException,
    ) as error:
        handle_error(bot, error, "Ошибка при запросе к эндпоинту API: {}")
    except Exception as error:
        handle_error(bot, error, "Доп ошибка в функции get_api_answer: {}")
    finally:
        logging.info("Функция get_api_answer завершена.")


def check_response(response):
    """Проверяем ответ API на соответствие."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    try:
        logging.info("Начало запасной проверки check_response ответа от API.")
        if not isinstance(response, dict) or not all(
            key in response for key in ("homeworks", "current_date")
        ):
            text = ("Ответ API не является словарем или не содержит "
                    "ожидаемых ключей: 'homeworks' или 'current_date'")
            logging.error(text, response)
            raise ValueError(text)
        if not isinstance(response["homeworks"], list):
            text = "API под ключом `homeworks` приходят не в виде списка"
            logging.error(text, response)
            raise TypeError(text)
        logging.info("Проверка schema check_response начата.")
        jsonschema.validate(instance=response, schema=SHEMA)
        logging.info("Проверка schema check_response закончена.")
        return True
    except (
        jsonschema.ValidationError,
        jsonschema.SchemaError,
    ) as error:
        handle_error(bot, error, "Ошибка jsonschema.exceptions json: {}")
    except Exception as error:
        handle_error(error, "Доп ошибка в функции check_response: {}")
    finally:
        logging.info("Функция check_response завершена.")


def parse_status(homework):
    """Извлекает инфо о статусе homework и в случае успеха возвращает."""
    try:
        logging.info("Начало parse_status.")
        if not isinstance(homework, dict) or not all(
            key in homework for key in ("status", "homework_name")
        ):
            text = ("homework не является словарем или не содержит ожидаемых "
                    "ключей: 'status' или 'homework_name'")
            logging.error(text, homework)
            raise ValueError(text)
        homework_status = homework.get("status")
        homework_name = homework.get("homework_name")
        if homework_status not in HOMEWORK_VERDICTS:
            text = "homework_status нет в HOMEWORK_VERDICTS"
            handle_error(bot, text, homework)
            raise ValueError(text)
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except Exception as error:
        handle_error(error, "Ошибка в функции parse_status: {}")
    finally:
        logging.info("Функция parse_status завершена.")


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        info_message = "Проблемы с токенами. Программа прервана."
        logging.critical(info_message)
        sys.exit(info_message)
    global bot
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.info("Бот запущен.")
    fromdate = number_days(DAYSNUM)
    logging.info("Расчёт даты закончился")
    # last_status = load_last_status() #v.2

    # global last_status #v.3
    # last_status = os.environ["LAST_STATUS"] #v.3
    last_status = None
    while True:
        try:
            response = get_api_answer(fromdate)
            check_response(response)
            last_homework = response.get("homeworks")[0]
            if last_status != last_homework.get("status"):
                logging.info("Обнаружено изменение статуса.")
                middle_status = last_homework.get("status")
                message = parse_status(last_homework)
                send_message(bot, message)
                # save_last_status(last_status) # v.2

                # os.environ["LAST_STATUS"] = middle_status # v.3
                # set_key(dotenv_file, "LAST_STATUS", os.environ["LAST_STATUS"]) #v.3
        except Exception as error:
            handle_error(bot, error, "Сбой в работе программы: {}")
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler(
                os.path.abspath("info.log"), mode="a", encoding="UTF-8"
            ),
            logging.StreamHandler(stream=sys.stdout),
        ],
    )
    main()
