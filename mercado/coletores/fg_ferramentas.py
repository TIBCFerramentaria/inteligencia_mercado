import json
import re
import time
from urllib.parse import urlparse

import requests


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto)
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def normalizar_numero(valor):
    if valor is None:
        return None

    try:
        return float(valor)
    except Exception:
        return None


def extrair_path_categoria(url):
    partes = urlparse(url)

    path = partes.path.strip("/")

    if not path:
        return ""

    return path


def montar_url_api_vtex(url_categoria, inicio=0, fim=49):
    partes = urlparse(url_categoria)

    dominio = f"{partes.scheme}://{partes.netloc}"
    path_categoria = extrair_path_categoria(url_categoria)

    return (
        f"{dominio}/api/catalog_system/pub/products/search/"
        f"{path_categoria}?_from={inicio}&_to={fim}"
    )


def extrair_melhor_item_vtex(produto_api):
    itens = produto_api.get("items") or []

    if not itens:
        return None

    # Preferir item disponível.
    for item in itens:
        sellers = item.get("sellers") or []

        for seller in sellers:
            oferta = seller.get("commertialOffer") or {}

            if oferta.get("IsAvailable"):
                return item

    return itens[0]


def extrair_oferta_item_vtex(item):
    sellers = item.get("sellers") or []

    if not sellers:
        return {}

    # Preferir seller disponível.
    for seller in sellers:
        oferta = seller.get("commertialOffer") or {}

        if oferta.get("IsAvailable"):
            return oferta

    return (sellers[0].get("commertialOffer") or {}) if sellers else {}


def converter_produto_vtex_fg(produto_api, ranking):
    item = extrair_melhor_item_vtex(produto_api)

    if not item:
        return None

    oferta = extrair_oferta_item_vtex(item)

    nome = normalizar_texto(produto_api.get("productName"))
    marca = normalizar_texto(produto_api.get("brand"))

    url = produto_api.get("link") or ""
    codigo_fabricante = normalizar_texto(produto_api.get("productReference"))
    codigo_site = normalizar_texto(produto_api.get("productId"))

    item_id = normalizar_texto(item.get("itemId"))

    if not codigo_site:
        codigo_site = item_id

    ean = normalizar_texto(item.get("ean"))

    preco_atual = normalizar_numero(oferta.get("Price"))
    preco_antigo = normalizar_numero(oferta.get("ListPrice"))

    disponivel = oferta.get("IsAvailable")
    # Na FG, vamos usar apenas disponibilidade.
    # Não vamos considerar AvailableQuantity como estoque real.
    estoque = None

    try:
        estoque = int(estoque) if estoque is not None else None
    except Exception:
        estoque = None

    texto_disponibilidade = ""

    if disponivel is True:
        texto_disponibilidade = "Em estoque"
    elif disponivel is False:
        texto_disponibilidade = "Indisponível"

    if not nome:
        return None

    return {
        "nome": nome,
        "nome_original": nome,
        "url": url,
        "codigo_site": codigo_site,
        "codigo_fabricante": codigo_fabricante,
        "marca_nome": marca,
        "ean": ean,
        "preco_atual": preco_atual,
        "preco_antigo": preco_antigo,
        "preco_prazo": None,
        "quantidade_parcelas": None,
        "valor_parcela": None,
        "estoque": estoque,
        "disponivel": disponivel,
        "texto_disponibilidade": texto_disponibilidade,
        "ranking": ranking,
    }


def buscar_pagina_api_vtex(session, url_categoria, inicio, fim):
    url_api = montar_url_api_vtex(url_categoria, inicio=inicio, fim=fim)

    print(f"[INFO] Acessando API FG: {url_api}")

    resposta = session.get(url_api, timeout=40)

    print(f"[DEBUG] Status HTTP API FG: {resposta.status_code}")

    if resposta.status_code not in [200, 206]:
        try:
            with open("debug_fg_api_erro.txt", "w", encoding="utf-8") as arquivo:
                arquivo.write(resposta.text)
        except Exception:
            pass

        print(f"[WARN] API FG retornou status {resposta.status_code}.")
        return []

    try:
        dados = resposta.json()
    except Exception as erro:
        print(f"[WARN] Erro ao interpretar JSON da API FG: {erro}")

        try:
            with open("debug_fg_api_resposta.txt", "w", encoding="utf-8") as arquivo:
                arquivo.write(resposta.text)
        except Exception:
            pass

        return []

    try:
        with open("debug_fg_api.json", "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    except Exception:
        pass

    if not isinstance(dados, list):
        print("[WARN] Resposta da API FG não veio como lista.")
        return []

    return dados


def coletar_produtos_fg(
    url_inicial=None,
    url_base=None,
    url=None,
    limite=500,
    max_paginas=10,
    **kwargs,
):
    if not url_inicial:
        url_inicial = url_base

    if not url_inicial:
        url_inicial = url

    if not url_inicial:
        url_inicial = kwargs.get("url")

    if not url_inicial:
        print("[ERRO] Nenhuma URL inicial foi informada.")
        return []

    session = requests.Session()
    session.headers.update(HEADERS)

    produtos = []
    chaves_vistas = set()

    tamanho_pagina = 50

    for pagina in range(1, max_paginas + 1):
        inicio = (pagina - 1) * tamanho_pagina
        fim = inicio + tamanho_pagina - 1

        print(f"[INFO] Coletando página {pagina}. Intervalo API: {inicio} a {fim}")

        produtos_api = buscar_pagina_api_vtex(
            session=session,
            url_categoria=url_inicial,
            inicio=inicio,
            fim=fim,
        )

        print(f"[INFO] Produtos retornados pela API na página {pagina}: {len(produtos_api)}")

        if not produtos_api:
            print("[INFO] Nenhum produto retornado. Encerrando.")
            break

        novos = 0

        for produto_api in produtos_api:
            item = converter_produto_vtex_fg(
                produto_api=produto_api,
                ranking=len(produtos) + 1,
            )

            if not item:
                continue

            chave = item.get("url") or item.get("codigo_site") or item.get("nome")

            if not chave:
                continue

            if chave in chaves_vistas:
                continue

            chaves_vistas.add(chave)
            produtos.append(item)
            novos += 1

            if limite and len(produtos) >= limite:
                print(f"[INFO] Limite de {limite} produtos atingido.")
                print(f"[FIM] Total de produtos coletados FG: {len(produtos)}")
                return produtos

        print(f"[INFO] Produtos novos adicionados da página {pagina}: {novos}")

        if len(produtos_api) < tamanho_pagina:
            print("[INFO] Última página detectada pela quantidade retornada.")
            break

        time.sleep(1)

    print(f"[FIM] Total de produtos coletados FG: {len(produtos)}")
    return produtos