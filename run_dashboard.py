import os
import subprocess
import sys
import webbrowser
import threading

import structlog
from logging_config import configurar_logging

logger = structlog.get_logger("run_dashboard")


def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _matar_porta(porta):
    meu_pid = os.getpid()
    try:
        if sys.platform == 'win32':
            resultado = subprocess.run(
                ['netstat', '-ano'], capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for linha in resultado.stdout.splitlines():
                if f':{porta}' in linha and 'LISTENING' in linha:
                    pid = int(linha.strip().split()[-1])
                    if pid != meu_pid:
                        subprocess.run(
                            ['taskkill', '/F', '/PID', str(pid)],
                            capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
        else:
            resultado = subprocess.run(
                ['lsof', '-ti', f':{porta}'], capture_output=True, text=True,
            )
            for pid_str in resultado.stdout.splitlines():
                try:
                    pid = int(pid_str.strip())
                    if pid != meu_pid:
                        os.kill(pid, 9)
                except (ValueError, ProcessLookupError, PermissionError):
                    pass
    except Exception:
        pass


def main():
    configurar_logging()
    base = get_base_path()
    cwd = os.getcwd()
    _matar_porta(8501)

    if getattr(sys, 'frozen', False):
        import shutil

        config_src = os.path.join(base, 'config.json')
        if os.path.exists(config_src) and not os.path.exists(os.path.join(cwd, 'config.json')):
            shutil.copy2(config_src, os.path.join(cwd, 'config.json'))

        streamlit_config_src = os.path.join(base, '.streamlit', 'config.toml')
        streamlit_config_dst = os.path.join(cwd, '.streamlit', 'config.toml')
        if os.path.exists(streamlit_config_src) and not os.path.exists(streamlit_config_dst):
            os.makedirs(os.path.dirname(streamlit_config_dst), exist_ok=True)
            shutil.copy2(streamlit_config_src, streamlit_config_dst)

        app_path = os.path.join(base, 'ui', 'app.py')

        from streamlit.web.cli import main as streamlit_main
        sys.argv = ['streamlit', 'run', app_path]
        threading.Timer(2.0, lambda: webbrowser.open('http://localhost:8501')).start()
        streamlit_main()
    else:
        app_path = os.path.join(os.path.dirname(__file__), 'ui', 'app.py')
        subprocess.run([
            sys.executable, '-m', 'streamlit', 'run', app_path,
            '--server.port=8501',
            '--server.headless=true',
        ])


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical("Erro ao iniciar dashboard", erro=str(e))
        input("\nPressione ENTER para fechar...")
