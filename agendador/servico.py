from datetime import datetime
from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.blocking import BlockingScheduler
import copy

import structlog
from coletor import Coletor

logger = structlog.get_logger("agendador")


class AgendadorService:
    def __init__(self, config_base, agendamentos):
        self.config_base = config_base
        self.agendamentos = agendamentos
        self.scheduler = BlockingScheduler()

    def _parse_data(self, quando_str):
        return datetime.strptime(quando_str, "%Y-%m-%d %H:%M")

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
        agora = datetime.now()
        for idx, agend in enumerate(self.agendamentos):
            quando = agend.get("quando", "now")
            if quando == "now":
                continue
            try:
                data_execucao = self._parse_data(quando)
            except ValueError:
                logger.warning("Agendamento pulado", quando=quando, motivo="formato de data invalido")
                continue
            if data_execucao <= agora:
                logger.info("Agendamento pulado", quando=quando, motivo="data/hora ja passou")
                continue
            trigger = DateTrigger(run_date=data_execucao)
            job_id = f"coleta_{idx}"
            self.scheduler.add_job(self._executar_agendamento, trigger, args=[agend], id=job_id, misfire_grace_time=None)
            origem = agend['config_override'].get('origem', '?')
            destino = agend['config_override'].get('destino', '?')
            logger.info("Agendamento registrado", quando=quando, origem=origem, destino=destino)

    def iniciar(self):
        self.registrar_jobs()
        jobs = self.scheduler.get_jobs()
        logger.info("Agendador iniciado", jobs=len(jobs))
        if not jobs:
            logger.warning("Nenhum agendamento futuro encontrado em agendamentos.json")
        self.scheduler.start()
