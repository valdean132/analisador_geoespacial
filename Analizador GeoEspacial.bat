color a

cd  C:\analisador_geoespacial\

call .venv\Scripts\activate.bat

cls

@echo off
echo.
echo Menu de Opcoes (Digite o numero para prosseguir)
echo.
echo 1. Abrir App
echo 2. Execultar pela tela de comando
echo 3. Sair
echo.
set /p OPCAO="Digite a sua escolha: "

if "%OPCAO%"=="1" goto Opcao1
if "%OPCAO%"=="2" goto Opcao2
if "%OPCAO%"=="3" goto Sair

goto :eof

:Opcao1
echo Abrindo App...
cls
py app_gui.py
@REM echo comando 1 executado.
pause
goto :eof

:Opcao2
echo Execultar pela tela de comando...
cls
py analisar_viabilidade.py
@REM echo comando 2 executado.
pause
goto :eof

:Sair
echo Saindo do programa.
goto :eof