@echo off
rem Construye dist\MiraTek.apk con el modelo entrenado en esta PC.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Primero ejecuta "Construir exe.bat" o instala el entorno de Python.
    pause
    exit /b 1
)
.venv\Scripts\python.exe tools\build_apk.py || goto :error
explorer dist
pause
exit /b 0
:error
echo.
echo Algo fallo. Revisa los mensajes de arriba.
pause
exit /b 1
