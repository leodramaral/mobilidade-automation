import structlog
from rich.logging import RichHandler
import logging
from datetime import datetime


# Cores ANSI
COLORS = {
    "DEBUG": "\033[36m",       # ciano
    "INFO": "\033[36m",        # ciano
    "WARNING": "\033[33m",     # amarelo
    "ERROR": "\033[31m",       # vermelho
    "CRITICAL": "\033[1;31m",  # vermelho bold
}
RESET = "\033[0m"

# Cores por app
APP_COLORS = {
    "99": "\033[33m",          # amarelo
    "uber": "\033[34m",        # azul
    "clima": "\033[32m",       # verde
    "coletor": "\033[37m",     # branco
    "repositorio": "\033[37m", # branco
    "agendador": "\033[37m",   # branco
}

MAX_FIELD_LEN = 40
MAX_ERROR_LEN = 460


def custom_time_stamper(logger, method_name, event_dict):
    now = datetime.now()
    event_dict["timestamp"] = now.strftime("%H:%M:%S - %d/%m/%y")
    return event_dict


def truncate(text, max_len=MAX_FIELD_LEN):
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


class CleanRenderer:
    """Renderer limpo com cores ANSI, tags de app e truncamento inteligente."""
    
    def __call__(self, logger, method_name, event_dict):
        timestamp = event_dict.pop("timestamp", "")
        level = event_dict.pop("level", "").upper()
        event = event_dict.pop("event", "")
        
        # Extrair app (não vai para os fields)
        app = event_dict.pop("app", None)
        
        # Montar campos restantes (excluindo app)
        fields = []
        for k, v in event_dict.items():
            if k in ("logger", "positional_args"):
                continue
            
            # Truncamento maior para campos de erro
            max_len = MAX_ERROR_LEN if k in ("erro", "exception", "traceback") else MAX_FIELD_LEN
            
            if isinstance(v, str):
                fields.append(f"{k}='{truncate(v, max_len)}'")
            elif isinstance(v, (list, tuple)):
                text = str(v)
                fields.append(f"{k}={truncate(text, max_len)}")
            else:
                fields.append(f"{k}={v}")
        
        fields_str = "  ".join(fields) if fields else ""
        
        # Cor do nível
        level_color = COLORS.get(level, "")
        
        # Tag de app com cor
        app_tag = ""
        if app:
            app_color = APP_COLORS.get(app, "\033[37m")
            app_tag = f" {app_color}[{app}]{RESET}"
        
        # Formato: timestamp [LEVEL][app] event  fields
        level_str = f"{level_color}[{level}]{RESET}"
        parts = [f"{timestamp} ", level_str, app_tag, f" {event}"]
        if fields_str:
            parts.append(f"  {fields_str}")
        
        return "".join(parts)


def configurar_logging(nivel="INFO"):
    logging.basicConfig(
        level=nivel,
        format="%(message)s",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                show_path=False,
                show_time=False,
            )
        ],
    )
    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        custom_time_stamper,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.format_exc_info,
        CleanRenderer(),
    ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, nivel, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
