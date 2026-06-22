from django.core.management.base import BaseCommand

from mercado.coletores.fg_ferramentas import coletar_produtos_fg
from mercado.models import (
    SiteMonitorado,
    ProdutoColetado,
    ColetaProduto,
    Marca,
)


def obter_site_monitorado():
    campos = {campo.name for campo in SiteMonitorado._meta.fields}

    defaults = {}

    if "url_base" in campos:
        defaults["url_base"] = "https://www.fg.com.br"

    if "dominio" in campos:
        defaults["dominio"] = "fg.com.br"

    if "ativo" in campos:
        defaults["ativo"] = True

    site, criado = SiteMonitorado.objects.get_or_create(
        nome="FG - Ferramentas Gerais",
        defaults=defaults,
    )

    return site


def obter_marca(nome_marca):
    nome_marca = (nome_marca or "").strip()

    if not nome_marca:
        return None

    campos = {campo.name for campo in Marca._meta.fields}

    defaults = {}

    if "ativo" in campos:
        defaults["ativo"] = True

    marca, criado = Marca.objects.get_or_create(
        nome=nome_marca,
        defaults=defaults,
    )

    return marca


class Command(BaseCommand):
    help = "Coleta produtos do site FG - Ferramentas Gerais."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            required=True,
            help="URL da categoria/listagem da FG.",
        )

        parser.add_argument(
            "--fonte",
            type=str,
            default="FG - Ferramentas Gerais",
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
            f"Iniciando coleta FG. "
            f"Fonte: {fonte}. URL: {url}. Limite: {limite}. "
            f"Máximo de páginas: {max_paginas}. Dry-run: {dry_run}"
        )

        produtos = coletar_produtos_fg(
            url=url,
            limite=limite,
            max_paginas=max_paginas,
        )

        self.stdout.write("")
        self.stdout.write(f"Produtos encontrados: {len(produtos)}")

        if dry_run:
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

            return

        site = obter_site_monitorado()

        salvos = 0

        for indice, item in enumerate(produtos, start=1):
            url_produto = item.get("url") or ""
            codigo_site = item.get("codigo_site") or ""
            nome = item.get("nome") or item.get("nome_original") or ""

            if not url_produto and not codigo_site:
                self.stdout.write(
                    self.style.WARNING(
                        f"Produto ignorado por falta de URL e código: {nome}"
                    )
                )
                continue

            marca = obter_marca(item.get("marca_nome"))

            defaults_produto = {
                "nome_original": nome,
                "codigo_site": codigo_site,
                "codigo_fabricante": item.get("codigo_fabricante") or "",
                "ean": item.get("ean") or "",
                "status_vinculo": "PENDENTE",
                "ativo": True,
            }

            if marca:
                defaults_produto["marca"] = marca

            if url_produto:
                produto_coletado, criado = ProdutoColetado.objects.update_or_create(
                    site=site,
                    url=url_produto,
                    defaults=defaults_produto,
                )
            else:
                produto_coletado, criado = ProdutoColetado.objects.update_or_create(
                    site=site,
                    codigo_site=codigo_site,
                    defaults=defaults_produto,
                )

            ColetaProduto.objects.create(
                produto=produto_coletado,
                preco_atual=item.get("preco_atual"),
                preco_antigo=item.get("preco_antigo"),
                preco_prazo=item.get("preco_prazo"),
                quantidade_parcelas=item.get("quantidade_parcelas"),
                valor_parcela=item.get("valor_parcela"),
                estoque=item.get("estoque"),
                disponivel=item.get("disponivel"),
                texto_disponibilidade=item.get("texto_disponibilidade") or "",
                ranking_categoria=item.get("ranking") or indice,
                ranking_geral=item.get("ranking") or indice,
                observacao=fonte,
            )

            salvos += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Produtos processados: {len(produtos)}"))
        self.stdout.write(self.style.SUCCESS(f"Produtos salvos/atualizados no banco: {salvos}"))