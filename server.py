from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from collections import deque
import asyncio

app = FastAPI()

# Разрешаем CORS для работы с доменом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Очередь заданий для печати
print_queue = deque()
queue_lock = asyncio.Lock()  # Блокировка для безопасной работы с очередью

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://unpkg.com/html5-qrcode"></script>
        <style>
            body { font-family: sans-serif; text-align: center; margin: 0; padding: 20px; background: #eef2f7; }
            #reader { width: 100%; max-width: 400px; margin: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
            .info { margin-top: 15px; padding: 10px; background: #fff; border-radius: 8px; font-size: 14px; }
        </style>
    </head>
    <body>
        <h3>Сканер Маркировки</h3>
        <div id="reader"></div>
        <div id="status" class="info">Наведите камеру на Data Matrix</div>

        <script>
            const html5QrCode = new Html5Qrcode("reader");
            let busy = false;

            async function onScan(text) {
                if (busy) return;
                busy = true;
                html5QrCode.pause();
                
                document.getElementById('status').innerText = "Отправка в отчет...";

                await fetch('/send-to-print', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({data: text})
                });

                alert("Готово! Данные в отчете и на печати.");
                busy = false;
                html5QrCode.resume();
                document.getElementById('status').innerText = "Жду следующий код";
            }

            html5QrCode.start(
                { facingMode: "environment" }, 
                { fps: 10, qrbox: 250, formatsToSupport: [ Html5QrcodeSupportedFormats.DATA_MATRIX ] }, 
                onScan
            );
        </script>
    </body>
    </html>
    """

class ScanData(BaseModel):
    data: str

@app.post("/send-to-print")
async def send_to_print(scan: ScanData):
    """Принимает данные от телефона и добавляет в очередь"""
    async with queue_lock:
        print_queue.append(scan.data)
    return {"status": "ok", "message": "Данные добавлены в очередь"}

@app.get("/get-job")
async def get_job():
    """Возвращает следующее задание из очереди для клиента"""
    async with queue_lock:
        if print_queue:
            data = print_queue.popleft()
            return {"status": "ok", "data": data}
        else:
            return {"status": "empty", "data": None}

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Пути к SSL сертификатам (после настройки certbot)
    ssl_keyfile = "/etc/letsencrypt/live/fffzar-tool.ru/privkey.pem"
    ssl_certfile = "/etc/letsencrypt/live/fffzar-tool.ru/fullchain.pem"
    
    # Проверяем наличие SSL сертификатов
    key_exists = os.path.exists(ssl_keyfile)
    cert_exists = os.path.exists(ssl_certfile)
    
    print(f"🔍 Проверка SSL: privkey={key_exists}, fullchain={cert_exists}")
    
    if key_exists and cert_exists:
        # Запуск с SSL
        print("✅ SSL сертификаты найдены. Запуск на HTTPS порту 443")
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=443,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile
        )
    else:
        # Запуск без SSL (для разработки или если SSL еще не настроен)
        print("⚠️  SSL сертификаты не найдены. Запуск на HTTP порту 8000")
        print(f"   Для настройки SSL выполните: certbot certonly --standalone -d fffzar-tool.ru")
        uvicorn.run(app, host="0.0.0.0", port=8000)