import time
import asyncio
import aiohttp
import ssl
import os
import datetime
import win32print
import win32ui
from PIL import Image, ImageWin
from pylibdmtx.pylibdmtx import encode
from pynput import keyboard
from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from dotenv import load_dotenv

load_dotenv()

# --- НАСТРОЙКИ ---
SERVER_IP = "84.54.29.24"
SERVER_DOMAIN = "fffzar-tool.ru"
# Используем HTTPS после настройки SSL
SERVER_URL = f"https://{SERVER_DOMAIN}"
HISTORY_FOLDER = "history"
EXCEL_FILE = "report.xlsx"

# Создаем папку для истории, если её нет
if not os.path.exists(HISTORY_FOLDER):
    os.makedirs(HISTORY_FOLDER)

def save_to_report(text, file_path):
    """Записывает данные о сканировании в Excel"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not os.path.exists(EXCEL_FILE):
        wb = Workbook()
        ws = wb.active
        ws.append(["Дата и время", "Содержимое кода", "Имя файла"])
    else:
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active

    ws.append([timestamp, ILLEGAL_CHARACTERS_RE.sub(r'', text), os.path.basename(file_path)])
    wb.save(EXCEL_FILE)

def process_and_print(text):
    """Генерация, сохранение, логирование и печать"""
    print(f"Обработка: {text}")
    try:
        # 1. Генерация Data Matrix
        encoded = encode(text.encode('utf-8'))
        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
        img = img.resize((150, 150), Image.NEAREST)

        # 2. Сохранение в папку истории с уникальным именем
        file_name = f"scan_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        full_path = os.path.join(HISTORY_FOLDER, file_name)
        img.save(full_path)

        # 3. Запись в Excel
        save_to_report(text, full_path)

        # 4. Печать
        printer_name = win32print.GetDefaultPrinter()
        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(printer_name)
        
        bmp = Image.open(full_path)
        hDC.StartDoc("DM_Job")
        hDC.StartPage()
        dib = ImageWin.Dib(bmp)
        dib.draw(hDC.GetHandleOutput(), (5, 5, 150, 150))
        hDC.EndPage()
        hDC.EndDoc()
        hDC.DeleteDC()
        print(f"Успешно: данные сохранены и отправлены на принтер.")
        
    except Exception as e:
        print(f"Ошибка при обработке: {e}")

# --- Логика перехвата (USB/Bluetooth сканер) ---
buffer = []

last_key_time = 0
is_scanner_typing = True

def on_press(key):
    global buffer, last_key_time, is_scanner_typing
    
    current_time = time.time()
    # Считаем время с момента прошлого нажатия
    delay = current_time - last_key_time
    last_key_time = current_time

    # Если пауза между буквами больше 50мс — это скорее всего человек
    if delay > 0.05:
        is_scanner_typing = False

    try:
        if key == keyboard.Key.enter:
            msg = "".join(buffer)
            if is_scanner_typing and len(msg) > 15:
                process_and_print(msg)

            buffer = []
            is_scanner_typing = True 
        elif hasattr(key, 'char') and key.char:
            buffer.append(key.char)
    except:
        pass

# --- Связь с сервером (HTTP API) ---
async def listen():
    """Опрос сервера на наличие новых заданий для печати"""
    # Настройка SSL для работы в exe (отключаем проверку сертификата)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Создаем connector с SSL контекстом
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        print(f"Подключение к серверу: {SERVER_URL}")
        while True:
            try:
                async with session.get(f"{SERVER_URL}/get-job", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "ok" and data.get("data"):
                            process_and_print(data["data"])
                            print(f"Получено задание: {data['data']}")
                    await asyncio.sleep(2)  # Проверка каждые 2 секунды
            except asyncio.TimeoutError:
                print("Таймаут подключения. Повтор через 5 сек...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Ошибка подключения к серверу: {e}. Повтор через 5 сек...")
                await asyncio.sleep(5)

if __name__ == "__main__":
    keyboard.Listener(on_press=on_press).start()
    asyncio.run(listen())