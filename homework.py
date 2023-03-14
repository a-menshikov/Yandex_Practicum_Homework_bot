"""Телеграм-бот для проверки статуса домашнего задания."""

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIRequestError, IncorrectRequestStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('log/my_logger.log', maxBytes=50000000,
                              backupCount=5)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет наличие всех переменных окружения."""
    env_tokens = (PRACTICUM_TOKEN,
                  TELEGRAM_CHAT_ID,
                  TELEGRAM_TOKEN,
                  )
    return all(env_tokens)


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Бот отправил сообщение в чат')
    except Exception as error:
        logger.error(f'Сбой в отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Осуществляет запрос к API."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException:
        raise APIRequestError('Ошибка при запросе к API')
    if response.status_code != HTTPStatus.OK:
        raise IncorrectRequestStatus('Статус запроса отличный от 200')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие."""
    if not isinstance(response, dict):
        raise TypeError(f'Ответ API не является словарём,'
                        f'тип ответа {type(response)}')

    checking_keys = ('homeworks',
                     'current_date',
                     )
    if not all(key in response for key in checking_keys):
        raise KeyError('В ответе API недостаточно ключей')

    homework_value = response.get('homeworks')
    if not isinstance(homework_value, list):
        raise TypeError(f'Значение по ключу homeworks не является списком. '
                        f'Тип значения ключа {type(homework_value)}')

    if not homework_value:
        raise IndexError('Список домашних работ пустой')

    last_homework = homework_value[0]
    if not isinstance(last_homework, dict):
        raise TypeError(f'Данные о последней работе не являются словарем. '
                        f'Тип значения ключа {type(last_homework)}')

    return last_homework


def parse_status(homework):
    """Проверяет статус домашней работы, формирует сообщение."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Отсуствует наименование последней домашней работы')

    homework_status = homework.get('status')
    if not homework_status:
        raise KeyError('Отсуствует статус последней домашней работы')

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not verdict:
        raise KeyError('Вердикт по последней домашней'
                       'работе нестандартный или отсуствует')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.debug('Бот запущен')

    if not check_tokens():
        logger.critical('Сбой в работе программы: '
                        'недостаточно переменных окружения\n'
                        'Работа программы остановлена.')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    last_message = ''
    timestamp = int(time.time())

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            last_homework = check_response(api_answer)
            message = parse_status(last_homework)
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
        finally:
            if message != last_message:
                send_message(bot, message)
                last_message = message
            else:
                logger.debug('Сообщение для отправки не изменилось, '
                             'в телеграм ничего не отправлено')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
