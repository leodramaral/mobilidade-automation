from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.blocking import BlockingScheduler
import copy

import structlog
from coletor import Coletor

logger = structlog.get_logger("agendador")


class AgendadorService:
    def __init__(self, config_base, agendamentos, timezone_str="America/Manaus"):
        self.config_base = config_base
        self.agendamentos = agendamentos
        self.tz = ZoneInfo(timezone_str)
        self.scheduler = BlockingScheduler(timezone=self.tz)

    def _parse_data(self, quando_str):
        naive = datetime.strptime(quando_str, "%Y-%m-%d %H:%M")
        return naive.replace(tzinfo=self.tz)

    def _merge_config(self, override):
        config = copy.deepcopy(self.config_base)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(config.get(k), dict):
                config[k].update(v)
            else:
                config[k] = v
        return config

    def _executar_agendamento(self, agendamento):
        config = self._merge_config(agendamento.get("config_override", {}))
        coletor = Coletor(config)
        coletor.executar()

    def registrar_jobs(self):
        agora = datetime.now(self.tz)
        for idx, agend in enumerate(self.agendamentos):
            data_execucao = self._parse_data(agend["quando"])
            if data_execucao <= agora:
                logger.info("Agendamento pulado", quando=agend['quando'], motivo="data/hora já passou")
                continue
            trigger = DateTrigger(run_date=data_execucao)
            job_id = f"coleta_{idx}"
            self.scheduler.add_job(self._executar_agendamento, trigger, args=[agend], id=job_id)
            origem = agend['config_override'].get('origem', '?')
            destino = agend['config_override'].get('destino', '?')
            logger.info("Agendamento registrado", quando=agend['quando'], origem=origem, destino=destino)

    def iniciar(self):
        self.registrar_jobs()
        jobs = self.scheduler.get_jobs()
        logger.info("Agendador iniciado", jobs=len(jobs))
        if not jobs:
            logger.warning("Nenhum agendamento futuro encontrado em agendamentos.json")
        self.scheduler.start()
