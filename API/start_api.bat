@echo off

color a

REM Define o título da janela do console para fácil identificação
title Servidor da API - Analisador Geoespacial

REM Muda o diretório de execução para o local onde este script .bat está
REM "%~dp0" é uma variável especial que significa "a pasta deste script"
cd /d "%~dp0"

echo ----------------------------------------------------
echo Ativando o ambiente virtual (.venv)...
echo ----------------------------------------------------
echo.
REM Ativa o ambiente virtual
call .venv\Scripts\activate.bat

REM Verifica se o ambiente virtual foi ativado com sucesso
if errorlevel 1 (
    echo ERRO: Nao foi possivel encontrar ou ativar o ambiente virtual.
    echo Verifique se a pasta '.venv' existe neste diretorio.
    pause
    goto :eof
)

echo Ambiente ativado com sucesso.
echo.
echo ----------------------------------------------------
echo Iniciando o servidor da API (Uvicorn)...
echo ----------------------------------------------------
echo.
echo A API estara acessivel em:
echo  - Localmente: http://127.0.0.1:8000
echo  - Na rede:    http://%IP_DA_SUA_MAQUINA%:8000 (ex: 172.16.207.86:8000)
echo.
echo Pressione CTRL+C nesta janela para parar o servidor.
echo.

REM Inicia o servidor Uvicorn escutando em todas as interfaces de rede
uvicorn api.main:app --host 0.0.0.0 --port 8000

:eof
echo Servidor finalizado.
pause