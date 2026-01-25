import asyncio
import websockets
import os
import datetime
import win32print
import win32ui
from PIL import Image, ImageWin
from pylibdmtx.pylibdmtx import encode
from pynput import keyboard
from openpyxl import Workbook, load_workbook
from dotenv import load_dotenv

load_dotenv()

# --- НАСТРОЙКИ ---
SERVER_URL = f"{os.getenv('SERVER_IP')}/ws-print"
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

    ws.append([timestamp, text, os.path.basename(file_path)])
    wb.save(EXCEL_FILE)

def process_and_print(text):
    """Генерация, сохранение, логирование и печать"""
    print(f"Обработка: {text}")
    try:
        # 1. Генерация Data Matrix
        encoded = encode(text.encode('utf-8'))
        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
        img = img.resize((400, 400), Image.NEAREST)

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
        dib.draw(hDC.GetHandleOutput(), (100, 100, 600, 600))
        hDC.EndPage()
        hDC.EndDoc()
        hDC.DeleteDC()
        print(f"Успешно: данные сохранены и отправлены на принтер.")
        
    except Exception as e:
        print(f"Ошибка при обработке: {e}")

# --- Логика перехвата (USB/Bluetooth сканер) ---
buffer = []
def on_press(key):
    global buffer
    try:
        if key == keyboard.Key.enter:
            msg = "".join(buffer)
            if msg:
                process_and_print(msg)
                buffer = []
        elif hasattr(key, 'char') and key.char:
            buffer.append(key.char)
    except: pass

# --- Связь с облаком (Телефон) ---
async def listen():
    while True:
        try:
            async with websockets.connect(SERVER_URL) as ws:
                print("Связь с сервером установлена!")
                while True:
                    data = await ws.recv()
                    process_and_print(data)
        except Exception:
            print("Потеря связи. Повтор через 5 сек...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    keyboard.Listener(on_press=on_press).start()
    asyncio.run(listen())