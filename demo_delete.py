import datetime
import json
import logging
import os

import requests
from dotenv import load_dotenv
from jsonschema import validate
from telegram import Bot, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, Updater

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


def number_days(number):
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(days=number)
    days = int(start_time.timestamp())
    return days


def get_api_answer(days):
    '''Получает ответ от API на запрос json домашних работы.
    Проверяет наличие ответа и ожидаемые ключи в API.'''
    fromdate = number_days(days)
    params_api = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': fromdate},
    }
    try:
        logging.info(
            'Начало отправки запроса API. Параметры: {}'.format(**params_api)
        )
        response = (
            requests.get(**params_api)
        ).json()
        if 'homeworks' not in response or 'status' not in response:
            logging.error('Invalid response: %s', response.text)
            if error != last_error:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f'Error sending message: {error}',
                )
                last_error = error
        return response
    except requests.exceptions.HTTPError as error:
        logging.error(f'Ошибка при запросе к эндпоинту API: {error}')
    except requests.exceptions.ConnectionError as error:
        logging.error('Error Connecting:', error)
    except requests.exceptions.Timeout as error:
        logging.error('Timeout Error:', error)
    except requests.exceptions.RequestException as error:
        logging.error('Something went wrong:', error)




# Опишите, какой вид JSON вы ожидаете
schema = {
    "type": "object",
    "properties": {
        "homeworks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "status": {"type": "string"},
                    "homework_name": {"type": "string"},
                },
                "required": ["id", "status", "homework_name"]
            }
        },
    }
}

# Прочитайте JSON-файл
with open("test.json") as file:
    data = json.load(file)
    # print(data)

# Валидация поднимет исключение, если данные не соответствуют схеме
validate(instance=data, schema=schema):
# Если все хорошо, выведем сообщение
print("Данные валидны")

