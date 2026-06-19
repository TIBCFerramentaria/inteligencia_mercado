from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from mercado.models import AlvoColeta


class Command(BaseCommand):
    help = "Executa múltiplos serviços de coleta em paralelo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--servicos",
            type=str,
            default=None,
            help="Lista de serviços separados por vírgula. Ex: servico_01,servico_02",
        )

        parser.add_argument(
            "--max-processos",
            type=int,
            default=2,
            help="Quantidade máxima de serviços rodando em paralelo.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a execução sem salvar dados.",
        )

        parser.add_argument(
            "--coletor",
            choices=[
                AlvoColeta.Coletor.LOJA_MECANICO,
                AlvoColeta.Coletor.DUTRA_MAQUINAS,
            ],
            default=None,
            help="Executa apenas alvos de um coletor específico.",
        )

        parser.add_argument(
            "--limite",
            type=int,
            default=None,
            help="Sobrescreve o limite configurado nos alvos.",
        )

        parser.add_argument(
            "--max-paginas",
            type=int,
            default=None,
            help="Sobrescreve o máximo de páginas configurado nos alvos.",
        )

    def obter_servicos(self, servicos_arg):
        if servicos_arg:
            return [
                servico.strip()
                for servico in servicos_arg.split(",")
                if servico.strip()
            ]

        return list(
            AlvoColeta.objects.filter(ativo=True)
            .exclude(servico_coleta__isnull=True)
            .exclude(servico_coleta="")
            .values_list("servico_coleta", flat=True)
            .distinct()
            .order_by("servico_coleta")
        )

    def montar_comando(self, servico, options):
        comando = [
            sys.executable,
            "manage.py",
            "executar_coletas",
            "--servico",
            servico,
        ]

        if options.get("dry_run"):
            comando.append("--dry-run")

        if options.get("coletor"):
            comando.extend(["--coletor", options["coletor"]])

        if options.get("limite") is not None:
            comando.extend(["--limite", str(options["limite"])])

        if options.get("max_paginas") is not None:
            comando.extend(["--max-paginas", str(options["max_paginas"])])

        return comando

    def finalizar_processos_concluidos(self, processos_ativos):
        ainda_ativos = []

        for processo_info in processos_ativos:
            processo = processo_info["processo"]
            servico = processo_info["servico"]
            log_file = processo_info["log_file"]
            log_path = processo_info["log_path"]

            retorno = processo.poll()

            if retorno is None:
                ainda_ativos.append(processo_info)
                continue

            log_file.close()

            if retorno == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[OK] Serviço finalizado com sucesso: {servico} | Log: {log_path}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"[ERRO] Serviço finalizado com erro: {servico} | Código: {retorno} | Log: {log_path}"
                    )
                )

        return ainda_ativos

    def handle(self, *args, **options):
        max_processos = options.get("max_processos") or 2

        if max_processos < 1:
            max_processos = 1

        servicos = self.obter_servicos(options.get("servicos"))

        if not servicos:
            self.stdout.write(
                self.style.WARNING("Nenhum serviço de coleta encontrado.")
            )
            return

        logs_dir = Path(settings.BASE_DIR) / "logs" / "coletas"
        logs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.stdout.write("=" * 100)
        self.stdout.write("EXECUÇÃO PARALELA DE SERVIÇOS DE COLETA")
        self.stdout.write("=" * 100)
        self.stdout.write(f"Serviços: {', '.join(servicos)}")
        self.stdout.write(f"Máximo de processos paralelos: {max_processos}")
        self.stdout.write(f"Dry-run: {options.get('dry_run')}")
        self.stdout.write(f"Logs: {logs_dir}")
        self.stdout.write("=" * 100)

        processos_ativos = []
        houve_erro = False

        for servico in servicos:
            while len(processos_ativos) >= max_processos:
                processos_ativos = self.finalizar_processos_concluidos(
                    processos_ativos
                )
                time.sleep(2)

            comando = self.montar_comando(servico, options)

            log_path = logs_dir / f"{timestamp}_{servico}.log"
            log_file = log_path.open("w", encoding="utf-8")

            self.stdout.write("")
            self.stdout.write(f"[INICIANDO] {servico}")
            self.stdout.write(f"Comando: {' '.join(comando)}")
            self.stdout.write(f"Log: {log_path}")

            processo = subprocess.Popen(
                comando,
                cwd=settings.BASE_DIR,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )

            processos_ativos.append(
                {
                    "servico": servico,
                    "processo": processo,
                    "log_file": log_file,
                    "log_path": log_path,
                }
            )

        while processos_ativos:
            processos_ativos = self.finalizar_processos_concluidos(
                processos_ativos
            )
            time.sleep(2)

        self.stdout.write("")
        self.stdout.write("=" * 100)
        self.stdout.write("Execução paralela finalizada.")
        self.stdout.write("=" * 100)