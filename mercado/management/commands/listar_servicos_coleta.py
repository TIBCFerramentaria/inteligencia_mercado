from django.core.management.base import BaseCommand
from django.db.models import Count, Max, Q

from mercado.models import AlvoColeta


class Command(BaseCommand):
    help = "Lista os serviços de coleta cadastrados e sua situação geral."

    def add_arguments(self, parser):
        parser.add_argument(
            "--servico",
            type=str,
            default=None,
            help="Filtra um serviço específico. Ex: servico_01",
        )

    def handle(self, *args, **options):
        servico = options.get("servico")

        alvos = AlvoColeta.objects.all()

        if servico:
            alvos = alvos.filter(servico_coleta=servico)

        resumo = (
            alvos.values("servico_coleta")
            .annotate(
                total_alvos=Count("id"),
                alvos_ativos=Count("id", filter=Q(ativo=True)),
                alvos_inativos=Count("id", filter=Q(ativo=False)),
                ultima_execucao=Max("ultima_execucao"),
            )
            .order_by("servico_coleta")
        )

        if not resumo:
            self.stdout.write(
                self.style.WARNING("Nenhum serviço de coleta encontrado.")
            )
            return

        self.stdout.write("=" * 100)
        self.stdout.write("RESUMO DOS SERVIÇOS DE COLETA")
        self.stdout.write("=" * 100)

        for item in resumo:
            servico_nome = item["servico_coleta"] or "sem_servico"

            alvos_do_servico = alvos.filter(servico_coleta=item["servico_coleta"])

            total_sucesso = alvos_do_servico.filter(
                ultima_situacao=AlvoColeta.SituacaoUltimaExecucao.SUCESSO
            ).count()

            total_erro = alvos_do_servico.filter(
                ultima_situacao=AlvoColeta.SituacaoUltimaExecucao.ERRO
            ).count()

            total_pendente = alvos_do_servico.filter(
                ultima_situacao=AlvoColeta.SituacaoUltimaExecucao.PENDENTE
            ).count()

            self.stdout.write("")
            self.stdout.write(f"Serviço: {servico_nome}")
            self.stdout.write("-" * 100)
            self.stdout.write(f"Total de alvos: {item['total_alvos']}")
            self.stdout.write(f"Alvos ativos: {item['alvos_ativos']}")
            self.stdout.write(f"Alvos inativos: {item['alvos_inativos']}")
            self.stdout.write(f"Sucesso: {total_sucesso}")
            self.stdout.write(f"Erro: {total_erro}")
            self.stdout.write(f"Pendente: {total_pendente}")
            self.stdout.write(f"Última execução: {item['ultima_execucao']}")

            self.stdout.write("")
            self.stdout.write("Alvos ativos deste serviço:")

            alvos_ativos = alvos_do_servico.filter(ativo=True).order_by(
                "ordem",
                "id",
            )

            if not alvos_ativos.exists():
                self.stdout.write("  Nenhum alvo ativo.")
                continue

            for alvo in alvos_ativos:
                self.stdout.write(
                    f"  [{alvo.id}] {alvo.nome} | "
                    f"Coletor: {alvo.get_coletor_display()} | "
                    f"Ordem: {alvo.ordem} | "
                    f"Situação: {alvo.get_ultima_situacao_display()} | "
                    f"Última execução: {alvo.ultima_execucao}"
                )

        self.stdout.write("")
        self.stdout.write("=" * 100)
        self.stdout.write("Fim da listagem.")
        self.stdout.write("=" * 100)