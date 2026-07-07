@echo off
echo ============================================
echo   Mobilidade - Build do Executavel
echo ============================================
echo.

if not exist build_venv (
    echo Criando virtual environment...
    python -m venv build_venv
)

echo Ativando venv...
call build_venv\Scripts\activate

echo Instalando dependencias...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Gerando executavel...
pyinstaller --clean --noconfirm Mobilidade.spec

echo.
if exist dist\Mobilidade.exe (
    echo ============================================
    echo   Build concluido com sucesso!
    echo   Executavel: dist\Mobilidade.exe
    echo.
    echo   Para rodar: clique com botao direito no
    echo   Mobilidade.exe e selecione "Executar
    echo   como administrador".
    echo ============================================
) else (
    echo ============================================
    echo   ERRO: Build falhou. Verifique os logs.
    echo ============================================
)

pause
