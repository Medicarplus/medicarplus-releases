@echo off
REM ==================================================================
REM COMPILAR MEDICAR PLUS · Doble-click i ja
REM Requereix Node.js instal·lat des de https://nodejs.org (LTS)
REM ==================================================================

setlocal
title MediCar Plus · Compilador

echo.
echo ================================================
echo   MediCar Plus - Compilador d'.exe
echo ================================================
echo.

REM Comprovem que Node.js hi es
where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js NO esta instal.lat.
    echo.
    echo Instal.la Node.js primer:
    echo   1. Ves a https://nodejs.org
    echo   2. Clica el boto verd "LTS"
    echo   3. Instal.la amb tots els "Next"
    echo   4. Tanca aquesta finestra i torna a fer doble-click a aquest fitxer
    echo.
    pause
    exit /b 1
)

echo [OK] Node.js detectat
node --version
echo.

REM Instal.lem yarn si cal
where yarn >nul 2>nul
if errorlevel 1 (
    echo [.] Instal.lant yarn per primer cop...
    call npm install -g yarn
    if errorlevel 1 (
        echo [ERROR] No s'ha pogut instal.lar yarn. Prova a executar aquest fitxer com a Administrador.
        pause
        exit /b 1
    )
)

echo [OK] Yarn detectat
yarn --version
echo.

echo [.] Instal.lant dependencies (5 min)...
call yarn install
if errorlevel 1 (
    echo [ERROR] yarn install ha fallat. Revisa la connexio a internet.
    pause
    exit /b 1
)
echo.

echo [.] Compilant .exe (10 min)...
call yarn build:installer
if errorlevel 1 (
    echo [ERROR] La compilacio ha fallat. Envia captura d'aquesta pantalla a suport.
    pause
    exit /b 1
)
echo.

echo ================================================
echo   COMPILACIO ACABADA CORRECTAMENT
echo ================================================
echo.
echo Trobaras el .exe nou a la carpeta:
echo   %CD%\dist\
echo.
echo Ara puja aquest .exe a GitHub Releases del repo:
echo   Medicarplus/medicarplus-releases
echo.
echo Obrint la carpeta dist en 3 segons...
timeout /t 3 /nobreak >nul
explorer "%CD%\dist"

pause
endlocal
