from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from openpyxl import Workbook
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