import asyncio
import websockets
import os
import platform
import win32print
import win32ui
from PIL import Image, ImageWin
from pylibdmtx.pylibdmtx import encode
from pynput import keyboard

# ЗАМЕНИТЕ НА ВАШ URL (wss для ngrok/https)
SERVER_URL = "wss://hx27sw-176-52-40-241.ru.tuna.am/ws-print"

buffer = []

def print_datamatrix(text):
    print(f"Печать Data Matrix: {text}")
    try:
        # 1. Генерация Data Matrix
        encoded = encode(text.encode('utf-8'))
        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
        img = img.resize((1000, 1000), Image.NEAREST) # Увеличиваем для четкости
        path = "dm_print.png"
        img.save(path)

        # 2. Тихая печать Windows
        printer_name = win32print.GetDefaultPrinter()
        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(printer_name)
        
        bmp = Image.open(path)
        hDC.StartDoc("DM_Job")
        hDC.StartPage()
        dib = ImageWin.Dib(bmp)
        # Координаты (лево, верх, право, низ)
        dib.draw(hDC.GetHandleOutput(), (100, 100, 1100, 1100))
        hDC.EndPage()
        hDC.EndDoc()
        hDC.DeleteDC()
    except Exception as e:
        print(f"Ошибка: {e}")

# Обработка Bluetooth/USB сканера
def on_press(key):
    global buffer
    try:
        if key == keyboard.Key.enter:
            msg = "".join(buffer)
            if msg:
                print_datamatrix(msg)
                buffer = []
        elif hasattr(key, 'char') and key.char:
            buffer.append(key.char)
    except: pass

async def listen():
    while True:
        try:
            async with websockets.connect(SERVER_URL) as ws:
                print("Подключено к серверу!")
                while True:
                    data = await ws.recv()
                    print_datamatrix(data)
        except Exception as e:
            print("Переподключение...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # Запуск перехвата сканера
    keyboard.Listener(on_press=on_press).start()
    # Запуск связи с сервером
    asyncio.run(listen())