import time
import re
from decimal import Decimal
from urllib.parse import urljoin, urldefrag, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


URL_BASE_DUTRA = "https://www.dutramaquinas.com.br/"


def normalizar_texto(texto):
    if not texto:
        return ""

    return re.sub(r"\s+", " ", str(texto)).strip()


def limpar_url(url):
    url, _fragmento = urldefrag(url)
    partes = urlsplit(url)

    return urlunsplit((
        partes.scheme,
        partes.netloc,
        partes.path,
        partes.query,
        "",
    ))


def converter_preco_para_decimal(texto_preco):
    if not texto_preco:
        return None

    texto = str(texto_preco)
    texto = texto.replace("R$", "")
    texto = texto.replace("\xa0", " ")
    texto = texto.strip()

    # Mantém apenas números, ponto e vírgula.
    texto = re.sub(r"[^0-9,\.]", "", texto)

    # Formato brasileiro: 1.234,56
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return Decimal(texto)
    except Exception:
        return None


def normalizar_texto_monetario(texto):
    if not texto:
        return ""

    texto = str(texto)
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"R\$\s*", "R$ ", texto)
    texto = re.sub(r"(\d)\s+,\s*(\d{2})", r"\1,\2", texto)

    return texto.strip()


def encontrar_precos_no_texto(texto):
    texto = normalizar_texto_monetario(texto)

    return re.findall(
        r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2}",
        texto,
    )


def extrair_primeiro_preco(texto):
    precos = encontrar_precos_no_texto(texto)

    if not precos:
        return None

    return converter_preco_para_decimal(precos[0])


def extrair_preco_antigo(texto):
    texto_normalizado = normalizar_texto_monetario(texto)

    # Só considera preço antigo quando houver estrutura comercial clara:
    # "De R$ 134,00 por R$ 108,21"
    # "Preço de R$ 134,00 por R$ 108,21"
    match = re.search(
        r"(?:pre[cç]o\s*)?de\s*(R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2})\s*(?:por|por\s*apenas)",
        texto_normalizado,
        flags=re.IGNORECASE,
    )

    if match:
        return converter_preco_para_decimal(match.group(1))

    return None


def extrair_parcelamento(texto):
    preco_prazo = None
    quantidade_parcelas = None
    valor_parcela = None

    texto = normalizar_texto_monetario(texto)

    # Exemplos da Dutra:
    # 3x de R$37,97 s/ juros
    # 3x de R$ 37,97 s/ juros
    # 10x de R$29,90
    # 10x R$ 29,90
    match = re.search(
        r"(\d+)\s*x\s*(?:de\s*)?(R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2})",
        texto,
        flags=re.IGNORECASE,
    )

    if match:
        quantidade_parcelas = int(match.group(1))
        valor_parcela = converter_preco_para_decimal(match.group(2))

    if quantidade_parcelas and valor_parcela:
        preco_prazo = quantidade_parcelas * valor_parcela

    return preco_prazo, quantidade_parcelas, valor_parcela

def extrair_texto_parcelamento_do_card(card):
    if not card or not hasattr(card, "select"):
        return ""

    seletores = [
        ".parcelamento-msg",
        "div.parcelamento-msg",
        "[class*='parcelamento']",
        "[class*='parcela']",
    ]

    for seletor in seletores:
        elementos = card.select(seletor)

        for elemento in elementos:
            texto = elemento.get_text(" ", strip=True)
            texto = normalizar_texto(texto)

            if re.search(r"\d+\s*x", texto, flags=re.IGNORECASE):
                return texto

    # Fallback: procura direto no texto completo do card.
    texto_card = normalizar_texto(card.get_text(" ", strip=True))

    match = re.search(
        r"\d+\s*x\s*(?:de\s*)?R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\s*x\s*(?:de\s*)?R\$\s*\d+,\d{2}",
        texto_card,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(0)

    return ""

def parece_link_produto(link):
    href = link.get("href", "")

    if not href:
        return False

    if href.startswith("javascript:"):
        return False

    href_lower = href.lower()

    return "/p/" in href_lower or "/produto/" in href_lower


def parece_titulo_produto(texto):
    texto = normalizar_texto(texto)

    if len(texto) < 15:
        return False

    texto_lower = texto.lower()

    termos_ruido = [
        "entrar",
        "cadastro",
        "carrinho",
        "meus pedidos",
        "atendimento",
        "política",
        "privacidade",
        "formas de pagamento",
        "institucional",
        "departamentos",
        "categorias",
        "ver todos",
        "comprar",
        "adicionar",
    ]

    for termo in termos_ruido:
        if termo in texto_lower:
            return False

    if "R$" in texto:
        return False

    return True


def localizar_card_produto(link):
    atual = link
    candidatos = []

    def eh_link_produto(href):
        return href and ("/p/" in href.lower() or "/produto/" in href.lower())

    for _ in range(14):
        if not atual:
            break

        if not hasattr(atual, "get_text"):
            break

        texto = atual.get_text(" ", strip=True)
        tem_preco = "R$" in texto

        links_produto = atual.find_all("a", href=eh_link_produto)
        qtd_links_produto = len(links_produto)

        # Queremos um bloco que tenha preço e produto,
        # mas que não seja a grade inteira com dezenas de produtos.
        if tem_preco and qtd_links_produto >= 1 and qtd_links_produto <= 3:
            candidatos.append(atual)

        atual = atual.parent

    # Dá preferência para o candidato que contém parcelamento.
    for candidato in candidatos:
        if candidato.select_one(".parcelamento-msg, [class*='parcelamento'], [class*='parcela']"):
            return candidato

    # Se não achou parcelamento, usa o maior bloco razoável encontrado.
    if candidatos:
        return candidatos[-1]

    return link.parent


def extrair_marca_codigo_fabricante(nome_produto):
    nome = normalizar_texto(nome_produto).upper()

    # Exemplo comum:
    # "Alicate universal 8 polegadas - Tramontina"
    # "Produto - R28001004"
    partes = [parte.strip() for parte in nome.split(" - ") if parte.strip()]

    if len(partes) >= 2:
        ultimo = partes[-1]

        # Se o último bloco parecer código, trata como código.
        if re.search(r"\d", ultimo):
            return None, ultimo

        return ultimo, None

    # Código no final do nome.
    match = re.search(r"\b([A-Z0-9][A-Z0-9\.\+\/-]{2,})$", nome)

    if match:
        codigo = match.group(1)
        return None, codigo

    return None, None


def extrair_codigo_site(url):
    # Exemplo possível:
    # /p/conjunto-de-alicates-com-3-pecas-3301189
    partes = urlsplit(url).path.strip("/").split("/")

    if not partes:
        return None

    ultimo = partes[-1]

    match = re.search(r"(\d+)$", ultimo)

    if match:
        return match.group(1)

    return ultimo or None

def extrair_preco_a_vista_do_card(card):
    if not card:
        return None

    # Criamos uma cópia do card para remover o parcelamento.
    # Assim o valor da parcela não é confundido com o preço à vista.
    soup_card = BeautifulSoup(str(card), "html.parser")

    seletores_remover = [
        ".parcelamento-msg",
        "[class*='parcelamento']",
        "[class*='parcela']",
        "[class*='installment']",
    ]

    for seletor in seletores_remover:
        for elemento in soup_card.select(seletor):
            elemento.decompose()

    texto_sem_parcelamento = normalizar_texto(
        soup_card.get_text(" ", strip=True)
    )

    texto_sem_parcelamento = normalizar_texto_monetario(
        texto_sem_parcelamento
    )

    precos = encontrar_precos_no_texto(texto_sem_parcelamento)

    if not precos:
        return None

    texto_upper = texto_sem_parcelamento.upper()

    # Quando houver estrutura tipo:
    # De R$ 134,00 por R$ 108,21
    # o preço atual é o segundo preço.
    if " POR " in texto_upper and len(precos) >= 2:
        return converter_preco_para_decimal(precos[1])

    return converter_preco_para_decimal(precos[0])

def remover_secoes_recomendacao_html(html):
    if not html:
        return html

    html_lower = html.lower()

    marcadores = [
        "mais vendidos",
        "produtos mais vendidos",
        "quem viu também",
        "quem viu, viu também",
        "produtos relacionados",
        "você também pode gostar",
        "voce tambem pode gostar",
        "aproveite também",
        "aproveite tambem",
    ]

    menor_indice = None

    for marcador in marcadores:
        indice = html_lower.find(marcador)

        if indice != -1:
            if menor_indice is None or indice < menor_indice:
                menor_indice = indice

    if menor_indice is not None:
        return html[:menor_indice]

    return html

def esta_dentro_de_carrossel_recomendacao(elemento):
    atual = elemento

    while atual:
        if not hasattr(atual, "get"):
            break

        id_elemento = atual.get("id", "")
        classes = atual.get("class", [])

        if isinstance(classes, str):
            classes = classes.split()

        classes_texto = " ".join(classes).lower()

        # Este é o carrossel específico que você encontrou no HTML:
        # <div class="produtos carousel carousel_26 is-draggable" id="prod_lista">
        if (
            id_elemento == "prod_lista"
            and "produtos" in classes_texto
            and "carousel" in classes_texto
            and "carousel_26" in classes_texto
        ):
            return True

        if "carousel_26" in classes_texto:
            return True

        atual = atual.parent

    return False

def extrair_produtos_do_html(html, url_base, limite=None):
    soup = BeautifulSoup(html, "html.parser")

    produtos = []
    urls_vistas = set()

    for link in soup.find_all("a", href=True):
        if esta_dentro_de_carrossel_recomendacao(link):
            continue
        
        if not parece_link_produto(link):
            continue

        nome = normalizar_texto(link.get_text(" ", strip=True))

        if not parece_titulo_produto(nome):
            continue

        href = link.get("href")
        url = limpar_url(urljoin(url_base, href))

        if url in urls_vistas:
            continue

        card = localizar_card_produto(link)

        if not card:
            continue

        texto_card = normalizar_texto(card.get_text(" ", strip=True))

        if "R$" not in texto_card:
            continue

        preco_atual = extrair_preco_a_vista_do_card(card)
        preco_antigo = extrair_preco_antigo(texto_card)

        texto_parcelamento = extrair_texto_parcelamento_do_card(card)

        if texto_parcelamento:
            preco_prazo, quantidade_parcelas, valor_parcela = extrair_parcelamento(
                texto_parcelamento
            )
        else:
            preco_prazo, quantidade_parcelas, valor_parcela = extrair_parcelamento(
                texto_card
            )

        if preco_atual is None:
            continue

        marca_nome, codigo_fabricante = extrair_marca_codigo_fabricante(nome)
        codigo_site = extrair_codigo_site(url)

        produto = {
            "nome_original": nome,
            "url": url,
            "codigo_site": codigo_site,
            "marca_nome": marca_nome,
            "codigo_fabricante": codigo_fabricante,
            "ean": None,
            "preco_atual": preco_atual,
            "preco_antigo": preco_antigo,
            "preco_prazo": preco_prazo,
            "quantidade_parcelas": quantidade_parcelas,
            "valor_parcela": valor_parcela,
            "desconto_percentual": None,
            "nota_media": None,
            "quantidade_avaliacoes": None,
            "ranking_geral": len(produtos) + 1,
            "ranking_categoria": None,
            "disponivel": True,
            "texto_disponibilidade": "Disponível na página pública",
        }

        produtos.append(produto)
        urls_vistas.add(url)

        if limite and len(produtos) >= limite:
            break

    return produtos

def obter_parametro_url(url, nome_parametro):
    parametros = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    return parametros.get(nome_parametro)


def encontrar_parametro_em_links(html, url_atual, nome_parametro):
    valor_atual = obter_parametro_url(url_atual, nome_parametro)

    if valor_atual:
        return valor_atual

    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if not href or href.startswith("javascript:"):
            continue

        url_candidata = urljoin(url_atual, href)
        valor = obter_parametro_url(url_candidata, nome_parametro)

        if valor:
            return valor

    return None


def montar_url_dutra_pagina(url_base, numero_pagina):
    if numero_pagina <= 1:
        return url_base

    partes = urlsplit(url_base)

    parametros = dict(parse_qsl(partes.query, keep_blank_values=True))

    caminho = partes.path.lower()

    # Caso específico da categoria de alicates da Dutra.
    # URL observada:
    # /c/ferramentas-ferramentas-manuais-alicates
    if "id_categoria_site" not in parametros:
        if "ferramentas-ferramentas-manuais-alicates" in caminho:
            parametros["id_categoria_site"] = "467"

    parametros.setdefault("it_preco_inicial", "0")
    parametros.setdefault("it_preco_final", "0")
    parametros.setdefault("ordering", "relevancia")
    parametros.setdefault("max", "48")

    parametros["pg_num"] = str(numero_pagina)

    nova_query = urlencode(parametros)

    return urlunsplit((
        partes.scheme,
        partes.netloc,
        partes.path,
        nova_query,
        "",
    ))

def encontrar_url_proxima_pagina(html, url_atual, numero_pagina_atual):
    soup = BeautifulSoup(html, "html.parser")

    numero_proxima = str(numero_pagina_atual + 1)
    dominio_atual = urlsplit(url_atual).netloc

    candidatos = []

    for link in soup.find_all("a", href=True):
        href = link.get("href")

        if not href or href.startswith("javascript:"):
            continue

        texto = normalizar_texto(link.get_text(" ", strip=True)).lower()

        rel = " ".join(link.get("rel", [])).lower() if link.get("rel") else ""

        url_candidata = limpar_url(urljoin(url_atual, href))
        dominio_candidata = urlsplit(url_candidata).netloc

        if dominio_candidata and dominio_candidata != dominio_atual:
            continue

        eh_proxima = (
            texto == numero_proxima
            or texto in ["próxima", "proxima", "próximo", "proximo", ">", "»"]
            or "next" in rel
            or f"page={numero_proxima}" in url_candidata.lower()
            or f"pagina={numero_proxima}" in url_candidata.lower()
            or f"p={numero_proxima}" in url_candidata.lower()
            or f"pg_num={numero_proxima}" in url_candidata.lower()
        )   

        if eh_proxima:
            candidatos.append(url_candidata)

    if candidatos:
        return candidatos[0]

    return None

def extrair_dados_detalhe_produto(html):
    soup = BeautifulSoup(html, "html.parser")

    marca_nome = None
    codigo_produto = None

    # Marca/fornecedor na página do produto
    seletores_marca = [
        "table.tit-fornecedor h2.tit-fornecedor a",
        "h2.tit-fornecedor a",
        "a[href*='/fornecedor/']",
    ]

    for seletor in seletores_marca:
        elemento_marca = soup.select_one(seletor)

        if elemento_marca:
            marca_nome = normalizar_texto(
                elemento_marca.get_text(" ", strip=True)
            )

            if marca_nome:
                break

    # Código na página do produto
    elemento_codigo = soup.select_one("a.idCopySKU")

    if elemento_codigo:
        codigo_produto = (
            elemento_codigo.get("cod")
            or elemento_codigo.get_text(" ", strip=True)
        )

    if not codigo_produto:
        elemento_codigo_oculto = soup.select_one("#idCopySKUHidden")

        if elemento_codigo_oculto:
            codigo_produto = elemento_codigo_oculto.get_text(" ", strip=True)

    if codigo_produto:
        codigo_produto = normalizar_texto(codigo_produto)
        codigo_produto = codigo_produto.replace(" ", "")
        codigo_produto = codigo_produto.replace("Cód.", "")
        codigo_produto = codigo_produto.replace("Cod.", "")
        codigo_produto = codigo_produto.strip("()")

    return {
        "marca_nome": marca_nome,
        "codigo_produto": codigo_produto,
    }

def enriquecer_produto_com_detalhe(driver, produto, pausa=0.4):
    url_produto = produto.get("url") or produto.get("url_produto")

    if not url_produto:
        return produto

    try:
        driver.get(url_produto)
        time.sleep(pausa)

        dados_detalhe = extrair_dados_detalhe_produto(driver.page_source)

        marca_nome = dados_detalhe.get("marca_nome")
        codigo_produto = dados_detalhe.get("codigo_produto")

        if marca_nome:
            produto["marca_nome"] = marca_nome

        if codigo_produto:
            produto["codigo_site"] = codigo_produto

            if not produto.get("codigo_fabricante"):
                produto["codigo_fabricante"] = codigo_produto

    except Exception as erro:
        print(f"[WARN] Não consegui enriquecer detalhe do produto: {url_produto}")
        print(f"[WARN] Erro: {erro}")

    return produto

def coletar_produtos_dutra(
    url_base,
    limite=None,
    max_paginas=20,
    nome_fonte=None,
):
    produtos_coletados = []
    urls_ja_coletadas = set()

    if not nome_fonte:
        nome_fonte = "Dutra Máquinas"

    if limite is not None:
        try:
            limite = int(limite)
        except Exception:
            limite = None

    if max_paginas is not None:
        try:
            max_paginas = int(max_paginas)
        except Exception:
            max_paginas = 20

    options = Options()
    options.add_argument("start-maximized")

    driver = webdriver.Chrome(options=options)

    url_pagina = url_base

    try:
        for numero_pagina in range(1, max_paginas + 1):
            url_pagina = montar_url_dutra_pagina(
                url_base,
                numero_pagina,
                )
            if limite and len(produtos_coletados) >= limite:
                print(f"[INFO] Limite de {limite} produtos atingido.")
                break

            print("=" * 80)
            print(f"[INFO] Fonte: {nome_fonte}")
            print(f"[INFO] Acessando página {numero_pagina}: {url_pagina}")
            print("=" * 80)

            try:
                driver.get(url_pagina)
                time.sleep(5)
            except Exception as erro:
                print(f"[ERRO] Falha ao abrir página {numero_pagina}: {erro}")
                break

            html_da_pagina = driver.page_source or ""
            html_minusculo = html_da_pagina.lower()

            if "r$" not in html_minusculo:
                print("[AVISO] Página não parece conter preços válidos. Coleta interrompida.")
                break

            itens_restantes = None

            if limite:
                itens_restantes = limite - len(produtos_coletados)

            produtos_da_pagina = extrair_produtos_do_html(
                html_da_pagina,
                url_base=url_pagina,
                limite=itens_restantes,
            )

            print(f"[INFO] Produtos extraídos da página {numero_pagina}: {len(produtos_da_pagina)}")

            if not produtos_da_pagina:
                print("[INFO] Nenhum produto encontrado nesta página. Encerrando paginação.")
                break

            novos_nesta_pagina = 0

            for produto in produtos_da_pagina:
                produto = enriquecer_produto_com_detalhe(driver, produto)
                
                url_produto = produto.get("url")

                if not url_produto or url_produto in urls_ja_coletadas:
                    continue

                urls_ja_coletadas.add(url_produto)

                produto["ranking_geral"] = len(produtos_coletados) + 1

                produtos_coletados.append(produto)
                novos_nesta_pagina += 1

                if limite and len(produtos_coletados) >= limite:
                    break

            print(f"[INFO] Produtos novos adicionados da página {numero_pagina}: {novos_nesta_pagina}")
            print(f"[INFO] Total acumulado até agora: {len(produtos_coletados)}")

            if novos_nesta_pagina == 0:
                print("[INFO] Página sem produtos novos. Encerrando para evitar repetição infinita.")
                break

            if limite and len(produtos_coletados) >= limite:
                print(f"[INFO] Limite de {limite} produtos atingido.")
                break

    finally:
        print("[INFO] Fechando navegador...")
        driver.quit()

    print(f"[INFO] Coleta finalizada. Total de produtos coletados: {len(produtos_coletados)}")

    return produtos_coletados