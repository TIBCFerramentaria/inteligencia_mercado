from django.core.management.base import BaseCommand
from django.utils import timezone

from mercado.coletores.ferramentas_kennedy import coletar_produtos_ferramentas_kennedy
from mercado.models import (
    SiteMonitorado,
    Categoria,
    Marca,
    ProdutoColetado,
    ColetaProduto,
    ExecucaoColeta,
)


class Command(BaseCommand):
    help = "Coleta produtos da Ferramentas Kennedy a partir de uma URL pública."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            required=True,
            help="URL da página de categoria, busca ou listagem da Ferramentas Kennedy.",
        )

        parser.add_argument(
            "--fonte",
            type=str,
            default="Ferramentas Kennedy",
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
            f"Iniciando coleta da Ferramentas Kennedy. "
            f"Fonte: {nome_fonte}. "
            f"URL: {url_base}. "
            f"Limite: {limite}. "
            f"Máximo de páginas: {max_paginas}. "
            f"Dry-run: {dry_run}"
        )

        site, _criado = SiteMonitorado.objects.get_or_create(
            nome="Ferramentas Kennedy",
            defaults={
                "url_base": "https://www.ferramentaskennedy.com.br/",
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
            produtos = coletar_produtos_ferramentas_kennedy(
                url_base=url_base,
                limite=limite,
                max_paginas=max_paginas,
                nome_fonte=nome_fonte,
            )

            execucao.produtos_encontrados = len(produtos)

            self.stdout.write(f"Produtos encontrados: {len(produtos)}")

            if dry_run:
                self.stdout.write(f"Produtos encontrados: {len(produtos)}")

                for indice, produto in enumerate(produtos, start=1):
                    ranking = produto.get("ranking") or indice

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

                url_produto = item.get("url") or ""
                codigo_site = item.get("codigo_site") or ""

                if not url_produto and not codigo_site:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Produto ignorado por falta de URL e código: {item.get('nome') or item.get('nome_original')}"
                        )
                    )
                    continue

                defaults_produto = {
                    "nome_original": item.get("nome") or item.get("nome_original") or "",
                    "codigo_site": codigo_site,
                    "codigo_fabricante": item.get("codigo_fabricante") or codigo_site,
                    "ean": item.get("ean") or "",
                    "status_vinculo": "PENDENTE",
                    "ativo": True,
                }

                if marca:
                    defaults_produto["marca"] = marca

                if categoria:
                    defaults_produto["categoria"] = categoria

                if url_produto:
                    produto, criado = ProdutoColetado.objects.update_or_create(
                        site=site,
                        url=url_produto,
                        defaults=defaults_produto,
                    )
                else:
                    produto, criado = ProdutoColetado.objects.update_or_create(
                        site=site,
                        codigo_site=codigo_site,
                        defaults=defaults_produto,
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
                    ranking_geral=item.get("ranking"),
                    ranking_categoria=item.get("ranking"),
                    disponivel=item.get("disponivel", True),
                    estoque=item.get("estoque"),
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