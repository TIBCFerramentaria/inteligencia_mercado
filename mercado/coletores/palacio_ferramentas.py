import re
import json
import time
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from mercado.coletores.debug_utils import salvar_debug_texto

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto)
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def normalizar_preco(valor):
    if valor is None:
        return None

    texto = normalizar_texto(valor)

    match = re.search(r"([\d\.]+,\d{2})", texto)

    if not match:
        return None

    numero = match.group(1).replace(".", "").replace(",", ".")

    try:
        return float(numero)
    except Exception:
        return None


def extrair_referencia_detalhe_palacio(html):
    """
    Extrai o código de referência/código fabricante da página de detalhe.

    No Palácio das Ferramentas, essa informação aparece dentro de:
    div class="pdp-details-stack"

    Exemplos esperados:
    Referência: 123456
    Ref.: 123456
    Ref: ABC-123
    """

    soup = BeautifulSoup(html, "html.parser")

    blocos = soup.select(".pdp-details-stack")

    textos = []

    for bloco in blocos:
        texto = normalizar_texto(bloco.get_text(" ", strip=True))
        if texto:
            textos.append(texto)

    texto_geral = " ".join(textos)

    if not texto_geral:
        return ""

    padroes = [
        r"Refer[eê]ncia\s*:?\s*([A-Za-z0-9\.\-\/_]+)",
        r"Ref\.?\s*:?\s*([A-Za-z0-9\.\-\/_]+)",
        r"C[oó]digo\s*do\s*fabricante\s*:?\s*([A-Za-z0-9\.\-\/_]+)",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto_geral, flags=re.IGNORECASE)

        if match:
            return normalizar_texto(match.group(1))

    return ""


def extrair_ean_detalhe_palacio(html):
    """
    Tenta extrair EAN/GTIN da página de detalhe do Palácio.

    Procura em:
    - Texto visível da página
    - JSON-LD
    - Scripts da página
    - Atributos itemprop
    """

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # 1. Tenta por atributos estruturados no HTML
    for seletor in [
        '[itemprop="gtin13"]',
        '[itemprop="gtin14"]',
        '[itemprop="gtin"]',
        '[itemprop="sku"]',
    ]:
        elemento = soup.select_one(seletor)

        if elemento:
            valor = elemento.get("content") or elemento.get_text(" ", strip=True)
            numeros = re.findall(r"\d{8,14}", valor or "")

            if numeros:
                return numeros[0]

    # 2. Tenta em JSON-LD
    for script in soup.select('script[type="application/ld+json"]'):
        conteudo = script.string or script.get_text()

        if not conteudo:
            continue

        try:
            dados = json.loads(conteudo)
        except Exception:
            continue

        objetos = dados if isinstance(dados, list) else [dados]

        for obj in objetos:
            if not isinstance(obj, dict):
                continue

            for chave in ["gtin13", "gtin14", "gtin", "ean", "sku"]:
                valor = obj.get(chave)

                if valor:
                    numeros = re.findall(r"\d{8,14}", str(valor))

                    if numeros:
                        return numeros[0]

    # 3. Tenta no texto visível
    texto = normalizar_texto(soup.get_text(" ", strip=True))

    padroes = [
        r"C[oó]digo\s+EAN\s*:?\s*([0-9\.\-\s]{8,30})",
        r"EAN\s*:?\s*([0-9\.\-\s]{8,30})",
        r"GTIN\s*:?\s*([0-9\.\-\s]{8,30})",
        r"C[oó]digo\s+de\s+barras\s*:?\s*([0-9\.\-\s]{8,30})",
        r"C[oó]d\.?\s+de\s+barras\s*:?\s*([0-9\.\-\s]{8,30})",
        r"C[oó]digo\s+barra\s*:?\s*([0-9\.\-\s]{8,30})",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto, flags=re.IGNORECASE)

        if match:
            bruto = match.group(1)
            numeros = re.findall(r"\d{8,14}", bruto.replace(".", "").replace("-", "").replace(" ", ""))

            if numeros:
                return numeros[0]

    # 4. Tenta no HTML bruto/scripts
    html_normalizado = normalizar_texto(html)

    padroes_html = [
        r'"gtin13"\s*:\s*"(\d{8,14})"',
        r'"gtin14"\s*:\s*"(\d{8,14})"',
        r'"gtin"\s*:\s*"(\d{8,14})"',
        r'"ean"\s*:\s*"(\d{8,14})"',
        r"'gtin13'\s*:\s*'(\d{8,14})'",
        r"'gtin14'\s*:\s*'(\d{8,14})'",
        r"'gtin'\s*:\s*'(\d{8,14})'",
        r"'ean'\s*:\s*'(\d{8,14})'",
    ]

    for padrao in padroes_html:
        match = re.search(padrao, html_normalizado, flags=re.IGNORECASE)

        if match:
            return match.group(1)

    return ""


def extrair_estoque_detalhe_palacio(html):
    """
    Extrai disponibilidade e quantidade de estoque, quando o site informa.

    Retorna:
    estoque: número ou None
    disponivel: True, False ou None
    texto_disponibilidade: texto encontrado
    """

    soup = BeautifulSoup(html, "html.parser")
    texto = normalizar_texto(soup.get_text(" ", strip=True))

    match_quantidade = re.search(
        r"Apenas\s+(\d+)\s+unidade\(s\)\s+restantes\s+em\s+estoque",
        texto,
        flags=re.IGNORECASE,
    )

    if match_quantidade:
        estoque = int(match_quantidade.group(1))
        texto_disponibilidade = match_quantidade.group(0)

        return estoque, True, texto_disponibilidade

    if re.search(r"\bEm estoque\b", texto, flags=re.IGNORECASE):
        return None, True, "Em estoque"

    if re.search(r"Fora de estoque|Indispon[ií]vel|Produto indispon[ií]vel", texto, flags=re.IGNORECASE):
        return 0, False, "Fora de estoque"

    return None, None, ""

def enriquecer_produto_com_detalhe_palacio(session, produto):
    """
    Abre a página de detalhe do produto e corrige o código_fabricante
    com base no campo Referência/Ref da div pdp-details-stack.
    """

    url_produto = produto.get("url")

    if not url_produto:
        return produto

    try:
        resposta = session.get(url_produto, timeout=40)

        if resposta.status_code != 200:
            print(
                f"[WARN] Detalhe Palácio retornou status {resposta.status_code}: "
                f"{url_produto}"
            )
            return produto

        salvar_debug_texto("debug_palacio_detalhe.html", resposta.text)

        codigo_fabricante = extrair_referencia_detalhe_palacio(resposta.text)
        ean = extrair_ean_detalhe_palacio(resposta.text)
        estoque, disponivel, texto_disponibilidade = extrair_estoque_detalhe_palacio(resposta.text)

        if codigo_fabricante:
            produto["codigo_fabricante"] = codigo_fabricante

            # Se o código do site estiver vazio ou foi deduzido da URL, podemos usar a referência também.
            if not produto.get("codigo_site"):
                produto["codigo_site"] = codigo_fabricante

            pass  # DEBUG DESATIVADO
        else:
            print(
                f"[WARN] Referência não encontrada no detalhe: "
                f"{produto.get('nome')} - {url_produto}"
            )

        if ean:
            produto["ean"] = ean
            pass  # DEBUG DESATIVADO

        produto["estoque"] = estoque
        produto["disponivel"] = disponivel
        produto["texto_disponibilidade"] = texto_disponibilidade

        if texto_disponibilidade:
            pass  # DEBUG DESATIVADO

    except Exception as erro:
        print(f"[WARN] Erro ao enriquecer detalhe Palácio: {erro}")

    return produto

def extrair_marca_pelo_nome_palacio(nome):
    if not nome:
        return ""

    nome_upper = nome.upper()

    marcas_conhecidas = [
        "VONDER",
        "TRAMONTINA",
        "GEDORE",
        "BOSCH",
        "MAKITA",
        "DEWALT",
        "STANLEY",
        "BLACK+DECKER",
        "BLACK & DECKER",
        "IRWIN",
        "WORKER",
        "SCHULZ",
        "FORTG",
        "NOVE54",
        "TEKNA",
        "HUSQVARNA",
        "TOYAMA",
        "BRANCO",
        "CHIAPERINI",
        "MENEGOTTI",
        "WAP",
        "KARCHER",
        "EINHELL",
        "SKIL",
    ]

    for marca in marcas_conhecidas:
        if marca in nome_upper:
            return marca.title()

    return ""


def montar_url_pagina(url_base, pagina):
    if pagina <= 1:
        return url_base

    partes = urlparse(url_base)
    query = parse_qs(partes.query)
    query["p"] = [str(pagina)]

    nova_query = urlencode(query, doseq=True)

    return urlunparse(
        (
            partes.scheme,
            partes.netloc,
            partes.path,
            partes.params,
            nova_query,
            partes.fragment,
        )
    )


def extrair_codigo_site_palacio(card, url_produto):
    html_card = str(card)

    match = re.search(r"product-image-container-(\d+)", html_card)

    if match:
        return match.group(1)

    match = re.search(r"product-item-info[_\-](\d+)", html_card)

    if match:
        return match.group(1)

    if url_produto:
        partes = [p for p in urlparse(url_produto).path.split("/") if p]
        if partes:
            slug = partes[-1]
            slug = slug.replace(".html", "")
            return slug[:100]

    return ""


def extrair_parcelamento_palacio(texto):
    texto = normalizar_texto(texto)

    quantidade_parcelas = None
    valor_parcela = None

    match = re.search(
        r"(\d+)\s*x\s*de\s*R\$\s*([\d\.]+,\d{2})",
        texto,
        flags=re.IGNORECASE,
    )

    if match:
        try:
            quantidade_parcelas = int(match.group(1))
        except Exception:
            quantidade_parcelas = None

        valor_parcela = normalizar_preco(match.group(2))

    return quantidade_parcelas, valor_parcela


def encontrar_cards_produtos_palacio(soup):
    seletores = [
        "li.product-item",
        ".products-grid .product-item",
        ".product-items .product-item",
        ".product-item-info",
    ]

    for seletor in seletores:
        cards = soup.select(seletor)
        if cards:
            return cards

    return []


def extrair_produtos_html_palacio(html, url_base, limite=None):
    soup = BeautifulSoup(html, "html.parser")

    cards = encontrar_cards_produtos_palacio(soup)

    pass  # DEBUG DESATIVADO

    produtos = []
    urls_vistas = set()

    for card in cards:
        nome_el = card.select_one(
            "a.product-item-link, "
            ".product-item-name a, "
            "strong.product-item-name a, "
            "h2 a, "
            "h3 a"
        )

        link_el = nome_el or card.select_one("a.product-item-photo, a[href]")

        if not link_el:
            continue

        nome = normalizar_texto(link_el.get_text(" ", strip=True))

        if not nome and nome_el:
            nome = normalizar_texto(nome_el.get_text(" ", strip=True))

        if not nome:
            continue

        href = link_el.get("href") or ""

        if not href:
            continue

        url_produto = urljoin(url_base, href)

        if url_produto in urls_vistas:
            continue

        urls_vistas.add(url_produto)

        preco_atual = None
        preco_antigo = None

        preco_atual_el = card.select_one(
            ".special-price .price, "
            ".price-final_price .price, "
            ".price-box .price, "
            ".price"
        )

        preco_antigo_el = card.select_one(
            ".old-price .price, "
            ".price-old .price"
        )

        if preco_atual_el:
            preco_atual = normalizar_preco(preco_atual_el.get_text(" ", strip=True))

        if preco_antigo_el:
            preco_antigo = normalizar_preco(preco_antigo_el.get_text(" ", strip=True))

        texto_card = normalizar_texto(card.get_text(" ", strip=True))

        if preco_atual is None:
            preco_atual = normalizar_preco(texto_card)

        quantidade_parcelas, valor_parcela = extrair_parcelamento_palacio(texto_card)

        preco_prazo = None

        if quantidade_parcelas and valor_parcela:
            preco_prazo = round(quantidade_parcelas * valor_parcela, 2)

        codigo_site = extrair_codigo_site_palacio(card, url_produto)

        produto = {
            "nome": nome,
            "nome_original": nome,
            "url": url_produto,
            "codigo_site": codigo_site,
            "codigo_fabricante": "",
            "marca_nome": extrair_marca_pelo_nome_palacio(nome),
            "ean": "",
            "preco_atual": preco_atual,
            "preco_antigo": preco_antigo,
            "preco_prazo": preco_prazo,
            "quantidade_parcelas": quantidade_parcelas,
            "valor_parcela": valor_parcela,
            "estoque": None,
            "ranking": len(produtos) + 1,
        }

        produtos.append(produto)

        if limite and len(produtos) >= limite:
            break

    return produtos


def encontrar_proxima_pagina_palacio(html, url_atual):
    soup = BeautifulSoup(html, "html.parser")

    link = soup.select_one("a.action.next, .pages a.next, a.next")

    if link and link.get("href"):
        return urljoin(url_atual, link.get("href"))

    return None


def coletar_produtos_palacio_ferramentas(
    url_inicial=None,
    url_base=None,
    url=None,
    limite=500,
    max_paginas=10,
    enriquecer_detalhe=True,
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
    urls_vistas = set()

    url_atual = url_inicial

    for pagina in range(1, max_paginas + 1):
        if pagina > 1 and not url_atual:
            url_atual = montar_url_pagina(url_inicial, pagina)

        print(f"[INFO] Acessando página {pagina}: {url_atual}")

        try:
            resposta = session.get(url_atual, timeout=40)
        except Exception as erro:
            print(f"[ERRO] Falha ao acessar página: {erro}")
            break

        pass  # DEBUG DESATIVADO

        if resposta.status_code != 200:
            print(f"[WARN] Página retornou status {resposta.status_code}. Encerrando.")
            break

        html = resposta.text

        if pagina == 1:
            salvar_debug_texto("debug_palacio_listagem.html", html)

        produtos_pagina = extrair_produtos_html_palacio(
            html=html,
            url_base=url_atual,
            limite=limite,
        )

        print(f"[INFO] Produtos extraídos da página {pagina}: {len(produtos_pagina)}")

        novos = 0

        for item in produtos_pagina:
            chave = item.get("url") or item.get("codigo_site") or item.get("nome")

            if not chave:
                continue

            if chave in urls_vistas:
                continue

            urls_vistas.add(chave)

            if enriquecer_detalhe:
                item = enriquecer_produto_com_detalhe_palacio(session, item)
                time.sleep(0.5)

            item["ranking"] = len(produtos) + 1
            produtos.append(item)
            novos += 1

            if limite and len(produtos) >= limite:
                print(f"[INFO] Limite de {limite} produtos atingido.")
                print(f"[FIM] Total de produtos coletados: {len(produtos)}")
                return produtos

        print(f"[INFO] Produtos novos adicionados: {novos}")

        proxima = encontrar_proxima_pagina_palacio(html, url_atual)

        if not proxima:
            print("[INFO] Próxima página não encontrada. Encerrando.")
            break

        url_atual = proxima

        time.sleep(1.5)

    print(f"[FIM] Total de produtos coletados: {len(produtos)}")
    return produtos
