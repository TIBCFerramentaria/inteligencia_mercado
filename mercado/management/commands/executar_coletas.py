import traceback

from django.core.management import call_command
from django.db import close_old_connections, connections
from django.core.management.base import BaseCommand
from django.utils import timezone

from mercado.models import AlvoColeta


class Command(BaseCommand):
    help = "Executa automaticamente todos os alvos de coleta ativos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa sem gravar os produtos no banco.",
        )

        parser.add_argument(
            "--coletor",
            type=str,
            choices=[
                AlvoColeta.Coletor.LOJA_MECANICO,
                AlvoColeta.Coletor.DUTRA_MAQUINAS,
            ],
            help="Executa apenas um tipo de coletor.",
        )

        parser.add_argument(
            "--servico",
            type=str,
            default=None,
            help="Executa apenas os alvos vinculados a um serviço específico. Ex: servico_01",
        )

        parser.add_argument(
            "--limite",
            type=int,
            help="Sobrescreve o limite configurado nos alvos.",
        )

        parser.add_argument(
            "--max-paginas",
            type=int,
            dest="max_paginas",
            help="Sobrescreve o máximo de páginas configurado nos alvos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        coletor_filtrado = options.get("coletor")
        limite_override = options.get("limite")
        max_paginas_override = options.get("max_paginas")

        alvos = AlvoColeta.objects.filter(ativo=True).order_by("servico_coleta", "ordem", "id")

        coletor = options.get("coletor")
        servico = options.get("servico")

        if coletor_filtrado:
            alvos = alvos.filter(coletor=coletor_filtrado)

        if servico:
            alvos = alvos.filter(servico_coleta=servico)

        total_alvos = alvos.count()

        self.stdout.write("=" * 80)
        self.stdout.write(f"[INFO] Alvos ativos encontrados: {total_alvos}")
        self.stdout.write(f"[INFO] Dry-run: {dry_run}")
        self.stdout.write("=" * 80)

        if total_alvos == 0:
            self.stdout.write("[INFO] Nenhum alvo ativo para executar.")
            return

        mapa_comandos = {
            AlvoColeta.Coletor.LOJA_MECANICO: "coletar_loja_mecanico",
            AlvoColeta.Coletor.DUTRA_MAQUINAS: "coletar_dutra_maquinas",
            AlvoColeta.Coletor.FERRAMENTAS_KENNEDY: "coletar_ferramentas_kennedy",
            AlvoColeta.Coletor.PALACIO_FERRAMENTAS: "coletar_palacio_ferramentas",
            AlvoColeta.Coletor.FG_FERRAMENTAS: "coletar_fg",
        }

        sucessos = 0
        erros = 0

        for alvo in alvos:
            comando = mapa_comandos.get(alvo.coletor)

            if not comando:
                erros += 1
                mensagem = f"Coletor não configurado: {alvo.coletor}"

                self.stdout.write(self.style.ERROR(mensagem))

                if not dry_run:
                    alvo.ultima_execucao = timezone.now()
                    alvo.ultima_situacao = AlvoColeta.SituacaoUltimaExecucao.ERRO
                    alvo.ultima_mensagem = mensagem
                    connections.close_all()
                    close_old_connections()
                    alvo.save(
                        update_fields=[
                            "ultima_execucao",
                            "ultima_situacao",
                            "ultima_mensagem",
                            "atualizado_em",
                        ]
                    )

                continue

            limite = limite_override or alvo.limite
            max_paginas = max_paginas_override or alvo.max_paginas

            self.stdout.write("")
            self.stdout.write("=" * 80)
            self.stdout.write(f"[INFO] Executando alvo: {alvo.nome}")
            self.stdout.write(f"[INFO] Coletor: {alvo.get_coletor_display()}")
            self.stdout.write(f"[INFO] Fonte: {alvo.nome_fonte}")
            self.stdout.write(f"[INFO] URL: {alvo.url}")
            self.stdout.write(f"[INFO] Limite: {limite}")
            self.stdout.write(f"[INFO] Máximo de páginas: {max_paginas}")
            self.stdout.write("=" * 80)

            try:
                call_command(
                    comando,
                    url=alvo.url,
                    fonte=alvo.nome_fonte,
                    limite=limite,
                    max_paginas=max_paginas,
                    dry_run=dry_run,
                )

                sucessos += 1
                mensagem = "Coleta executada com sucesso."

                self.stdout.write(self.style.SUCCESS(f"[OK] {mensagem}"))

                if not dry_run:
                    alvo.ultima_execucao = timezone.now()
                    alvo.ultima_situacao = AlvoColeta.SituacaoUltimaExecucao.SUCESSO
                    alvo.ultima_mensagem = mensagem
                    connections.close_all()
                    close_old_connections()
                    alvo.save(
                        update_fields=[
                            "ultima_execucao",
                            "ultima_situacao",
                            "ultima_mensagem",
                            "atualizado_em",
                        ]
                    )

            except Exception as erro:
                erros += 1

                mensagem = f"Erro ao executar coleta: {erro}"
                detalhe = traceback.format_exc()

                self.stdout.write(self.style.ERROR(f"[ERRO] {mensagem}"))
                self.stdout.write(self.style.ERROR(detalhe))

                if not dry_run:
                    alvo.ultima_execucao = timezone.now()
                    alvo.ultima_situacao = AlvoColeta.SituacaoUltimaExecucao.ERRO
                    alvo.ultima_mensagem = detalhe
                    connections.close_all()
                    close_old_connections()
                    alvo.save(
                        update_fields=[
                            "ultima_execucao",
                            "ultima_situacao",
                            "ultima_mensagem",
                            "atualizado_em",
                        ]
                    )

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write("[INFO] Execução finalizada.")
        self.stdout.write(f"[INFO] Sucessos: {sucessos}")
        self.stdout.write(f"[INFO] Erros: {erros}")
        self.stdout.write("=" * 80)

