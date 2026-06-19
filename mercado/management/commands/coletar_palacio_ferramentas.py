from django.core.management.base import BaseCommand

from mercado.coletores.palacio_ferramentas import coletar_produtos_palacio_ferramentas


class Command(BaseCommand):
    help = "Coleta produtos do site Palácio das Ferramentas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            required=True,
            help="URL da categoria/listagem do Palácio das Ferramentas.",
        )

        parser.add_argument(
            "--fonte",
            type=str,
            default="Palácio das Ferramentas",
            help="Nome da fonte da coleta.",
        )

        parser.add_argument(
            "--limite",
            type=int,
            default=20,
            help="Quantidade máxima de produtos.",
        )

        parser.add_argument(
            "--max-paginas",
            type=int,
            default=1,
            help="Quantidade máxima de páginas.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra os produtos coletados, sem salvar no banco.",
        )

    def handle(self, *args, **options):
        url = options["url"]
        fonte = options["fonte"]
        limite = options["limite"]
        max_paginas = options["max_paginas"]
        dry_run = options["dry_run"]

        self.stdout.write(
            f"Iniciando coleta do Palácio das Ferramentas. "
            f"Fonte: {fonte}. URL: {url}. Limite: {limite}. "
            f"Máximo de páginas: {max_paginas}. Dry-run: {dry_run}"
        )

        produtos = coletar_produtos_palacio_ferramentas(
            url=url,
            limite=limite,
            max_paginas=max_paginas,
        )

        self.stdout.write("")
        self.stdout.write(f"Produtos encontrados: {len(produtos)}")

        for indice, produto in enumerate(produtos, start=1):
            self.stdout.write("-" * 80)
            self.stdout.write(
                f"Produto {indice}: {produto.get('nome') or produto.get('nome_original')}"
            )
            self.stdout.write(f"URL: {produto.get('url')}")
            self.stdout.write(f"Código site: {produto.get('codigo_site')}")
            self.stdout.write(f"Marca: {produto.get('marca_nome')}")
            self.stdout.write(f"Código fabricante: {produto.get('codigo_fabricante')}")
            self.stdout.write(f"EAN: {produto.get('ean')}")
            self.stdout.write(f"Preço atual: {produto.get('preco_atual')}")
            self.stdout.write(f"Preço antigo: {produto.get('preco_antigo')}")
            self.stdout.write(f"Preço a prazo: {produto.get('preco_prazo')}")
            self.stdout.write(f"Parcelas: {produto.get('quantidade_parcelas')}")
            self.stdout.write(f"Valor parcela: {produto.get('valor_parcela')}")
            self.stdout.write(f"Ranking: {produto.get('ranking') or indice}")
            self.stdout.write(f"Estoque: {produto.get('estoque')}")
            self.stdout.write(f"Disponível: {produto.get('disponivel')}")
            self.stdout.write(f"Texto disponibilidade: {produto.get('texto_disponibilidade')}")

        if not dry_run:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Nesta primeira versão, o comando ainda não grava no banco. "
                    "Vamos validar a extração primeiro e depois ativar a gravação."
                )
            )