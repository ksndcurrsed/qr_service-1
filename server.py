from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_to_pc(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://unpkg.com/html5-qrcode"></script>
        <style>
            body { font-family: sans-serif; text-align: center; background: #f4f4f4; margin: 0; padding: 20px; }
            #reader { width: 100%; max-width: 400px; margin: auto; border-radius: 10px; overflow: hidden; }
            .status { margin-top: 20px; padding: 15px; background: white; border-radius: 10px; }
        </style>
    </head>
    <body>
        <h2>Сканер Data Matrix</h2>
        <div id="reader"></div>
        <div id="status" class="status">Ожидание сканирования...</div>

        <script>
            const html5QrCode = new Html5Qrcode("reader");
            let isPaused = false;

            async function onScanSuccess(decodedText) {
                if (isPaused) return;
                isPaused = true;
                html5QrCode.pause();
                
                document.getElementById('status').innerText = "Отправка: " + decodedText;

                await fetch('/send-to-print', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({data: decodedText})
                });

                alert("Код отправлен на печать!");
                isPaused = false;
                html5QrCode.resume();
                document.getElementById('status').innerText = "Готов к следующему коду";
            }

            // Настройка именно под Data Matrix
            const config = { 
                fps: 10, 
                qrbox: 250,
                formatsToSupport: [ Html5QrcodeSupportedFormats.DATA_MATRIX ]
            };
            
            html5QrCode.start({ facingMode: "environment" }, config, onScanSuccess);
        </script>
    </body>
    </html>
    """

class ScanData(BaseModel):
    data: str

@app.post("/send-to-print")
async def send_to_print(scan: ScanData):
    await manager.send_to_pc(scan.data)
    return {"status": "ok"}

@app.websocket("/ws-print")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)