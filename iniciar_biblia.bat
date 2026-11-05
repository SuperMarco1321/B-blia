@echo off
title Biblia Digital
rem ============================================================
rem  Inicia a Biblia Digital com dois cliques.
rem  Deixe este arquivo na RAIZ do projeto (ao lado das pastas core, ui e utils).
rem ============================================================

rem Vai para a pasta onde este arquivo esta, nao importa de onde foi aberto
cd /d "%~dp0"

if not exist "ui\biblia_digital.py" (
    echo [ERRO] Nao encontrei ui\biblia_digital.py nesta pasta.
    echo Coloque este arquivo na raiz do projeto, ao lado das pastas core, ui e utils.
    echo.
    pause
    exit /b 1
)

rem Procura o Python: primeiro "python", depois o atalho "py" do Windows
set "PY="
python --version >nul 2>nul && set "PY=python"
if not defined PY (
    py --version >nul 2>nul && set "PY=py"
)
if not defined PY (
    echo [ERRO] Python nao encontrado.
    echo Instale em https://www.python.org/downloads/ e marque a opcao "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

rem Instala o Streamlit se ainda nao estiver instalado
%PY% -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo Streamlit nao encontrado. Instalando, aguarde...
    %PY% -m pip install streamlit
    if errorlevel 1 (
        echo.
        echo [ERRO] Nao foi possivel instalar o Streamlit. Verifique a internet e tente de novo.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Iniciando a Biblia Digital... o navegador abre sozinho.
echo Para ENCERRAR o site, feche esta janela (ou aperte Ctrl+C).
echo.
%PY% -m streamlit run ui/biblia_digital.py

echo.
echo O site foi encerrado.
pause
