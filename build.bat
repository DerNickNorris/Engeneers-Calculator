@echo off
REM Baut die Windows-EXE lokal. Voraussetzung: Python 3.11+ installiert.
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Erstelle virtuelle Umgebung ...
    py -3 -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error

echo Installiere Abhaengigkeiten ...
python -m pip install --upgrade pip >nul
pip install -r requirements-dev.txt || goto :error

echo Fuehre Tests aus ...
set QT_QPA_PLATFORM=offscreen
python -m pytest -q || goto :error
set QT_QPA_PLATFORM=

echo Baue EXE ...
pyinstaller ingrechner.spec --noconfirm || goto :error

echo Selbsttest ...
"dist\Ingenieurs-Rechner\Ingenieurs-Rechner.exe" --selftest --selftest-out=selftest.txt
type selftest.txt

echo.
echo Fertig: dist\Ingenieurs-Rechner\Ingenieurs-Rechner.exe

REM ---- Installer (optional, benoetigt Inno Setup 6: https://jrsoftware.org/isdl.php)
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo Inno Setup nicht gefunden - Installer wird uebersprungen.
    echo Zum Weitergeben den kompletten Ordner dist\Ingenieurs-Rechner zippen.
    exit /b 0
)
for /f %%v in ('python -c "import ingrechner; print(ingrechner.__version__)"') do set "APPVER=%%v"
echo Baue Installer fuer Version %APPVER% ...
"%ISCC%" /Q "/DAppVersion=%APPVER%" installer\ingrechner.iss || goto :error
echo Fertig: dist\installer\Ingenieurs-Rechner-Setup-%APPVER%.exe
exit /b 0

:error
echo.
echo FEHLER beim Build - siehe Ausgabe oben.
exit /b 1
