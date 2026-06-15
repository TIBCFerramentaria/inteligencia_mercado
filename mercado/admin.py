from django.contrib import admin
from .models import (
    SiteMonitorado,
    Categoria,
    Marca,
    FabricanteImportador,
    ProdutoReferencia,
    ProdutoColetado,
    ColetaProduto,
    ExecucaoColeta,
    AlvoColeta,
)


@admin.register(SiteMonitorado)
class SiteMonitoradoAdmin(admin.ModelAdmin):
    list_display = ("nome", "url_base", "ativo", "criado_em")
    search_fields = ("nome", "url_base")
    list_filter = ("ativo",)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria_pai", "criado_em")
    search_fields = ("nome",)
    list_filter = ("categoria_pai",)


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nome", "criado_em")
    search_fields = ("nome",)


@admin.register(FabricanteImportador)
class FabricanteImportadorAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "site_oficial", "pais_origem", "atualizado_em")
    search_fields = ("nome", "site_oficial", "pais_origem")
    list_filter = ("tipo",)


@admin.register(ProdutoReferencia)
class ProdutoReferenciaAdmin(admin.ModelAdmin):
    list_display = (
        "nome_referencia",
        "marca",
        "fabricante_importador",
        "categoria",
        "codigo_fabricante",
        "ean",
        "fonte_validacao",
        "status_validacao",
        "ativo",
        "atualizado_em",
    )
    search_fields = (
        "nome_referencia",
        "codigo_fabricante",
        "ean",
        "url_oficial",
    )
    list_filter = (
        "marca",
        "fabricante_importador",
        "categoria",
        "fonte_validacao",
        "status_validacao",
        "ativo",
    )


@admin.register(ProdutoColetado)
class ProdutoColetadoAdmin(admin.ModelAdmin):
    list_display = (
        "nome_original",
        "produto_referencia",
        "site",
        "marca",
        "categoria",
        "codigo_site",
        "codigo_fabricante",
        "ean",
        "status_vinculo",
        "ativo",
        "atualizado_em",
    )
    search_fields = (
        "nome_original",
        "produto_referencia__nome_referencia",
        "codigo_site",
        "codigo_fabricante",
        "ean",
        "url",
    )
    list_filter = (
        "site",
        "marca",
        "categoria",
        "status_vinculo",
        "ativo",
    )


@admin.register(ColetaProduto)
class ColetaProdutoAdmin(admin.ModelAdmin):
    list_display = (
        "produto",
        "data_coleta",
        "preco_atual",
        "preco_prazo",
        "quantidade_parcelas",
        "valor_parcela",
        "preco_antigo",
        "desconto_percentual",
        "nota_media",
        "quantidade_avaliacoes",
        "ranking_geral",
        "ranking_categoria",
        "disponivel",
    )
    search_fields = (
        "produto__nome_original",
        "produto__produto_referencia__nome_referencia",
        "produto__codigo_fabricante",
        "produto__ean",
    )
    list_filter = ("produto__site", "disponivel", "data_coleta")

@admin.register(ExecucaoColeta)
class ExecucaoColetaAdmin(admin.ModelAdmin):
    list_display = [
        "data_inicio",
        "data_fim",
        "site",
        "tipo_coleta",
        "nome_fonte",
        "status",
        "dry_run",
        "limite_solicitado",
        "max_paginas",
        "produtos_encontrados",
        "produtos_novos",
        "produtos_atualizados",
        "coletas_gravadas",
        "duracao_segundos",
    ]

    list_filter = [
        "status",
        "tipo_coleta",
        "dry_run",
        "site",
        "data_inicio",
    ]

    search_fields = [
        "nome_fonte",
        "url_base",
        "mensagem_erro",
        "site__nome",
    ]

    readonly_fields = [
        "data_inicio",
        "data_fim",
        "criado_em",
        "atualizado_em",
        "duracao_segundos",
    ]

    ordering = ["-data_inicio"]

@admin.register(AlvoColeta)
class AlvoColetaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "coletor",
        "nome_fonte",
        "ativo",
        "limite",
        "max_paginas",
        "ordem",
        "ultima_situacao",
        "ultima_execucao",
    )

    list_filter = (
        "coletor",
        "ativo",
        "ultima_situacao",
        "site_monitorado",
        "categoria",
    )

    search_fields = (
        "nome",
        "nome_fonte",
        "url",
    )

    ordering = (
        "ordem",
        "id",
    )

    readonly_fields = (
        "ultima_execucao",
        "ultima_situacao",
        "ultima_mensagem",
        "criado_em",
        "atualizado_em",
    )