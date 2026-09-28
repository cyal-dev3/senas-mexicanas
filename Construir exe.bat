@echo off
rem Construye dist\MiraTek.exe (la app de PC para grabar y entrenar).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Creando entorno de Python...
    python -m venv .venv || goto :error
)
.venv\Scripts\python.exe -m pip install -q -r requirements.txt -r requirements-dev.txt || goto :error
.venv\Scripts\python.exe tools\build_exe.py || goto :error
explorer dist
pause
exit /b 0
:error
echo.
echo Algo fallo. Revisa los mensajes de arriba.
pause
exit /b 1
