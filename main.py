import logging
import requests
import datetime
import time
import os
import json
import pandas as pd
import schedule

# Настройка логирования: вывод в консоль и в файл script.log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("settings/script.log", encoding="utf-8")
    ]
)

# Папка для хранения состояния
settings_folder = "settings"
if not os.path.exists(settings_folder):
    os.makedirs(settings_folder)
    logging.info(f"Создана папка для хранения состояния: {settings_folder}")

STATE_FILE = os.path.join(settings_folder, "state.json")

def load_state():
    """
    Загружает состояние из JSON-файла, если он существует.
    Возвращает словарь с current_date и block_from.
    Если файла нет – возвращает None.
    """
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                logging.info(f"Состояние загружено из {STATE_FILE}: {state}")
                return state
        except Exception as e:
            logging.error(f"Ошибка загрузки состояния: {e}")
    return None

def save_state(state):
    """Сохраняет состояние в JSON-файл."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
        logging.info(f"Состояние сохранено: {state}")
    except Exception as e:
        logging.error(f"Ошибка сохранения состояния: {e}")

# URL для запроса CSV
url = 'https://zakupki.gov.ru/epz/order/orderCsvSettings/download.html'

# Базовые параметры запроса
base_params = {
    'morphology': 'on',
    'search-filter': 'Дате размещения',
    'pageNumber': '1',
    'sortDirection': 'true',
    'recordsPerPage': '_10',
    'showLotsInfoHidden': 'false',
    'sortBy': 'PUBLISH_DATE',
    'fz44': 'on',
    'fz223': 'on',
    'af': 'on',
    'ca': 'on',
    'pc': 'on',
    'pa': 'on',
    'currencyIdGeneral': '-1',
    'publishDateFrom': None,
    'publishDateTo': None,
    'from': None,
    'to': None,
    'placementCsv': 'true',
    'registryNumberCsv': 'true',
    'stepOrderPlacementCsv': 'true',
    'methodOrderPurchaseCsv': 'true',
    'nameOrderCsv': 'true',
    'purchaseNumbersCsv': 'true',
    'numberLotCsv': 'true',
    'nameLotCsv': 'true',
    'maxContractPriceCsv': 'true',
    'currencyCodeCsv': 'true',
    'maxPriceContractCurrencyCsv': 'true',
    'currencyCodeContractCurrencyCsv': 'true',
    'scopeOkdpCsv': 'true',
    'scopeOkpdCsv': 'true',
    'scopeOkpd2Csv': 'true',
    'scopeKtruCsv': 'true',
    'ea615ItemCsv': 'true',
    'customerNameCsv': 'true',
    'organizationOrderPlacementCsv': 'true',
    'publishDateCsv': 'true',
    'lastDateChangeCsv': 'true',
    'startDateRequestCsv': 'true',
    'endDateRequestCsv': 'true',
    'ea615DateCsv': 'true',
    'featureOrderPlacementCsv': 'true'
}

header = {
    'User-Agent': ('Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; '
                   'rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7')
}

# Папка для сохранения CSV-файлов
output_folder = "zakupki_data"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    logging.info(f"Создана папка для сохранения файлов: {output_folder}")

# Начальная дата
START_DATE = datetime.date(2012, 10, 10)
delta = datetime.timedelta(days=1)

def process_day(process_date, start_block=1):
    """
    Обрабатывает один день, начиная с указанного блока (start_block).
    Перебирает блоки с шагом 500 и сохраняет CSV-файлы.
    Если число строк в файле (проверяем через pandas) меньше 500, считаем, что данные за этот день закончились.
    """
    current_day_str = process_date.strftime("%d.%m.%Y")
    logging.info(f"Обрабатываем дату: {current_day_str} начиная с блока {start_block}")
    block_from = start_block
    while block_from < 5001:
        block_to = block_from + 500 - 1
        logging.info(f"  Запрос для записей с {block_from} по {block_to}")
        
        params = base_params.copy()
        params["publishDateFrom"] = current_day_str
        params["publishDateTo"] = current_day_str
        params["from"] = str(block_from)
        params["to"] = str(block_to)
        
        try:
            response = requests.get(url, params=params, headers=header, timeout=30)
        except Exception as e:
            logging.error(f"  Ошибка запроса: {e}")
            break
        
        attempt = 1
        while response.status_code != 200 and attempt <= 2:
            logging.warning(f"  Ошибка {response.status_code} для диапазона {block_from}-{block_to} на дату {current_day_str}. Попытка {attempt}.")
            time.sleep(5)
            try:
                response = requests.get(url, params=params, headers=header, timeout=30)
                logging.info(f"  Повторный запрос: {response.url}")
            except Exception as e:
                logging.error(f"  Ошибка запроса при повторной попытке: {e}")
                break
            attempt += 1
        
        if response.status_code == 200:
            try:
                csv_data = response.text
                file_name = f"{current_day_str}_OrderSearch({block_from}-{block_to}).csv"
                file_path = os.path.join(output_folder, file_name)
                with open(file_path, "w", encoding="utf-8", newline="") as file:
                    file.write(csv_data)
                logging.info(f"  Файл сохранён: {file_name}")
            except Exception as e:
                logging.error(f"  Ошибка сохранения файла для диапазона {block_from}-{block_to} на дату {current_day_str}: {e}")
        else:
            logging.error(f"  Ошибка {response.status_code} для диапазона {block_from}-{block_to} на дату {current_day_str} после повторных попыток.")
        
        # Проверка количества строк в файле через pandas
        try:
            df = pd.read_csv(file_path, encoding="utf-8", sep=";")
            row_count = len(df)
            logging.info(f"  Количество строк в файле {file_name}: {row_count}")
            if row_count < 500:
                logging.info("  Строк меньше 500. Данные для этой даты закончились.")
                # Выходим из цикла, сохраняя состояние как завершённое для данного дня
                block_from += 500  # или можно установить block_from = 5001
                save_state({"current_date": process_date.isoformat(), "block_from": block_from})
                break
        except Exception as e:
            logging.error(f"  Ошибка чтения файла {file_name} через pandas: {e}")
        
        block_from += 500
        save_state({"current_date": process_date.isoformat(), "block_from": block_from})
        time.sleep(5)

def scheduled_job():
    """
    Задание для планировщика, которое выполняется для сегодняшних данных после 18:00.
    При запуске извлекается сохранённый block_from, и обработка продолжается с него.
    После завершения обработки сегодняшних данных состояние обновляется для следующего дня.
    """
    now = datetime.datetime.now()
    if now.hour < 18:
        logging.info("Время обработки сегодняшних данных еще не наступило (текущий час меньше 18).")
        return
    today = datetime.date.today()
    state = load_state() or {"current_date": today.isoformat(), "block_from": 1}
    state_block_from = state.get("block_from", 1)
    logging.info(f"Запуск обработки сегодняшних данных: {today.isoformat()} начиная с блока {state_block_from}")
    process_day(today, start_block=state_block_from)
    next_day = today + delta
    save_state({"current_date": next_day.isoformat(), "block_from": 1})

def main():
    """
    Основная функция:
    - Если состояние (current_date) меньше сегодняшней даты, данные скачиваются непрерывно,
      при этом для первого дня используется сохранённый block_from.
    - Если состояние соответствует сегодняшнему дню, используется планировщик, который запускает обработку в 18:00.
    """
    state = load_state() or {"current_date": START_DATE.isoformat(), "block_from": 1}
    try:
        current_date = datetime.date.fromisoformat(state["current_date"])
    except Exception as e:
        logging.error(f"Ошибка преобразования сохранённого состояния: {e}")
        current_date = START_DATE
    state_block_from = state.get("block_from", 1)
    today = datetime.date.today()

    if current_date < today:
        logging.info("Обработка исторических данных в непрерывном режиме.")
        # Для первого дня используем сохраненный block_from
        process_day(current_date, start_block=state_block_from)
        current_date += delta
        save_state({"current_date": current_date.isoformat(), "block_from": 1})
        while current_date < today:
            process_day(current_date)
            current_date += delta
            save_state({"current_date": current_date.isoformat(), "block_from": 1})
    else:
        logging.info("Состояние соответствует сегодняшнему дню. Используем планировщик для запуска задачи в 18:00.")
        schedule.every().day.at("18:00").do(scheduled_job)
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    while True:
        main()
