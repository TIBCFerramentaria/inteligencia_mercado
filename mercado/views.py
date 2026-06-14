from difflib import SequenceMatcher
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from openpyxl import Workbook, load_workbook
from .models import (
    SiteMonitorado,
    Categoria,
    Marca,
    FabricanteImportador,
    ProdutoReferencia,
    ProdutoColetado,
    ColetaProduto,
)


def dashboard(request):
    contexto = {
        "total_sites": SiteMonitorado.objects.count(),
        "total_categorias": Categoria.objects.count(),
        "total_marcas": Marca.objects.count(),
        "total_fabricantes": FabricanteImportador.objects.count(),
        "total_referencias": ProdutoReferencia.objects.count(),
        "total_produtos": ProdutoColetado.objects.count(),
        "total_coletas": ColetaProduto.objects.count(),
        "ultimas_coletas": ColetaProduto.objects.select_related(
            "produto",
            "produto__site",
            "produto__marca",
            "produto__categoria",
            "produto__produto_referencia",
        ).order_by("-data_coleta")[:10],
    }

    return render(request, "mercado/dashboard.html", contexto)


def lista_produtos(request):
    produtos = ProdutoColetado.objects.select_related(
        "site",
        "marca",
        "categoria",
        "produto_referencia",
    ).all()

    busca = request.GET.get("busca", "")
    site_id = request.GET.get("site", "")
    marca_id = request.GET.get("marca", "")
    categoria_id = request.GET.get("categoria", "")

    if busca:
        produtos = produtos.filter(
            nome_original__icontains=busca
        ) | produtos.filter(
            codigo_fabricante__icontains=busca
        ) | produtos.filter(
            ean__icontains=busca
        ) | produtos.filter(
            produto_referencia__nome_referencia__icontains=busca
        ) | produtos.filter(
            produto_referencia__codigo_fabricante__icontains=busca
        ) | produtos.filter(
            produto_referencia__ean__icontains=busca
        )

    if site_id:
        produtos = produtos.filter(site_id=site_id)

    if marca_id:
        produtos = produtos.filter(marca_id=marca_id)

    if categoria_id:
        produtos = produtos.filter(categoria_id=categoria_id)

    contexto = {
        "produtos": produtos.distinct(),
        "sites": SiteMonitorado.objects.all(),
        "marcas": Marca.objects.all(),
        "categorias": Categoria.objects.all(),
        "busca": busca,
        "site_id": site_id,
        "marca_id": marca_id,
        "categoria_id": categoria_id,
    }

    return render(request, "mercado/lista_produtos.html", contexto)


def lista_referencias(request):
    referencias = ProdutoReferencia.objects.select_related(
        "marca",
        "categoria",
        "fabricante_importador",
    ).all()

    busca = request.GET.get("busca", "")
    marca_id = request.GET.get("marca", "")
    categoria_id = request.GET.get("categoria", "")
    fabricante_id = request.GET.get("fabricante", "")
    status_validacao = request.GET.get("status_validacao", "")

    if busca:
        referencias = referencias.filter(
            nome_referencia__icontains=busca
        ) | referencias.filter(
            codigo_fabricante__icontains=busca
        ) | referencias.filter(
            ean__icontains=busca
        ) | referencias.filter(
            url_oficial__icontains=busca
        )

    if marca_id:
        referencias = referencias.filter(marca_id=marca_id)

    if categoria_id:
        referencias = referencias.filter(categoria_id=categoria_id)

    if fabricante_id:
        referencias = referencias.filter(fabricante_importador_id=fabricante_id)

    if status_validacao:
        referencias = referencias.filter(status_validacao=status_validacao)

    contexto = {
        "referencias": referencias.distinct(),
        "marcas": Marca.objects.all(),
        "categorias": Categoria.objects.all(),
        "fabricantes": FabricanteImportador.objects.all(),
        "status_choices": ProdutoReferencia.STATUS_VALIDACAO_CHOICES,
        "busca": busca,
        "marca_id": marca_id,
        "categoria_id": categoria_id,
        "fabricante_id": fabricante_id,
        "status_validacao": status_validacao,
    }

    return render(request, "mercado/lista_referencias.html", contexto)


def ranking_mercado(request):
    coletas = ColetaProduto.objects.select_related(
        "produto",
        "produto__site",
        "produto__marca",
        "produto__categoria",
        "produto__produto_referencia",
    ).order_by("-data_coleta")

    busca = request.GET.get("busca", "")
    site_id = request.GET.get("site", "")
    marca_id = request.GET.get("marca", "")
    categoria_id = request.GET.get("categoria", "")
    somente_disponiveis = request.GET.get("somente_disponiveis", "")

    if busca:
        coletas = coletas.filter(
            produto__nome_original__icontains=busca
        ) | coletas.filter(
            produto__codigo_fabricante__icontains=busca
        ) | coletas.filter(
            produto__ean__icontains=busca
        ) | coletas.filter(
            produto__produto_referencia__nome_referencia__icontains=busca
        ) | coletas.filter(
            produto__produto_referencia__codigo_fabricante__icontains=busca
        ) | coletas.filter(
            produto__produto_referencia__ean__icontains=busca
        )

    if site_id:
        coletas = coletas.filter(produto__site_id=site_id)

    if marca_id:
        coletas = coletas.filter(produto__marca_id=marca_id)

    if categoria_id:
        coletas = coletas.filter(produto__categoria_id=categoria_id)

    if somente_disponiveis == "1":
        coletas = coletas.filter(disponivel=True)

    # Pega apenas a última coleta de cada produto.
    ultimas_por_produto = {}
    for coleta in coletas.distinct():
        if coleta.produto_id not in ultimas_por_produto:
            ultimas_por_produto[coleta.produto_id] = coleta

    ranking = list(ultimas_por_produto.values())

    # Ordena priorizando melhor ranking geral; quando não houver ranking, joga para o final.
    ranking.sort(
        key=lambda coleta: (
            coleta.ranking_geral if coleta.ranking_geral is not None else 999999,
            coleta.ranking_categoria if coleta.ranking_categoria is not None else 999999,
            coleta.preco_atual if coleta.preco_atual is not None else 999999999,
        )
    )

    contexto = {
        "ranking": ranking,
        "sites": SiteMonitorado.objects.all(),
        "marcas": Marca.objects.all(),
        "categorias": Categoria.objects.all(),
        "busca": busca,
        "site_id": site_id,
        "marca_id": marca_id,
        "categoria_id": categoria_id,
        "somente_disponiveis": somente_disponiveis,
        "total_ranking": len(ranking),
        "query_string": request.GET.urlencode(),
    }

    return render(request, "mercado/ranking_mercado.html", contexto)

def forca_marcas(request):
    coletas = ColetaProduto.objects.select_related(
        "produto",
        "produto__site",
        "produto__marca",
        "produto__categoria",
        "produto__produto_referencia",
        "produto__produto_referencia__fabricante_importador",
    ).order_by("-data_coleta")

    # Pega somente a última coleta de cada produto.
    ultimas_por_produto = {}
    for coleta in coletas:
        if coleta.produto_id not in ultimas_por_produto:
            ultimas_por_produto[coleta.produto_id] = coleta

    grupos = {}

    for coleta in ultimas_por_produto.values():
        produto = coleta.produto

        marca_nome = "Sem marca"
        fabricante_nome = "-"

        if produto.produto_referencia and produto.produto_referencia.marca:
            marca_nome = produto.produto_referencia.marca.nome
        elif produto.marca:
            marca_nome = produto.marca.nome

        if (
            produto.produto_referencia
            and produto.produto_referencia.fabricante_importador
        ):
            fabricante_nome = produto.produto_referencia.fabricante_importador.nome

        if marca_nome not in grupos:
            grupos[marca_nome] = {
                "marca": marca_nome,
                "fabricante": fabricante_nome,
                "qtd_produtos": 0,
                "qtd_vinculados": 0,
                "qtd_disponiveis": 0,
                "soma_precos": 0,
                "qtd_precos": 0,
                "soma_notas": 0,
                "qtd_notas": 0,
                "total_avaliacoes": 0,
                "soma_rankings": 0,
                "qtd_rankings": 0,
            }

        grupo = grupos[marca_nome]
        grupo["qtd_produtos"] += 1

        if produto.status_vinculo == "VINCULADO":
            grupo["qtd_vinculados"] += 1

        if coleta.disponivel:
            grupo["qtd_disponiveis"] += 1

        if coleta.preco_atual is not None:
            grupo["soma_precos"] += float(coleta.preco_atual)
            grupo["qtd_precos"] += 1

        if coleta.nota_media is not None:
            grupo["soma_notas"] += float(coleta.nota_media)
            grupo["qtd_notas"] += 1

        if coleta.quantidade_avaliacoes is not None:
            grupo["total_avaliacoes"] += coleta.quantidade_avaliacoes

        if coleta.ranking_geral is not None:
            grupo["soma_rankings"] += coleta.ranking_geral
            grupo["qtd_rankings"] += 1

    resultado = []

    for grupo in grupos.values():
        qtd_produtos = grupo["qtd_produtos"]

        preco_medio = None
        if grupo["qtd_precos"] > 0:
            preco_medio = grupo["soma_precos"] / grupo["qtd_precos"]

        nota_media = None
        if grupo["qtd_notas"] > 0:
            nota_media = grupo["soma_notas"] / grupo["qtd_notas"]

        ranking_medio = None
        if grupo["qtd_rankings"] > 0:
            ranking_medio = grupo["soma_rankings"] / grupo["qtd_rankings"]

        percentual_disponivel = 0
        if qtd_produtos > 0:
            percentual_disponivel = grupo["qtd_disponiveis"] / qtd_produtos

        percentual_vinculado = 0
        if qtd_produtos > 0:
            percentual_vinculado = grupo["qtd_vinculados"] / qtd_produtos

        # Score inicial de força da marca.
        # Este score será refinado depois com mais dados e mais sites.
        score = 0

        # Presença da marca no mercado monitorado.
        score += min(qtd_produtos * 5, 25)

        # Disponibilidade dos produtos.
        score += percentual_disponivel * 20

        # Qualidade percebida por nota.
        if nota_media is not None:
            score += (nota_media / 5) * 20

        # Volume de avaliações como sinal de histórico/demanda.
        score += min(grupo["total_avaliacoes"] / 1000 * 20, 20)

        # Ranking médio: quanto menor, melhor.
        if ranking_medio is not None:
            if ranking_medio <= 10:
                score += 15
            elif ranking_medio <= 50:
                score += 10
            elif ranking_medio <= 100:
                score += 6
            else:
                score += 3

        # Confiabilidade por vínculo com produto referência.
        score += percentual_vinculado * 20

        grupo["preco_medio"] = preco_medio
        grupo["nota_media"] = nota_media
        grupo["ranking_medio"] = ranking_medio
        grupo["score"] = round(score, 2)

        resultado.append(grupo)

    resultado.sort(key=lambda item: item["score"], reverse=True)

    contexto = {
        "marcas": resultado,
        "total_marcas": len(resultado),
    }

    return render(request, "mercado/forca_marcas.html", contexto)

def precos_referencias(request):
    coletas = ColetaProduto.objects.select_related(
        "produto",
        "produto__site",
        "produto__marca",
        "produto__categoria",
        "produto__produto_referencia",
        "produto__produto_referencia__marca",
        "produto__produto_referencia__categoria",
        "produto__produto_referencia__fabricante_importador",
    ).filter(
        produto__produto_referencia__isnull=False,
        preco_atual__isnull=False,
    )

    busca = request.GET.get("busca", "")
    site_id = request.GET.get("site", "")
    marca_id = request.GET.get("marca", "")
    categoria_id = request.GET.get("categoria", "")
    data_inicio = request.GET.get("data_inicio", "")
    data_fim = request.GET.get("data_fim", "")

    if busca:
        coletas = coletas.filter(
            Q(produto__produto_referencia__nome_referencia__icontains=busca)
            | Q(produto__produto_referencia__codigo_fabricante__icontains=busca)
            | Q(produto__produto_referencia__ean__icontains=busca)
            | Q(produto__nome_original__icontains=busca)
            | Q(produto__codigo_fabricante__icontains=busca)
            | Q(produto__ean__icontains=busca)
        )

    if site_id:
        coletas = coletas.filter(produto__site_id=site_id)

    if marca_id:
        coletas = coletas.filter(produto__produto_referencia__marca_id=marca_id)

    if categoria_id:
        coletas = coletas.filter(produto__produto_referencia__categoria_id=categoria_id)

    if data_inicio:
        coletas = coletas.filter(data_coleta__date__gte=data_inicio)

    if data_fim:
        coletas = coletas.filter(data_coleta__date__lte=data_fim)

    grupos = {}

    for coleta in coletas.order_by("produto__produto_referencia__nome_referencia", "data_coleta"):
        referencia = coleta.produto.produto_referencia
        preco = float(coleta.preco_atual)

        if referencia.id not in grupos:
            grupos[referencia.id] = {
                "referencia": referencia,
                "marca": referencia.marca.nome if referencia.marca else "-",
                "fabricante": (
                    referencia.fabricante_importador.nome
                    if referencia.fabricante_importador
                    else "-"
                ),
                "categoria": referencia.categoria.nome if referencia.categoria else "-",
                "sites": set(),
                "qtd_coletas": 0,
                "soma_precos": 0,
                "menor_preco": preco,
                "maior_preco": preco,
                "site_menor_preco": coleta.produto.site.nome,
                "site_maior_preco": coleta.produto.site.nome,
                "ultima_coleta": coleta.data_coleta,
            }

        grupo = grupos[referencia.id]

        grupo["sites"].add(coleta.produto.site.nome)
        grupo["qtd_coletas"] += 1
        grupo["soma_precos"] += preco

        if preco < grupo["menor_preco"]:
            grupo["menor_preco"] = preco
            grupo["site_menor_preco"] = coleta.produto.site.nome

        if preco > grupo["maior_preco"]:
            grupo["maior_preco"] = preco
            grupo["site_maior_preco"] = coleta.produto.site.nome

        if coleta.data_coleta > grupo["ultima_coleta"]:
            grupo["ultima_coleta"] = coleta.data_coleta

    resultado = []

    for grupo in grupos.values():
        preco_medio = grupo["soma_precos"] / grupo["qtd_coletas"]

        variacao_percentual = 0
        if grupo["menor_preco"] > 0:
            variacao_percentual = (
                (grupo["maior_preco"] - grupo["menor_preco"])
                / grupo["menor_preco"]
            ) * 100

        grupo["preco_medio"] = preco_medio
        grupo["variacao_percentual"] = variacao_percentual
        grupo["sites_texto"] = ", ".join(sorted(grupo["sites"]))

        resultado.append(grupo)

    resultado.sort(key=lambda item: item["preco_medio"], reverse=True)

    contexto = {
    "resultados": resultado,
    "total_resultados": len(resultado),
    "sites": SiteMonitorado.objects.all(),
    "marcas": Marca.objects.all(),
    "categorias": Categoria.objects.all(),
    "busca": busca,
    "site_id": site_id,
    "marca_id": marca_id,
    "categoria_id": categoria_id,
    "data_inicio": data_inicio,
    "data_fim": data_fim,
    "query_string": request.GET.urlencode(),
    }

    return render(request, "mercado/precos_referencias.html", contexto)

def exportar_precos_excel(request):
    coletas = ColetaProduto.objects.select_related(
        "produto",
        "produto__site",
        "produto__marca",
        "produto__categoria",
        "produto__produto_referencia",
        "produto__produto_referencia__marca",
        "produto__produto_referencia__categoria",
        "produto__produto_referencia__fabricante_importador",
    ).filter(
        produto__produto_referencia__isnull=False,
        preco_atual__isnull=False,
    )

    busca = request.GET.get("busca", "")
    site_id = request.GET.get("site", "")
    marca_id = request.GET.get("marca", "")
    categoria_id = request.GET.get("categoria", "")
    data_inicio = request.GET.get("data_inicio", "")
    data_fim = request.GET.get("data_fim", "")

    if busca:
        coletas = coletas.filter(
            Q(produto__produto_referencia__nome_referencia__icontains=busca)
            | Q(produto__produto_referencia__codigo_fabricante__icontains=busca)
            | Q(produto__produto_referencia__ean__icontains=busca)
            | Q(produto__nome_original__icontains=busca)
            | Q(produto__codigo_fabricante__icontains=busca)
            | Q(produto__ean__icontains=busca)
        )

    if site_id:
        coletas = coletas.filter(produto__site_id=site_id)

    if marca_id:
        coletas = coletas.filter(produto__produto_referencia__marca_id=marca_id)

    if categoria_id:
        coletas = coletas.filter(produto__produto_referencia__categoria_id=categoria_id)

    if data_inicio:
        coletas = coletas.filter(data_coleta__date__gte=data_inicio)

    if data_fim:
        coletas = coletas.filter(data_coleta__date__lte=data_fim)

    grupos = {}

    for coleta in coletas.order_by("produto__produto_referencia__nome_referencia", "data_coleta"):
        referencia = coleta.produto.produto_referencia
        preco = float(coleta.preco_atual)

        if referencia.id not in grupos:
            grupos[referencia.id] = {
                "referencia": referencia,
                "marca": referencia.marca.nome if referencia.marca else "-",
                "fabricante": (
                    referencia.fabricante_importador.nome
                    if referencia.fabricante_importador
                    else "-"
                ),
                "categoria": referencia.categoria.nome if referencia.categoria else "-",
                "sites": set(),
                "qtd_coletas": 0,
                "soma_precos": 0,
                "menor_preco": preco,
                "maior_preco": preco,
                "site_menor_preco": coleta.produto.site.nome,
                "site_maior_preco": coleta.produto.site.nome,
                "ultima_coleta": coleta.data_coleta,
            }

        grupo = grupos[referencia.id]

        grupo["sites"].add(coleta.produto.site.nome)
        grupo["qtd_coletas"] += 1
        grupo["soma_precos"] += preco

        if preco < grupo["menor_preco"]:
            grupo["menor_preco"] = preco
            grupo["site_menor_preco"] = coleta.produto.site.nome

        if preco > grupo["maior_preco"]:
            grupo["maior_preco"] = preco
            grupo["site_maior_preco"] = coleta.produto.site.nome

        if coleta.data_coleta > grupo["ultima_coleta"]:
            grupo["ultima_coleta"] = coleta.data_coleta

    resultado = []

    for grupo in grupos.values():
        preco_medio = grupo["soma_precos"] / grupo["qtd_coletas"]

        variacao_percentual = 0
        if grupo["menor_preco"] > 0:
            variacao_percentual = (
                (grupo["maior_preco"] - grupo["menor_preco"])
                / grupo["menor_preco"]
            ) * 100

        grupo["preco_medio"] = preco_medio
        grupo["variacao_percentual"] = variacao_percentual
        grupo["sites_texto"] = ", ".join(sorted(grupo["sites"]))

        resultado.append(grupo)

    resultado.sort(key=lambda item: item["preco_medio"], reverse=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Preco Medio"

    cabecalhos = [
        "Produto referência",
        "Marca",
        "Fabricante / Importador",
        "Categoria",
        "Sites",
        "Quantidade de coletas",
        "Menor preço",
        "Site menor preço",
        "Preço médio",
        "Maior preço",
        "Site maior preço",
        "Variação percentual",
        "Última coleta",
    ]

    sheet.append(cabecalhos)

    for item in resultado:
        sheet.append([
            item["referencia"].nome_referencia,
            item["marca"],
            item["fabricante"],
            item["categoria"],
            item["sites_texto"],
            item["qtd_coletas"],
            round(item["menor_preco"], 2),
            item["site_menor_preco"],
            round(item["preco_medio"], 2),
            round(item["maior_preco"], 2),
            item["site_maior_preco"],
            round(item["variacao_percentual"], 2),
            item["ultima_coleta"].strftime("%d/%m/%Y %H:%M"),
        ])

    for coluna in sheet.columns:
        largura = 12
        letra_coluna = coluna[0].column_letter

        for celula in coluna:
            if celula.value:
                largura = max(largura, len(str(celula.value)) + 2)

        sheet.column_dimensions[letra_coluna].width = min(largura, 60)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="preco_medio_produtos_referencia.xlsx"'

    workbook.save(response)
    return response

def exportar_ranking_excel(request):
    coletas = ColetaProduto.objects.select_related(
        "produto",
        "produto__site",
        "produto__marca",
        "produto__categoria",
        "produto__produto_referencia",
    ).order_by("-data_coleta")

    busca = request.GET.get("busca", "")
    site_id = request.GET.get("site", "")
    marca_id = request.GET.get("marca", "")
    categoria_id = request.GET.get("categoria", "")
    somente_disponiveis = request.GET.get("somente_disponiveis", "")

    if busca:
        coletas = coletas.filter(
            Q(produto__nome_original__icontains=busca)
            | Q(produto__codigo_fabricante__icontains=busca)
            | Q(produto__ean__icontains=busca)
            | Q(produto__produto_referencia__nome_referencia__icontains=busca)
            | Q(produto__produto_referencia__codigo_fabricante__icontains=busca)
            | Q(produto__produto_referencia__ean__icontains=busca)
        )

    if site_id:
        coletas = coletas.filter(produto__site_id=site_id)

    if marca_id:
        coletas = coletas.filter(produto__marca_id=marca_id)

    if categoria_id:
        coletas = coletas.filter(produto__categoria_id=categoria_id)

    if somente_disponiveis == "1":
        coletas = coletas.filter(disponivel=True)

    # Pega somente a última coleta de cada produto.
    ultimas_por_produto = {}
    for coleta in coletas.distinct():
        if coleta.produto_id not in ultimas_por_produto:
            ultimas_por_produto[coleta.produto_id] = coleta

    ranking = list(ultimas_por_produto.values())

    ranking.sort(
        key=lambda coleta: (
            coleta.ranking_geral if coleta.ranking_geral is not None else 999999,
            coleta.ranking_categoria if coleta.ranking_categoria is not None else 999999,
            coleta.preco_atual if coleta.preco_atual is not None else 999999999,
        )
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ranking Mercado"

    cabecalhos = [
        "Ranking geral",
        "Ranking categoria",
        "Produto coletado",
        "Produto referência",
        "Site",
        "Marca",
        "Categoria",
        "Código site",
        "Código fabricante",
        "EAN",
        "Preço atual",
        "Preço antigo",
        "Desconto percentual",
        "Nota média",
        "Quantidade avaliações",
        "Disponível",
        "Status vínculo",
        "Data coleta",
        "URL",
    ]

    sheet.append(cabecalhos)

    for coleta in ranking:
        produto = coleta.produto

        sheet.append([
            coleta.ranking_geral,
            coleta.ranking_categoria,
            produto.nome_original,
            produto.produto_referencia.nome_referencia if produto.produto_referencia else "",
            produto.site.nome if produto.site else "",
            produto.marca.nome if produto.marca else "",
            produto.categoria.nome if produto.categoria else "",
            produto.codigo_site or "",
            produto.codigo_fabricante or "",
            produto.ean or "",
            float(coleta.preco_atual) if coleta.preco_atual is not None else "",
            float(coleta.preco_antigo) if coleta.preco_antigo is not None else "",
            float(coleta.desconto_percentual) if coleta.desconto_percentual is not None else "",
            float(coleta.nota_media) if coleta.nota_media is not None else "",
            coleta.quantidade_avaliacoes if coleta.quantidade_avaliacoes is not None else "",
            "Sim" if coleta.disponivel else "Não",
            produto.get_status_vinculo_display(),
            coleta.data_coleta.strftime("%d/%m/%Y %H:%M"),
            produto.url,
        ])

    for coluna in sheet.columns:
        largura = 12
        letra_coluna = coluna[0].column_letter

        for celula in coluna:
            if celula.value:
                largura = max(largura, len(str(celula.value)) + 2)

        sheet.column_dimensions[letra_coluna].width = min(largura, 60)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="ranking_mercado.xlsx"'

    workbook.save(response)
    return response

def produtos_pendentes_validacao(request):
    produtos = ProdutoColetado.objects.select_related(
        "site",
        "marca",
        "categoria",
        "produto_referencia",
    ).filter(
        Q(produto_referencia__isnull=True)
        | Q(status_vinculo="PENDENTE")
        | Q(status_vinculo="DIVERGENTE")
        | Q(status_vinculo="SEM_REFERENCIA")
    )

    busca = request.GET.get("busca", "")
    site_id = request.GET.get("site", "")
    marca_id = request.GET.get("marca", "")
    categoria_id = request.GET.get("categoria", "")
    status_vinculo = request.GET.get("status_vinculo", "")

    if busca:
        produtos = produtos.filter(
            Q(nome_original__icontains=busca)
            | Q(codigo_site__icontains=busca)
            | Q(codigo_fabricante__icontains=busca)
            | Q(ean__icontains=busca)
            | Q(url__icontains=busca)
        )

    if site_id:
        produtos = produtos.filter(site_id=site_id)

    if marca_id:
        produtos = produtos.filter(marca_id=marca_id)

    if categoria_id:
        produtos = produtos.filter(categoria_id=categoria_id)

    if status_vinculo:
        produtos = produtos.filter(status_vinculo=status_vinculo)

    produtos = produtos.order_by("site__nome", "marca__nome", "nome_original")

    contexto = {
        "produtos": produtos.distinct(),
        "total_produtos": produtos.distinct().count(),
        "sites": SiteMonitorado.objects.all(),
        "marcas": Marca.objects.all(),
        "categorias": Categoria.objects.all(),
        "status_choices": ProdutoColetado.STATUS_VINCULO_CHOICES,
        "busca": busca,
        "site_id": site_id,
        "marca_id": marca_id,
        "categoria_id": categoria_id,
        "status_vinculo": status_vinculo,
    }

    return render(request, "mercado/produtos_pendentes_validacao.html", contexto)

def importar_referencias_excel(request):
    if request.method == "POST":
        arquivo = request.FILES.get("arquivo_excel")

        if not arquivo:
            messages.error(request, "Nenhum arquivo foi enviado.")
            return redirect("mercado:importar_referencias_excel")

        if not arquivo.name.endswith(".xlsx"):
            messages.error(request, "Envie um arquivo Excel no formato .xlsx.")
            return redirect("mercado:importar_referencias_excel")

        try:
            workbook = load_workbook(arquivo, data_only=True)
            sheet = workbook.active

            cabecalhos = []
            for celula in sheet[1]:
                cabecalhos.append(str(celula.value).strip() if celula.value else "")

            mapa_colunas = {
                nome_coluna: indice
                for indice, nome_coluna in enumerate(cabecalhos)
            }

            colunas_obrigatorias = [
                "nome_referencia",
                "marca",
                "categoria",
            ]

            for coluna in colunas_obrigatorias:
                if coluna not in mapa_colunas:
                    messages.error(
                        request,
                        f"Coluna obrigatória ausente no Excel: {coluna}"
                    )
                    return redirect("mercado:importar_referencias_excel")

            total_linhas = 0
            total_criados = 0
            total_atualizados = 0
            total_erros = 0

            for numero_linha, linha in enumerate(sheet.iter_rows(min_row=2), start=2):
                def valor(nome_coluna):
                    indice = mapa_colunas.get(nome_coluna)

                    if indice is None:
                        return ""

                    celula = linha[indice].value

                    if celula is None:
                        return ""

                    return str(celula).strip()

                nome_referencia = valor("nome_referencia")
                marca_nome = valor("marca")
                categoria_nome = valor("categoria")

                if not nome_referencia or not marca_nome or not categoria_nome:
                    total_erros += 1
                    continue

                total_linhas += 1

                fabricante_nome = valor("fabricante_importador")
                tipo_fabricante = valor("tipo_fabricante") or "FABRICANTE"
                pais_origem = valor("pais_origem")

                codigo_fabricante = valor("codigo_fabricante")
                ean = valor("ean")
                url_oficial = valor("url_oficial")
                fonte_validacao = valor("fonte_validacao") or "SITE_FABRICANTE"
                status_validacao = valor("status_validacao") or "PENDENTE"
                observacao_validacao = valor("observacao_validacao")
                ativo_texto = valor("ativo").lower()

                ativo = True
                if ativo_texto in ["não", "nao", "false", "0", "inativo"]:
                    ativo = False

                marca, _ = Marca.objects.get_or_create(
                    nome=marca_nome.upper()
                )

                categoria, _ = Categoria.objects.get_or_create(
                    nome=categoria_nome
                )

                fabricante_importador = None
                if fabricante_nome:
                    fabricante_importador, _ = FabricanteImportador.objects.get_or_create(
                        nome=fabricante_nome,
                        defaults={
                            "tipo": tipo_fabricante,
                            "pais_origem": pais_origem,
                        },
                    )

                # Critério de identificação:
                # 1. EAN, se existir
                # 2. Código fabricante + marca
                # 3. Nome referência + marca
                referencia = None

                if ean:
                    referencia = ProdutoReferencia.objects.filter(ean=ean).first()

                if not referencia and codigo_fabricante:
                    referencia = ProdutoReferencia.objects.filter(
                        marca=marca,
                        codigo_fabricante=codigo_fabricante,
                    ).first()

                if not referencia:
                    referencia = ProdutoReferencia.objects.filter(
                        marca=marca,
                        nome_referencia=nome_referencia,
                    ).first()

                if referencia:
                    referencia.nome_referencia = nome_referencia
                    referencia.marca = marca
                    referencia.categoria = categoria
                    referencia.fabricante_importador = fabricante_importador
                    referencia.codigo_fabricante = codigo_fabricante
                    referencia.ean = ean
                    referencia.url_oficial = url_oficial
                    referencia.fonte_validacao = fonte_validacao
                    referencia.status_validacao = status_validacao
                    referencia.observacao_validacao = observacao_validacao
                    referencia.ativo = ativo
                    referencia.save()

                    total_atualizados += 1
                else:
                    ProdutoReferencia.objects.create(
                        nome_referencia=nome_referencia,
                        marca=marca,
                        categoria=categoria,
                        fabricante_importador=fabricante_importador,
                        codigo_fabricante=codigo_fabricante,
                        ean=ean,
                        url_oficial=url_oficial,
                        fonte_validacao=fonte_validacao,
                        status_validacao=status_validacao,
                        observacao_validacao=observacao_validacao,
                        ativo=ativo,
                    )

                    total_criados += 1

            messages.success(
                request,
                (
                    f"Importação concluída. "
                    f"Linhas processadas: {total_linhas}. "
                    f"Criados: {total_criados}. "
                    f"Atualizados: {total_atualizados}. "
                    f"Linhas ignoradas/erro: {total_erros}."
                )
            )

            return redirect("mercado:importar_referencias_excel")

        except Exception as erro:
            messages.error(request, f"Erro ao importar arquivo: {erro}")
            return redirect("mercado:importar_referencias_excel")

    return render(request, "mercado/importar_referencias_excel.html")

def normalizar_para_comparacao(texto):
    if not texto:
        return ""

    texto = str(texto).upper().strip()

    substituicoes = {
        ".": " ",
        ",": " ",
        "-": " ",
        "/": " ",
        "_": " ",
        "  ": " ",
    }

    for antigo, novo in substituicoes.items():
        texto = texto.replace(antigo, novo)

    return " ".join(texto.split())


def similaridade_texto(texto_a, texto_b):
    texto_a = normalizar_para_comparacao(texto_a)
    texto_b = normalizar_para_comparacao(texto_b)

    if not texto_a or not texto_b:
        return 0

    return SequenceMatcher(None, texto_a, texto_b).ratio()


def gerar_sugestao_para_produto(produto, referencias):
    melhor_sugestao = None

    produto_ean = normalizar_para_comparacao(produto.ean)
    produto_codigo = normalizar_para_comparacao(produto.codigo_fabricante)
    produto_marca = produto.marca.nome.upper() if produto.marca else ""

    for referencia in referencias:
        referencia_ean = normalizar_para_comparacao(referencia.ean)
        referencia_codigo = normalizar_para_comparacao(referencia.codigo_fabricante)
        referencia_marca = referencia.marca.nome.upper() if referencia.marca else ""

        criterio = None
        confianca = 0

        # 1. Melhor critério: EAN igual.
        if produto_ean and referencia_ean and produto_ean == referencia_ean:
            criterio = "EAN igual"
            confianca = 100

        # 2. Código fabricante igual + marca igual.
        elif (
            produto_codigo
            and referencia_codigo
            and produto_codigo == referencia_codigo
            and produto_marca
            and referencia_marca
            and produto_marca == referencia_marca
        ):
            criterio = "Código fabricante igual + marca igual"
            confianca = 95

        # 3. Código fabricante igual.
        elif produto_codigo and referencia_codigo and produto_codigo == referencia_codigo:
            criterio = "Código fabricante igual"
            confianca = 85

        # 4. Nome parecido + marca igual.
        else:
            similaridade = similaridade_texto(
                produto.nome_original,
                referencia.nome_referencia,
            )

            if (
                similaridade >= 0.70
                and produto_marca
                and referencia_marca
                and produto_marca == referencia_marca
            ):
                criterio = "Nome parecido + marca igual"
                confianca = round(similaridade * 100, 2)

            elif similaridade >= 0.82:
                criterio = "Nome muito parecido"
                confianca = round(similaridade * 100, 2)

        if criterio and confianca > 0:
            if not melhor_sugestao or confianca > melhor_sugestao["confianca"]:
                melhor_sugestao = {
                    "produto": produto,
                    "referencia": referencia,
                    "criterio": criterio,
                    "confianca": confianca,
                }

    return melhor_sugestao


def sugestoes_vinculo(request):
    produtos = ProdutoColetado.objects.select_related(
        "site",
        "marca",
        "categoria",
        "produto_referencia",
    ).filter(
        Q(produto_referencia__isnull=True)
        | Q(status_vinculo="PENDENTE")
        | Q(status_vinculo="DIVERGENTE")
        | Q(status_vinculo="SEM_REFERENCIA")
    )

    referencias = ProdutoReferencia.objects.select_related(
        "marca",
        "categoria",
        "fabricante_importador",
    ).filter(
        ativo=True
    )

    busca = request.GET.get("busca", "")
    minimo_confianca = request.GET.get("minimo_confianca", "70")

    if busca:
        produtos = produtos.filter(
            Q(nome_original__icontains=busca)
            | Q(codigo_fabricante__icontains=busca)
            | Q(ean__icontains=busca)
            | Q(url__icontains=busca)
        )

    try:
        minimo_confianca_num = float(minimo_confianca)
    except Exception:
        minimo_confianca_num = 70

    sugestoes = []

    for produto in produtos.order_by("site__nome", "marca__nome", "nome_original"):
        sugestao = gerar_sugestao_para_produto(produto, referencias)

        if sugestao and sugestao["confianca"] >= minimo_confianca_num:
            sugestoes.append(sugestao)

    sugestoes.sort(key=lambda item: item["confianca"], reverse=True)

    contexto = {
        "sugestoes": sugestoes,
        "total_sugestoes": len(sugestoes),
        "busca": busca,
        "minimo_confianca": minimo_confianca,
    }

    return render(request, "mercado/sugestoes_vinculo.html", contexto)


def aplicar_sugestao_vinculo(request, produto_id, referencia_id):
    if request.method != "POST":
        return redirect("mercado:sugestoes_vinculo")

    produto = get_object_or_404(ProdutoColetado, id=produto_id)
    referencia = get_object_or_404(ProdutoReferencia, id=referencia_id)

    produto.produto_referencia = referencia
    produto.status_vinculo = "VINCULADO"

    # Se o produto coletado estiver sem marca/categoria, aproveita a referência.
    if not produto.marca and referencia.marca:
        produto.marca = referencia.marca

    if not produto.categoria and referencia.categoria:
        produto.categoria = referencia.categoria

    # Se estiver sem código/EAN, aproveita a referência oficial.
    if not produto.codigo_fabricante and referencia.codigo_fabricante:
        produto.codigo_fabricante = referencia.codigo_fabricante

    if not produto.ean and referencia.ean:
        produto.ean = referencia.ean

    produto.save()

    messages.success(
        request,
        f"Produto '{produto.nome_original}' vinculado à referência '{referencia.nome_referencia}'."
    )

    return redirect("mercado:sugestoes_vinculo")