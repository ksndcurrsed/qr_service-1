@echo off
REM Сборка qr_scanner_app.py в exe
echo Installing dependencies...
pip install pyinstaller PyQt5 pillow pylibdmtx pywin32

echo.
echo Building qr_scanner_app.exe...
pyinstaller --noconfirm --onefile ^
    --name "qr_scanner_app" ^
    --hidden-import=pylibdmtx ^
    --hidden-import=pylibdmtx.pylibdmtx ^
    --collect-all pylibdmtx ^
    --hidden-import=win32print ^
    --hidden-import=win32ui ^
    --hidden-import=win32con ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageWin ^
    --hidden-import=PyQt5 ^
    --hidden-import=PyQt5.QtCore ^
    --hidden-import=PyQt5.QtGui ^
    --hidden-import=PyQt5.QtWidgets ^
    --collect-all PyQt5 ^
    --windowed ^
    --noconsole ^
    qr_scanner_app.py

echo.
echo Done! EXE: dist\qr_scanner_app.exe
pause
