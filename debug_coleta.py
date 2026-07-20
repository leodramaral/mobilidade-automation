import logging
import os
from datetime import datetime
from typing import Optional

_handler: Optional[logging.FileHandler] = None
_logger: Optional[logging.Logger] = None
_finalizado: bool = False


def iniciar() -> logging.Logger:
    global _handler, _logger, _finalizado
    _finalizado = False
    os.makedirs("debugs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    caminho = os.path.join("debugs", f"{timestamp}.log")
    _handler = logging.FileHandler(caminho, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    _logger = logging.getLogger(f"coleta.debug.{timestamp}")
    _logger.setLevel(logging.DEBUG)
    _logger.addHandler(_handler)
    _logger.propagate = False
    return _logger


def obter() -> Optional[logging.Logger]:
    if _finalizado or _handler is None:
        return None
    return _logger


def finalizar() -> None:
    global _handler, _logger, _finalizado
    if not _finalizado and _handler is not None:
        _logger.removeHandler(_handler)
        _handler.close()
    _finalizado = True
    _handler = None
    _logger = None
