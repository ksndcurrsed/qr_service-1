import sys
import os
import time
import datetime
import win32print
import win32ui
import win32con
from PIL import Image, ImageWin
from pylibdmtx.pylibdmtx import encode
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

# Импортируем функции печати из main.py (если они там есть, иначе дублируем)
HISTORY_FOLDER = "history"
LABEL_MM = (58, 40)
PRINTER_DPI = 203
QR_FILL_RATIO = float(os.environ.get("QR_FILL_RATIO", "0.82"))

# Создаем папку для истории, если её нет
if not os.path.exists(HISTORY_FOLDER):
    os.makedirs(HISTORY_FOLDER)


def mm_to_px(mm, dpi=PRINTER_DPI):
    """Конвертация миллиметров в пиксели принтера"""
    return int(mm / 25.4 * dpi)


def _dmpaper_user_const() -> int:
    return int(getattr(win32con, "DMPAPER_USER", 256))


def build_label_devmode(printer_name: str, width_mm: int, height_mm: int):
    """Возвращает DEVMODE с кастомным размером бумаги"""
    try:
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            info2 = win32print.GetPrinter(hPrinter, 2)
            devmode = info2.get("pDevMode")
            if devmode is None:
                return None

            devmode.Fields |= (
                win32con.DM_PAPERSIZE
                | win32con.DM_PAPERWIDTH
                | win32con.DM_PAPERLENGTH
                | win32con.DM_ORIENTATION
            )
            devmode.PaperSize = _dmpaper_user_const()
            devmode.PaperWidth = int(width_mm * 10)
            devmode.PaperLength = int(height_mm * 10)
            devmode.Orientation = (
                win32con.DMORIENT_LANDSCAPE
                if width_mm >= height_mm
                else win32con.DMORIENT_PORTRAIT
            )
            return devmode
        finally:
            win32print.ClosePrinter(hPrinter)
    except Exception as e:
        print(f"Не удалось подготовить настройки бумаги принтера (DEVMODE): {e}")
        return None


def create_printer_dc(printer_name: str, label_mm: tuple[int, int] = LABEL_MM):
    """Создаёт DC принтера"""
    devmode = build_label_devmode(printer_name, label_mm[0], label_mm[1])
    hDC = win32ui.CreateDC()

    if devmode is not None:
        try:
            hDC.CreateDC("WINSPOOL", printer_name, None, devmode)
            return hDC
        except Exception as e:
            print(f"DEVMODE не применился, печатаю с настройками драйвера по умолчанию: {e}")

    hDC.CreatePrinterDC(printer_name)
    return hDC


def get_dc_page_px(hDC) -> tuple[int, int]:
    """Размер печатаемой области (в пикселях устройства)"""
    w = int(hDC.GetDeviceCaps(win32con.HORZRES) or 0)
    h = int(hDC.GetDeviceCaps(win32con.VERTRES) or 0)
    return w, h


# Защита от дублей
_last_printed = {}
_DEDUP_SEC = 2


def print_data_matrix(text: str) -> tuple[bool, str]:
    """
    Генерирует Data Matrix и печатает на дефолтный принтер.
    Возвращает (успех, сообщение об ошибке или успехе).
    """
    global _last_printed
    now = time.time()
    if text in _last_printed and (now - _last_printed[text]) < _DEDUP_SEC:
        return False, "Пропуск дубля"
    _last_printed[text] = now
    _last_printed = {k: v for k, v in _last_printed.items() if now - v < 60}

    try:
        # 1. Генерация Data Matrix
        encoded = encode(text.encode('utf-8'))
        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)

        # 2. Создаём DC и берём реальный размер страницы
        printer_name = win32print.GetDefaultPrinter()
        hDC = create_printer_dc(printer_name, LABEL_MM)
        try:
            page_w, page_h = get_dc_page_px(hDC)

            # Фолбэк, если драйвер вернул 0
            if page_w <= 0 or page_h <= 0:
                dpi_x = int(hDC.GetDeviceCaps(win32con.LOGPIXELSX) or PRINTER_DPI)
                dpi_y = int(hDC.GetDeviceCaps(win32con.LOGPIXELSY) or PRINTER_DPI)
                page_w = mm_to_px(LABEL_MM[0], dpi_x)
                page_h = mm_to_px(LABEL_MM[1], dpi_y)

            # 3. QR/DM занимает заданную долю меньшей стороны, по центру
            qr_size = max(1, int(min(page_w, page_h) * QR_FILL_RATIO))
            img = img.resize((qr_size, qr_size), Image.NEAREST)

            # 4. Создаём полную этикетку с центрированным QR
            label_img = Image.new('RGB', (page_w, page_h), 'white')
            x = max(0, (page_w - qr_size) // 2)
            y = max(0, (page_h - qr_size) // 2)
            label_img.paste(img, (x, y))

            # 5. Сохранение в папку истории
            file_name = f"scan_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
            full_path = os.path.join(HISTORY_FOLDER, file_name)
            label_img.save(full_path)

            # 6. Печать
            hDC.StartDoc("DM_Job")
            hDC.StartPage()
            dib = ImageWin.Dib(label_img)
            dib.draw(hDC.GetHandleOutput(), (0, 0, page_w, page_h))
            hDC.EndPage()
            hDC.EndDoc()
            return True, "Успешно отправлено на печать"
        finally:
            try:
                hDC.DeleteDC()
            except Exception:
                pass

    except Exception as e:
        return False, f"Ошибка: {str(e)}"


class PrintWorker(QThread):
    """Поток для печати, чтобы не блокировать UI"""
    finished = pyqtSignal(bool, str)
    status_update = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        self.status_update.emit("Генерация Data Matrix...")
        time.sleep(0.1)  # Небольшая задержка для обновления UI
        self.status_update.emit("Отправка на принтер...")
        success, message = print_data_matrix(self.text)
        self.finished.emit(success, message)


class QRScannerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.input_buffer = ""
        self.last_key_time = 0
        self.print_worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("QR Сканер - Печать")
        self.setFixedSize(400, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)  # Окно всегда сверху

        # Центрируем окно
        self.center_window()

        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        central_widget.setLayout(layout)

        # Заголовок
        title = QLabel("QR Сканер")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Статус
        self.status_label = QLabel("Ожидаются данные...")
        self.status_label.setAlignment(Qt.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(12)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px solid #ccc;
                border-radius: 10px;
                padding: 15px;
                color: #333;
            }
        """)
        layout.addWidget(self.status_label)

        # Кнопка закрытия
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        layout.addWidget(close_btn)

        # Устанавливаем фокус для перехвата ввода
        self.setFocusPolicy(Qt.StrongFocus)
        # Делаем окно активным при показе
        self.activateWindow()
        self.raise_()

    def center_window(self):
        """Центрирует окно на экране"""
        frame_geometry = self.frameGeometry()
        screen = QApplication.primaryScreen().availableGeometry().center()
        frame_geometry.moveCenter(screen)
        self.move(frame_geometry.topLeft())
    
    def showEvent(self, event):
        """При показе окна активируем его и устанавливаем фокус"""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def keyPressEvent(self, event):
        """Перехватывает нажатия клавиш от сканера"""
        current_time = time.time()
        delay = current_time - self.last_key_time
        self.last_key_time = current_time

        # Если пауза больше 100мс - это человек, очищаем буфер
        if delay > 0.1:
            self.input_buffer = ""

        # Обрабатываем Enter (сканер обычно отправляет Enter в конце)
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if len(self.input_buffer) > 15:  # Минимальная длина для QR кода
                self.process_input(self.input_buffer)
            self.input_buffer = ""
        elif event.text() and event.text().isprintable():
            # Добавляем символ в буфер
            self.input_buffer += event.text()

        # Не вызываем super(), чтобы перехватить все события
        event.accept()

    def process_input(self, text: str):
        """Обрабатывает введенный текст"""
        if self.print_worker and self.print_worker.isRunning():
            return  # Уже печатаем

        self.update_status("Данные получены", "#28a745")
        self.input_buffer = ""

        # Запускаем печать в отдельном потоке
        self.print_worker = PrintWorker(text)
        self.print_worker.status_update.connect(self.update_status)
        self.print_worker.finished.connect(self.on_print_finished)
        self.print_worker.start()

    def update_status(self, message: str, color: str = "#333"):
        """Обновляет статус"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                background-color: #f0f0f0;
                border: 2px solid #ccc;
                border-radius: 10px;
                padding: 15px;
                color: {color};
            }}
        """)

    def on_print_finished(self, success: bool, message: str):
        """Обработчик завершения печати"""
        if success:
            self.update_status("Отправлено на печать ✓", "#28a745")
            # Через 2 секунды возвращаемся к ожиданию
            QApplication.processEvents()
            time.sleep(2)
            self.update_status("Ожидаются данные...", "#333")
        else:
            self.update_status(f"Ошибка: {message}", "#dc3545")
            # Через 3 секунды возвращаемся к ожиданию
            QApplication.processEvents()
            time.sleep(3)
            self.update_status("Ожидаются данные...", "#333")


def main():
    app = QApplication(sys.argv)
    
    # Устанавливаем темную тему (опционально)
    app.setStyle('Fusion')
    
    window = QRScannerWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
