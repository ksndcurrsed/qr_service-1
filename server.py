from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from collections import deque
import asyncio
import os

app = FastAPI()

# CORS (можно оставить *)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Очередь заданий
print_queue = deque()
queue_lock = asyncio.Lock()


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
            let lastScanned = { text: '', time: 0 };

            async function onScan(text) {
                const now = Date.now();
                if (text === lastScanned.text && (now - lastScanned.time) < 2000) return;
                lastScanned = { text: text, time: now };

                if (busy) return;
                busy = true;
                html5QrCode.pause();

                document.getElementById('status').innerText = "Отправка...";

                await fetch('/send-to-print', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({data: text})
                });

                busy = false;
                html5QrCode.resume();
                document.getElementById('status').innerText = "Готово! Можно сканировать следующий";
                setTimeout(() => {
                    document.getElementById('status').innerText = "Жду следующий код";
                }, 2000);
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

@app.head("/")
async def head_root():
    return


class ScanData(BaseModel):
    data: str


@app.post("/send-to-print")
async def send_to_print(scan: ScanData):
    async with queue_lock:
        print_queue.append(scan.data)
    return {"status": "ok"}


@app.get("/get-job")
async def get_job():
    async with queue_lock:
        if print_queue:
            return {"status": "ok", "data": print_queue.popleft()}
        return {"status": "empty", "data": None}


if __name__ == "__main__":
    import uvicorn
    _dir = os.path.dirname(os.path.abspath(__file__))
    ssl_certfile = os.environ.get("SSL_CERTFILE") or os.path.join(_dir, "fffzar-tool.ru-chain.pem")
    ssl_keyfile = os.environ.get("SSL_KEYFILE") or os.path.join(_dir, "fffzar-tool.ru-key.pem")
    if os.path.exists(ssl_certfile) and os.path.exists(ssl_keyfile):
        uvicorn.run(app, host="0.0.0.0", port=443, ssl_certfile=ssl_certfile, ssl_keyfile=ssl_keyfile)
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)  # 80 свободен для win-acme
