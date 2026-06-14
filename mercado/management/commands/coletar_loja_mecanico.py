from django.core.management.base import BaseCommand

from mercado.coletores.loja_mecanico import coletar_mais_vendidos
from mercado.models import (
    SiteMonitorado,
    Categoria,
    Marca,
    ProdutoColetado,
    ColetaProduto,
)


class Command(BaseCommand):
    help = "Coleta produtos mais vendidos da Loja do Mecânico."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=20,
            help="Quantidade máxima de produtos a coletar.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra os produtos encontrados, sem salvar no banco.",
        )

    def handle(self, *args, **options):
        limite = options["limite"]
        dry_run = options["dry_run"]

        self.stdout.write(
            self.style.WARNING(
                f"Iniciando coleta da Loja do Mecânico. Limite: {limite}. Dry-run: {dry_run}"
            )
        )

        produtos = coletar_mais_vendidos(limite=limite)

        self.stdout.write(
            self.style.SUCCESS(f"Produtos encontrados: {len(produtos)}")
        )

        if dry_run:
            for produto in produtos:
                self.stdout.write("-" * 80)
                self.stdout.write(f"Ranking: {produto['ranking_geral']}")
                self.stdout.write(f"Nome: {produto['nome_original']}")
                self.stdout.write(f"Marca: {produto['marca_nome']}")
                self.stdout.write(f"Código fabricante: {produto['codigo_fabricante']}")
                self.stdout.write(f"Código site: {produto['codigo_site']}")
                self.stdout.write(f"Preço atual: {produto['preco_atual']}")
                self.stdout.write(f"Preço antigo: {produto['preco_antigo']}")
                self.stdout.write(f"Desconto: {produto['desconto_percentual']}")
                self.stdout.write(f"Nota: {produto['nota_media']}")
                self.stdout.write(f"Avaliações: {produto['quantidade_avaliacoes']}")
                self.stdout.write(f"URL: {produto['url']}")

            self.stdout.write(
                self.style.WARNING("Dry-run finalizado. Nada foi salvo no banco.")
            )
            return

        site, _criado = SiteMonitorado.objects.get_or_create(
            nome="Loja do Mecânico",
            defaults={
                "url_base": "https://www.lojadomecanico.com.br",
                "ativo": True,
                "observacao": "Site coletado automaticamente pelo sistema.",
            },
        )

        categoria, _criado = Categoria.objects.get_or_create(
            nome="Mais vendidos - Loja do Mecânico"
        )

        total_salvos = 0
        total_coletas = 0

        for item in produtos:
            marca = None

            if item["marca_nome"]:
                marca, _criado = Marca.objects.get_or_create(
                    nome=item["marca_nome"].upper()
                )

            produto, _criado = ProdutoColetado.objects.update_or_create(
                site=site,
                url=item["url"],
                defaults={
                    "categoria": categoria,
                    "marca": marca,
                    "nome_original": item["nome_original"],
                    "codigo_site": item["codigo_site"],
                    "codigo_fabricante": item["codigo_fabricante"],
                    "ean": None,
                    "status_vinculo": "PENDENTE",
                    "ativo": True,
                },
            )

            ColetaProduto.objects.create(
                produto=produto,
                preco_atual=item["preco_atual"],
                preco_antigo=item["preco_antigo"],
                desconto_percentual=item["desconto_percentual"],
                nota_media=item["nota_media"],
                quantidade_avaliacoes=item["quantidade_avaliacoes"],
                ranking_geral=item["ranking_geral"],
                ranking_categoria=None,
                disponivel=item["disponivel"],
                texto_disponibilidade=item["texto_disponibilidade"],
                observacao="Coleta automática da página pública de mais vendidos.",
            )

            total_salvos += 1
            total_coletas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Coleta concluída. Produtos processados: {total_salvos}. Coletas criadas: {total_coletas}."
            )
        )