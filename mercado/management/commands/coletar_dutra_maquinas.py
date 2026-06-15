from django.core.management.base import BaseCommand
from django.utils import timezone

from mercado.coletores.dutra_maquinas import coletar_produtos_dutra
from mercado.models import (
    SiteMonitorado,
    Categoria,
    Marca,
    ProdutoColetado,
    ColetaProduto,
    ExecucaoColeta,
)


class Command(BaseCommand):
    help = "Coleta produtos da Dutra Máquinas a partir de uma URL pública."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            required=True,
            help="URL da página de categoria, busca ou listagem da Dutra Máquinas.",
        )

        parser.add_argument(
            "--fonte",
            type=str,
            default="Dutra Máquinas",
            help="Nome descritivo da fonte coletada.",
        )

        parser.add_argument(
            "--limite",
            type=int,
            default=None,
            help="Quantidade máxima de produtos para coletar.",
        )

        parser.add_argument(
            "--max-paginas",
            type=int,
            default=20,
            help="Quantidade máxima de páginas para percorrer.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa sem gravar no banco de dados.",
        )

    def handle(self, *args, **options):
        url_base = options.get("url")
        nome_fonte = options.get("fonte")
        limite = options.get("limite")
        max_paginas = options.get("max_paginas")
        dry_run = options.get("dry_run")

        self.stdout.write(
            f"Iniciando coleta da Dutra Máquinas. "
            f"Fonte: {nome_fonte}. "
            f"URL: {url_base}. "
            f"Limite: {limite}. "
            f"Máximo de páginas: {max_paginas}. "
            f"Dry-run: {dry_run}"
        )

        site, _criado = SiteMonitorado.objects.get_or_create(
            nome="Dutra Máquinas",
            defaults={
                "url_base": "https://www.dutramaquinas.com.br/",
                "ativo": True,
            },
        )

        execucao = ExecucaoColeta.objects.create(
            site=site,
            nome_fonte=nome_fonte,
            data_inicio=timezone.now(),
            status="EM_EXECUCAO",
        )

        produtos_novos = 0
        produtos_atualizados = 0
        coletas_gravadas = 0

        try:
            produtos = coletar_produtos_dutra(
                url_base=url_base,
                limite=limite,
                max_paginas=max_paginas,
                nome_fonte=nome_fonte,
            )

            execucao.produtos_encontrados = len(produtos)

            self.stdout.write(f"Produtos encontrados: {len(produtos)}")

            if dry_run:
                for indice, item in enumerate(produtos, start=1):
                    self.stdout.write("-" * 80)
                    self.stdout.write(f"Produto {indice}: {item.get('nome_original')}")
                    self.stdout.write(f"URL: {item.get('url')}")
                    self.stdout.write(f"Código site: {item.get('codigo_site')}")
                    self.stdout.write(f"Marca: {item.get('marca_nome')}")
                    self.stdout.write(f"Código fabricante: {item.get('codigo_fabricante')}")
                    self.stdout.write(f"Preço atual: {item.get('preco_atual')}")
                    self.stdout.write(f"Preço antigo: {item.get('preco_antigo')}")
                    self.stdout.write(f"Preço a prazo: {item.get('preco_prazo')}")
                    self.stdout.write(f"Parcelas: {item.get('quantidade_parcelas')}")
                    self.stdout.write(f"Valor parcela: {item.get('valor_parcela')}")
                    self.stdout.write(f"Ranking: {item.get('ranking_geral')}")

                execucao.status = "DRY_RUN"
                execucao.data_fim = timezone.now()
                execucao.save()

                return

            for item in produtos:
                categoria = None

                if nome_fonte:
                    categoria, _ = Categoria.objects.get_or_create(
                        nome=nome_fonte
                    )

                marca = None

                if item.get("marca_nome"):
                    marca, _ = Marca.objects.get_or_create(
                        nome=item.get("marca_nome")
                    )

                produto, criado = ProdutoColetado.objects.update_or_create(
                    site=site,
                    url=item.get("url"),
                    defaults={
                        "nome_original": item.get("nome_original"),
                        "codigo_site": item.get("codigo_site"),
                        "codigo_fabricante": item.get("codigo_fabricante"),
                        "ean": item.get("ean"),
                        "marca": marca,
                        "categoria": categoria,
                        "ativo": True,
                    },
                )

                if criado:
                    produtos_novos += 1
                else:
                    produtos_atualizados += 1

                ColetaProduto.objects.create(
                    produto=produto,
                    preco_atual=item.get("preco_atual"),
                    preco_antigo=item.get("preco_antigo"),
                    preco_prazo=item.get("preco_prazo"),
                    quantidade_parcelas=item.get("quantidade_parcelas"),
                    valor_parcela=item.get("valor_parcela"),
                    desconto_percentual=item.get("desconto_percentual"),
                    nota_media=item.get("nota_media"),
                    quantidade_avaliacoes=item.get("quantidade_avaliacoes"),
                    ranking_geral=item.get("ranking_geral"),
                    ranking_categoria=item.get("ranking_categoria"),
                    disponivel=item.get("disponivel", True),
                    texto_disponibilidade=item.get("texto_disponibilidade"),
                    observacao=f"Coleta automática. Fonte: {nome_fonte}. URL base: {url_base}.",
                )

                coletas_gravadas += 1

            execucao.status = "SUCESSO"
            execucao.data_fim = timezone.now()
            execucao.produtos_novos = produtos_novos
            execucao.produtos_atualizados = produtos_atualizados
            execucao.coletas_criadas = coletas_gravadas
            execucao.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Coleta concluída. "
                    f"Produtos encontrados: {len(produtos)}. "
                    f"Produtos novos: {produtos_novos}. "
                    f"Produtos atualizados: {produtos_atualizados}. "
                    f"Coletas criadas: {coletas_gravadas}."
                )
            )

        except Exception as erro:
            execucao.status = "ERRO"
            execucao.data_fim = timezone.now()
            execucao.mensagem_erro = str(erro)
            execucao.save()

            self.stdout.write(
                self.style.ERROR(f"Erro durante a coleta: {erro}")
            )

            raise