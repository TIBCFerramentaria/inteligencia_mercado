from django.core.management.base import BaseCommand
from django.utils import timezone

from mercado.coletores.loja_mecanico import coletar_mais_vendidos
from mercado.models import (
    SiteMonitorado,
    Categoria,
    Marca,
    ProdutoColetado,
    ColetaProduto,
    ExecucaoColeta,
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
            "--max-paginas",
            type=int,
            default=20,
            help="Quantidade máxima de páginas a coletar.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra os produtos encontrados, sem salvar no banco.",
        )
        parser.add_argument(
            "--url",
            type=str,
            default=None,
            help="URL base da página de produtos da Loja do Mecânico.",
        )

        parser.add_argument(
            "--fonte",
            type=str,
            default=None,
            help="Nome descritivo da fonte coletada. Exemplo: Furadeiras, Solda, Ferramentas manuais.",
        )

    def handle(self, *args, **options):
        limite = options["limite"]
        dry_run = options["dry_run"]
        max_paginas = options["max_paginas"]
        url_base = options.get("url")
        nome_fonte = options.get("fonte")

        site, _criado_site = SiteMonitorado.objects.get_or_create(
            nome="Loja do Mecânico",
            defaults={
                "url_base": "https://www.lojadomecanico.com.br",
                "ativo": True,
                "observacao": "Site coletado automaticamente pelo sistema.",
            },
        )

        execucao = ExecucaoColeta.objects.create(
            site=site,
            tipo_coleta="MAIS_VENDIDOS",
            nome_fonte="Mais vendidos",
            url_base="https://www.lojadomecanico.com.br/hotsite/maisvendidos",
            limite_solicitado=limite,
            max_paginas=max_paginas,
            dry_run=dry_run,
            status="EM_EXECUCAO",
        )

        produtos_novos = 0
        produtos_atualizados = 0
        coletas_gravadas = 0

        try:
            self.stdout.write(
                f"Iniciando coleta da Loja do Mecânico. "
                f"Fonte: {nome_fonte or 'Mais vendidos'}. "
                f"URL: {url_base or 'Mais vendidos padrão'}. "
                f"Limite: {limite}. "
                f"Máximo de páginas: {max_paginas}. "
                f"Dry-run: {dry_run}"
            )

            produtos = coletar_mais_vendidos(
                limite=limite,
                max_paginas=max_paginas,
                url_base=url_base,
                nome_fonte=nome_fonte,
            )

            execucao.produtos_encontrados = len(produtos)
            execucao.save()

            self.stdout.write(
                self.style.SUCCESS(f"Produtos encontrados: {len(produtos)}")
            )

            if not produtos:
                execucao.status = "SEM_DADOS"
                execucao.data_fim = timezone.now()
                execucao.save()

                self.stdout.write(
                    self.style.WARNING("Nenhum produto encontrado na coleta.")
                )
                return

            if dry_run:
                for produto in produtos:
                    self.stdout.write("-" * 80)
                    self.stdout.write(f"Ranking: {produto.get('ranking_geral')}")
                    self.stdout.write(f"Nome: {produto.get('nome_original')}")
                    self.stdout.write(f"Marca: {produto.get('marca_nome')}")
                    self.stdout.write(f"Código fabricante: {produto.get('codigo_fabricante')}")
                    self.stdout.write(f"Código site: {produto.get('codigo_site')}")
                    self.stdout.write(f"EAN: {produto.get('ean')}")
                    self.stdout.write(f"Estoque: {produto.get('estoque')}")
                    self.stdout.write(f"Preço atual: {produto.get('preco_atual')}")
                    self.stdout.write(f"Preço antigo: {produto.get('preco_antigo')}")
                    self.stdout.write(f"Desconto: {produto.get('desconto_percentual')}")
                    self.stdout.write(f"Preço a prazo: {produto.get('preco_prazo')}")
                    self.stdout.write(f"Parcelas: {produto.get('quantidade_parcelas')}")
                    self.stdout.write(f"Valor parcela: {produto.get('valor_parcela')}")
                    self.stdout.write(f"Nota: {produto.get('nota_media')}")
                    self.stdout.write(f"Avaliações: {produto.get('quantidade_avaliacoes')}")
                    self.stdout.write(f"URL: {produto.get('url')}")

                execucao.status = "SUCESSO"
                execucao.data_fim = timezone.now()
                execucao.produtos_novos = 0
                execucao.produtos_atualizados = 0
                execucao.coletas_gravadas = 0
                execucao.save()

                self.stdout.write(
                    self.style.WARNING("Dry-run finalizado. Nada foi salvo no banco.")
                )
                return

            categoria, _criado_categoria = Categoria.objects.get_or_create(
                nome=nome_fonte or "Mais vendidos - Loja do Mecânico"
            )

            for item in produtos:
                marca = None
                marca_nome = item.get("marca_nome")

                if marca_nome:
                    marca, _criado_marca = Marca.objects.get_or_create(
                        nome=marca_nome.upper()
                    )

                defaults = {
                    "categoria": categoria,
                    "marca": marca,
                    "nome_original": item.get("nome_original"),
                    "codigo_site": item.get("codigo_site"),
                    "codigo_fabricante": item.get("codigo_fabricante"),
                    "ativo": True,
                }

                if item.get("ean"):
                    defaults["ean"] = item.get("ean")

                produto, criado = ProdutoColetado.objects.update_or_create(
                    site=site,
                    url=item.get("url"),
                    defaults=defaults,
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
                    estoque=item.get("estoque"),
                    texto_disponibilidade=item.get("texto_disponibilidade"),
                    observacao=f"Coleta automática. Fonte: {nome_fonte or 'Mais vendidos'}. URL base: {url_base or 'Mais vendidos padrão'}.",
                )

                coletas_gravadas += 1

            execucao.produtos_novos = produtos_novos
            execucao.produtos_atualizados = produtos_atualizados
            execucao.coletas_gravadas = coletas_gravadas
            execucao.status = "SUCESSO"
            execucao.data_fim = timezone.now()
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
            execucao.produtos_novos = produtos_novos
            execucao.produtos_atualizados = produtos_atualizados
            execucao.coletas_gravadas = coletas_gravadas
            execucao.save()

            self.stdout.write(
                self.style.ERROR(f"Erro durante a coleta: {erro}")
            )

            raise