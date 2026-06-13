from django.contrib import admin
from .models import (
    SiteMonitorado,
    Categoria,
    Marca,
    FabricanteImportador,
    ProdutoReferencia,
    ProdutoColetado,
    ColetaProduto,
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