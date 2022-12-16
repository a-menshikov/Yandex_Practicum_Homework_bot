"""Телеграм-бот для проверки статус домашнего задания."""

import logging
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
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет наличие всех переменных окружения."""
    if not PRACTICUM_TOKEN:
        raise ValueError('Отсутствует обязательная переменная '
                         'окружения: PRACTICUM_TOKEN.\n'
                         'Работа программы остановлена.')
    if not TELEGRAM_TOKEN:
        raise ValueError('Отсутствует обязательная переменная '
                         'окружения: TELEGRAM_TOKEN.\n'
                         'Работа программы остановлена.')
    if not TELEGRAM_CHAT_ID:
        raise ValueError('Отсутствует обязательная переменная '
                         'окружения: TELEGRAM_CHAT_ID.\n'
                         'Работа программы остановлена.')


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
        raise TypeError(f'Значение по ключу homeworks не является списком'
                        f'тип значения ключа {type(homework_value)}')

    if not homework_value:
        raise IndexError('Список домашних работ пустой')
    return homework_value[0]


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

    try:
        check_tokens()
    except ValueError as error:
        logger.critical(f'Сбой в работе программы: {error}')
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    prev_homework_message = ''
    last_message = ''
    timestamp = int(time.time())

    while True:
        try:
            api_answer = get_api_answer(timestamp)
            last_homework = check_response(api_answer)
            homework_message = parse_status(last_homework)
            if homework_message != prev_homework_message:
                send_message(bot, homework_message)
                prev_homework_message = homework_message
            else:
                logger.debug('Статус последней домашки не изменился')
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            if message != last_message:
                last_message = message
                send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
