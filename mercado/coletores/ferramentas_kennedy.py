import os
import ssl
import json
import re
import time
import certifi
from urllib.parse import urljoin, urlparse
from mercado.coletores.debug_utils import (
    salvar_debug_texto,
    salvar_debug_screenshot,
    debug_coletores_ativo,
)


os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

ssl._create_default_https_context = lambda: ssl.create_default_context(
    cafile=certifi.where()
)

import undetected_chromedriver as uc

from bs4 import BeautifulSoup

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


def criar_driver_ferramentas_kennedy(headless=False):
    """
    Cria navegador Chrome usando undetected_chromedriver.

    Uso recomendado apenas quando houver autorização do site monitorado.
    """

    options = uc.ChromeOptions()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--window-size=1400,1000")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Evita alguns problemas de certificado/conexão no Chrome.
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors=yes")

    # Mantém logs de rede para diagnóstico.
    options.set_capability(
        "goog:loggingPrefs",
        {
            "performance": "ALL",
            "browser": "ALL",
        },
    )

    try:
        driver = uc.Chrome(
            options=options,
            version_main=149,
            use_subprocess=False,
        )
    except Exception as erro:
        print(f"[ERRO] Não consegui iniciar o undetected_chromedriver: {erro}")
        raise

    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception as erro:
        print(f"[WARN] Não consegui ativar captura de rede CDP: {erro}")

    driver.set_page_load_timeout(60)

    return driver

def salvar_diagnostico_rede_kennedy(
    driver,
    arquivo_urls="debug_kennedy_network.txt",
    arquivo_respostas="debug_kennedy_performa_responses.txt",
):
    """
    Lê os logs de performance apenas quando COLETORES_DEBUG=1.

    Em uso normal, retorna listas vazias para não deixar a coleta lenta.
    """

    if not debug_coletores_ativo():
        return [], []

    urls = []
    respostas = []

    try:
        logs = driver.get_log("performance")
    except Exception as erro:
        print(f"[WARN] Não consegui ler logs de performance: {erro}")
        return [], []

    for entrada in logs:
        try:
            mensagem = json.loads(entrada.get("message", "{}")).get("message", {})
        except Exception:
            continue

        metodo = mensagem.get("method")
        params = mensagem.get("params", {})

        if metodo == "Network.requestWillBeSent":
            request = params.get("request", {})
            url = request.get("url")

            if url:
                urls.append(url)

        elif metodo == "Network.responseReceived":
            response = params.get("response", {})
            request_id = params.get("requestId")
            url = response.get("url")

            if url:
                urls.append(url)

            if request_id and url and "api.performa.ai" in url:
                try:
                    body = driver.execute_cdp_cmd(
                        "Network.getResponseBody",
                        {"requestId": request_id},
                    )

                    texto = body.get("body", "")

                    respostas.append(
                        {
                            "url": url,
                            "body": texto,
                        }
                    )

                except Exception as erro:
                    respostas.append(
                        {
                            "url": url,
                            "body": f"[ERRO AO LER BODY] {erro}",
                        }
                    )

    urls_unicas = []

    for url in urls:
        if url not in urls_unicas:
            urls_unicas.append(url)

    conteudo_urls = "\n".join(urls_unicas)

    conteudo_respostas = ""

    for indice, item in enumerate(respostas, start=1):
        conteudo_respostas += "=" * 120 + "\n"
        conteudo_respostas += f"RESPOSTA {indice}\n"
        conteudo_respostas += f"URL: {item['url']}\n"
        conteudo_respostas += "-" * 120 + "\n"
        conteudo_respostas += item["body"][:30000]
        conteudo_respostas += "\n\n"

    salvar_debug_texto(arquivo_urls, conteudo_urls)
    salvar_debug_texto(arquivo_respostas, conteudo_respostas)

    print(f"[DEBUG] URLs de rede salvas em {arquivo_urls}. Total: {len(urls_unicas)}")
    print(f"[DEBUG] Respostas Performa salvas em {arquivo_respostas}. Total: {len(respostas)}")

    return urls_unicas, respostas

def normalizar_texto(valor):
    if valor is None:
        return ""

    return re.sub(r"\s+", " ", str(valor)).strip()


def normalizar_preco(valor):
    if valor is None:
        return None

    texto = str(valor)

    match = re.search(r"(?:R\$)?\s*([\d\.]+,\d{2})", texto)

    if not match:
        return None

    numero = match.group(1)
    numero = numero.replace(".", "").replace(",", ".")

    try:
        return float(numero)
    except Exception:
        return None


def normalizar_url(url_base, href):
    if not href:
        return None

    return urljoin(url_base, href)


def parece_url_produto(url):
    if not url:
        return False

    url_lower = url.lower()

    bloqueios = [
        "/c/",
        "/ferramentas-manuais",
        "/abrasivos",
        "/epi",
        "/ferragens",
        "/institucional",
        "/politica",
        "/blog",
        "/login",
        "/carrinho",
        "/checkout",
        "/conta",
        "wa.me",
        "facebook",
        "instagram",
        "youtube",
        "linkedin",
    ]

    if any(bloqueio in url_lower for bloqueio in bloqueios):
        # Não descarta URLs de produto apenas se tiver padrão claro depois,
        # mas evita menus e categorias.
        if "/produto" not in url_lower and "/p/" not in url_lower:
            return False

    padroes_produto = [
        "/produto/",
        "/p/",
    ]

    if any(padrao in url_lower for padrao in padroes_produto):
        return True

    return False


def extrair_marca_pelo_nome_kennedy(nome):
    if not nome:
        return ""

    nome_upper = nome.upper()

    marcas_conhecidas = [
        "TRAMONTINA",
        "VONDER",
        "WORKER",
        "GEDORE",
        "KRAFT",
        "BELZER",
        "STANLEY",
        "IRWIN",
        "MAYLE",
        "ROCAST",
        "MTX",
        "SPARTA",
        "BLACK JACK",
        "BUMAFFER",
        "BUMAFER",
        "EDA",
        "NOVE54",
    ]

    for marca in marcas_conhecidas:
        if marca in nome_upper:
            return marca.title()

    return ""

def extrair_codigo_por_url(url):
    if not url:
        return ""

    caminho = urlparse(url).path.strip("/")

    if not caminho:
        return ""

    partes = caminho.split("/")

    ultimo = partes[-1]

    return ultimo[:100]


def extrair_nome_do_card(card, link):
    candidatos = []

    atributos = [
        link.get("title"),
        link.get("aria-label"),
        link.get("data-name"),
        link.get("data-product-name"),
    ]

    candidatos.extend(atributos)

    seletores = [
        "h1",
        "h2",
        "h3",
        "h4",
        ".nome",
        ".name",
        ".product-name",
        ".produto-nome",
        ".titulo",
        ".title",
        "[class*='name']",
        "[class*='nome']",
        "[class*='title']",
        "[class*='titulo']",
    ]

    for seletor in seletores:
        elemento = card.select_one(seletor)

        if elemento:
            candidatos.append(elemento.get_text(" ", strip=True))

    candidatos.append(link.get_text(" ", strip=True))

    for candidato in candidatos:
        texto = normalizar_texto(candidato)

        if texto and len(texto) >= 8 and "R$" not in texto:
            return texto

    return ""


def extrair_precos_do_card(card):
    texto = card.get_text(" ", strip=True)

    precos = re.findall(r"R\$\s*[\d\.]+,\d{2}", texto)

    if not precos:
        return None, None, None, None

    valores = [normalizar_preco(preco) for preco in precos]
    valores = [valor for valor in valores if valor is not None]

    if not valores:
        return None, None, None, None

    preco_atual = valores[0]
    preco_antigo = None

    if len(valores) >= 2:
        maior = max(valores)
        menor = min(valores)

        preco_atual = menor
        preco_antigo = maior if maior != menor else None

    quantidade_parcelas = None
    valor_parcela = None
    preco_prazo = None

    match_parcela = re.search(
        r"(\d+)\s*x\s*de\s*R\$\s*([\d\.]+,\d{2})",
        texto,
        flags=re.IGNORECASE,
    )

    if match_parcela:
        try:
            quantidade_parcelas = int(match_parcela.group(1))
            valor_parcela = normalizar_preco(f"R$ {match_parcela.group(2)}")

            if quantidade_parcelas and valor_parcela:
                preco_prazo = round(quantidade_parcelas * valor_parcela, 2)
        except Exception:
            pass

    return preco_atual, preco_antigo, preco_prazo, quantidade_parcelas, valor_parcela


def subir_para_card_com_preco(link):
    atual = link

    for _ in range(6):
        if not atual:
            break

        texto = atual.get_text(" ", strip=True)

        if "R$" in texto and len(texto) > 20:
            return atual

        atual = atual.parent

    return link.parent or link

def encontrar_url_produto_performa(card, url_base):
    """
    Tenta encontrar a URL do produto a partir do bloco performa-details-vitrine.
    A URL pode estar em um link pai ou em algum link próximo dentro do card.
    """

    link_pai = card.find_parent("a", href=True)

    if link_pai and link_pai.get("href"):
        return urljoin(url_base, link_pai.get("href"))

    atual = card

    for _ in range(8):
        if not atual:
            break

        link = atual.select_one("a[href]")

        if link and link.get("href"):
            href = link.get("href")

            href_lower = href.lower()

            if not any(x in href_lower for x in ["javascript:", "#", "carrinho", "checkout"]):
                return urljoin(url_base, href)

        atual = atual.parent

    return None


def extrair_produtos_performa_kennedy(html, url_base, limite=None):
    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select(".performa-details-vitrine")

    print(f"[DEBUG] Cards performa encontrados: {len(cards)}")

    produtos = []
    urls_vistas = set()

    for card in cards:
        nome_el = card.select_one(".performa-name-vitrine")
        codigo_el = card.select_one(".performa-code-vitrine")
        preco_el = card.select_one(".performa-price-vitrine")
        preco_vista_el = card.select_one(".performa-list-price-vitrine")
        parcelas_el = card.select_one(".performa-installments-vitrine")

        nome = normalizar_texto(nome_el.get_text(" ", strip=True)) if nome_el else ""

        if not nome:
            continue

        codigo_texto = codigo_el.get_text(" ", strip=True) if codigo_el else ""
        codigo_site = ""

        match_codigo = re.search(r"Ref\.?\s*:\s*([A-Za-z0-9\.\-\/]+)", codigo_texto, flags=re.IGNORECASE)

        if match_codigo:
            codigo_site = normalizar_texto(match_codigo.group(1))

        preco_tabela = normalizar_preco(preco_el.get_text(" ", strip=True)) if preco_el else None
        preco_vista = normalizar_preco(preco_vista_el.get_text(" ", strip=True)) if preco_vista_el else None

        preco_prazo = None
        quantidade_parcelas = None
        valor_parcela = None

        texto_parcelas = parcelas_el.get_text(" ", strip=True) if parcelas_el else ""

        # Exemplo:
        # R$ 300,02 em 7x de R$ 42,86 s/ juros
        match_parcela = re.search(
            r"R\$\s*([\d\.]+,\d{2})\s*em\s*(\d+)\s*x\s*de\s*R\$\s*([\d\.]+,\d{2})",
            texto_parcelas,
            flags=re.IGNORECASE,
        )

        if match_parcela:
            preco_prazo = normalizar_preco(f"R$ {match_parcela.group(1)}")

            try:
                quantidade_parcelas = int(match_parcela.group(2))
            except Exception:
                quantidade_parcelas = None

            valor_parcela = normalizar_preco(f"R$ {match_parcela.group(3)}")

        # Regra inicial:
        # preço atual = preço à vista, se existir.
        # preço antigo = preço maior/tabela, se existir.
        preco_atual = preco_vista or preco_prazo or preco_tabela
        preco_antigo = preco_tabela

        if preco_antigo == preco_atual:
            preco_antigo = None

        if preco_atual is None:
            continue

        url_produto = encontrar_url_produto_performa(card, url_base)

        if url_produto and url_produto in urls_vistas:
            continue

        if url_produto:
            urls_vistas.add(url_produto)

        produtos.append(
            {
                "nome": nome,
                "nome_original": nome,
                "url": url_produto or "",
                "codigo_site": codigo_site,
                "codigo_fabricante": codigo_site,
                "marca_nome": extrair_marca_pelo_nome_kennedy(nome),
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "preco_prazo": preco_prazo,
                "quantidade_parcelas": quantidade_parcelas,
                "valor_parcela": valor_parcela,
                "ean": "",
                "estoque": None,
            }
        )

        if limite and len(produtos) >= limite:
            break

    return produtos

def limpar_texto_kennedy(texto):
    texto = normalizar_texto(texto)

    substituicoes = {
        "â%": '"',
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "Ã©": "é",
        "Ã£": "ã",
        "Ã§": "ç",
        "Ã³": "ó",
        "Ãº": "ú",
        "Ã¡": "á",
        "Ãª": "ê",
        "Ã­": "í",
    }

    for errado, certo in substituicoes.items():
        texto = texto.replace(errado, certo)

    return texto

def extrair_produtos_listagem_kennedy(html, url_base, limite=None):
    produtos_performa = extrair_produtos_performa_kennedy(
        html=html,
        url_base=url_base,
        limite=limite,
    )

    if produtos_performa:
        return produtos_performa
    
    soup = BeautifulSoup(html, "html.parser")

    produtos = []
    urls_vistas = set()

    links = soup.select("a[href]")

    for link in links:
        href = link.get("href")
        url = normalizar_url(url_base, href)

        if not url:
            continue

        if url in urls_vistas:
            continue

        card = subir_para_card_com_preco(link)

        texto_card = card.get_text(" ", strip=True)

        if "R$" not in texto_card:
            continue

        nome = extrair_nome_do_card(card, link)

        if not nome:
            continue

        preco_atual, preco_antigo, preco_prazo, quantidade_parcelas, valor_parcela = extrair_precos_do_card(card)

        if preco_atual is None:
            continue

        urls_vistas.add(url)

        codigo_site = extrair_codigo_por_url(url)

        produtos.append(
            {
                "nome": nome,
                "nome_original": nome,
                "url": url,
                "codigo_site": codigo_site,
                "codigo_fabricante": "",
                "marca_nome": "",
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "preco_prazo": preco_prazo,
                "quantidade_parcelas": quantidade_parcelas,
                "valor_parcela": valor_parcela,
                "ean": "",
                "estoque": None,
            }
        )

        if limite and len(produtos) >= limite:
            break

    return produtos


def extrair_json_lds(html):
    soup = BeautifulSoup(html, "html.parser")
    resultados = []

    for script in soup.select('script[type="application/ld+json"]'):
        conteudo = script.string or script.get_text()

        if not conteudo:
            continue

        try:
            dados = json.loads(conteudo)
            resultados.append(dados)
        except Exception:
            continue

    return resultados


def procurar_produto_em_json_ld(obj):
    if isinstance(obj, dict):
        tipo = obj.get("@type")

        if isinstance(tipo, list):
            tipos = [str(t).lower() for t in tipo]
        else:
            tipos = [str(tipo).lower()]

        if "product" in tipos:
            return obj

        for valor in obj.values():
            encontrado = procurar_produto_em_json_ld(valor)

            if encontrado:
                return encontrado

    if isinstance(obj, list):
        for item in obj:
            encontrado = procurar_produto_em_json_ld(item)

            if encontrado:
                return encontrado

    return None


def extrair_dados_detalhe_kennedy(html):
    dados = {}

    soup = BeautifulSoup(html, "html.parser")

    for json_ld in extrair_json_lds(html):
        produto = procurar_produto_em_json_ld(json_ld)

        if not produto:
            continue

        nome = produto.get("name")
        sku = produto.get("sku")
        mpn = produto.get("mpn")
        gtin = (
            produto.get("gtin13")
            or produto.get("gtin")
            or produto.get("gtin14")
            or produto.get("gtin8")
        )

        marca = produto.get("brand")

        if isinstance(marca, dict):
            marca_nome = marca.get("name")
        else:
            marca_nome = marca

        ofertas = produto.get("offers")

        if isinstance(ofertas, list) and ofertas:
            ofertas = ofertas[0]

        if isinstance(ofertas, dict):
            preco = ofertas.get("price")
            disponibilidade = ofertas.get("availability")

            try:
                if preco is not None:
                    dados["preco_atual"] = float(str(preco).replace(",", "."))
            except Exception:
                pass

            if disponibilidade:
                dados["disponibilidade_texto"] = str(disponibilidade)

        if nome:
            dados["nome_original"] = normalizar_texto(nome)

        if sku:
            dados["codigo_site"] = normalizar_texto(sku)

        if mpn:
            dados["codigo_fabricante"] = normalizar_texto(mpn)

        if gtin:
            dados["ean"] = normalizar_texto(gtin)

        if marca_nome:
            dados["marca_nome"] = normalizar_texto(marca_nome)

        break

    texto = soup.get_text(" ", strip=True)

    if not dados.get("codigo_fabricante"):
        padroes_codigo = [
            r"C[oó]digo\s*[:\-]?\s*([A-Za-z0-9\.\-\/]+)",
            r"Refer[eê]ncia\s*[:\-]?\s*([A-Za-z0-9\.\-\/]+)",
            r"SKU\s*[:\-]?\s*([A-Za-z0-9\.\-\/]+)",
        ]

        for padrao in padroes_codigo:
            match = re.search(padrao, texto, flags=re.IGNORECASE)

            if match:
                dados["codigo_fabricante"] = normalizar_texto(match.group(1))
                break

    if not dados.get("marca_nome"):
        padroes_marca = [
            r"Marca\s*[:\-]?\s*([A-Za-zÀ-ÿ0-9 \.\-]+)",
            r"Fabricante\s*[:\-]?\s*([A-Za-zÀ-ÿ0-9 \.\-]+)",
        ]

        for padrao in padroes_marca:
            match = re.search(padrao, texto, flags=re.IGNORECASE)

            if match:
                marca = normalizar_texto(match.group(1))
                marca = marca.split(" ")[0] if len(marca.split(" ")) > 4 else marca
                dados["marca_nome"] = marca
                break

    return dados


def enriquecer_produto_com_detalhe_kennedy(driver, produto, pausa=1.5):
    url_produto = produto.get("url")

    if not url_produto:
        return produto

    try:
        driver.get(url_produto)
        time.sleep(pausa)

        html = driver.page_source
        dados_detalhe = extrair_dados_detalhe_kennedy(html)

        for chave, valor in dados_detalhe.items():
            if valor not in [None, ""]:
                produto[chave] = valor

    except Exception as erro:
        print(f"[WARN] Não consegui enriquecer detalhe do produto Kennedy: {url_produto}")
        print(f"[WARN] Erro: {erro}")

    return produto


def encontrar_proxima_pagina_kennedy(html, url_atual):
    soup = BeautifulSoup(html, "html.parser")

    seletores = [
        'a[rel="next"]',
        'a[aria-label*="Próxima"]',
        'a[aria-label*="proxima"]',
        'a[aria-label*="Next"]',
    ]

    for seletor in seletores:
        link = soup.select_one(seletor)

        if link and link.get("href"):
            return urljoin(url_atual, link.get("href"))

    for link in soup.select("a[href]"):
        texto = normalizar_texto(link.get_text(" ", strip=True)).lower()

        if texto in ["próxima", "proxima", "next", ">"]:
            return urljoin(url_atual, link.get("href"))

    return None


def aguardar_produtos_kennedy(driver, timeout=20):
    """
    Aguarda os produtos da vitrine Kennedy carregarem na página.

    A Kennedy renderiza os produtos em blocos:
    .performa-details-vitrine
    """

    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass

    # Pequenas rolagens ajudam páginas que carregam vitrine sob demanda.
    for _ in range(5):
        quantidade = driver.execute_script(
            "return document.querySelectorAll('.performa-details-vitrine').length;"
        )

        if quantidade and int(quantidade) > 0:
            print(f"[INFO] Produtos Kennedy encontrados no DOM: {quantidade}")
            return True

        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(1.5)

    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".performa-details-vitrine"))
        )

        quantidade = driver.execute_script(
            "return document.querySelectorAll('.performa-details-vitrine').length;"
        )

        print(f"[INFO] Produtos Kennedy encontrados após espera: {quantidade}")
        return True

    except TimeoutException:
        quantidade = driver.execute_script(
            "return document.querySelectorAll('.performa-details-vitrine').length;"
        )

        print(f"[WARN] Produtos Kennedy não encontrados após espera. Quantidade no DOM: {quantidade}")
        return False

def aguardar_vitrine_performa_kennedy(driver, timeout=60):
    """
    Aguarda a Performa AI montar a vitrine de produtos no DOM.

    A Kennedy usa classes como:
    .performa-details-vitrine
    .performa-name-vitrine
    .performa-price-vitrine
    """

    inicio = time.time()

    while time.time() - inicio < timeout:
        try:
            contadores = driver.execute_script(
                """
                return {
                    details: document.querySelectorAll('.performa-details-vitrine').length,
                    nomes: document.querySelectorAll('.performa-name-vitrine').length,
                    precos: document.querySelectorAll('.performa-price-vitrine').length,
                    htmlTemPerforma: document.documentElement.innerHTML.includes('performa-details-vitrine'),
                    textoTemPreco: document.body.innerText.includes('R$')
                };
                """
            )

            print(f"[DEBUG] Status Performa Kennedy: {contadores}")

            if (
                contadores.get("details", 0) > 0
                or contadores.get("nomes", 0) > 0
                or contadores.get("htmlTemPerforma")
            ):
                print("[INFO] Vitrine Performa Kennedy carregada.")
                return True

            # Rola a página para disparar carregamento deferido/lazy.
            driver.execute_script("window.scrollBy(0, 900);")
            time.sleep(2)

        except Exception as erro:
            print(f"[WARN] Erro aguardando Performa Kennedy: {erro}")
            time.sleep(2)

    print("[WARN] Vitrine Performa Kennedy não carregou dentro do tempo limite.")
    return False

def detectar_bloqueio_kennedy(driver, html=None):
    """
    Detecta bloqueio real de acesso automatizado na Ferramentas Kennedy.

    Importante:
    Não usar termos genéricos como 'blocked' ou 'cloudflare',
    porque eles podem aparecer dentro de scripts sem significar bloqueio real.
    """

    if html is None:
        try:
            html = driver.page_source
        except Exception:
            html = ""

    html_lower = (html or "").lower()

    termos_bloqueio_reais = [
        "sorry you have been blocked",
        "you have been blocked",
        "this website is using a security service to protect itself from online attacks",
        "the action you just performed triggered the security solution",
        "cloudflare ray id",
    ]

    if any(termo in html_lower for termo in termos_bloqueio_reais):
        return True

    try:
        titulo = (driver.title or "").lower()

        titulos_bloqueio = [
            "sorry you have been blocked",
            "access denied",
        ]

        if any(termo in titulo for termo in titulos_bloqueio):
            return True

    except Exception:
        pass

    return False

def aceitar_cookies_kennedy(driver):
    """
    Tenta aceitar o banner de cookies da Kennedy, se aparecer.
    """

    try:
        botoes = driver.find_elements(By.TAG_NAME, "button")

        for botao in botoes:
            texto = (botao.text or "").strip().lower()

            if texto in ["aceitar", "aceito", "concordo"]:
                try:
                    botao.click()
                    print("[INFO] Banner de cookies aceito.")
                    time.sleep(2)
                    return True
                except Exception:
                    pass

    except Exception as erro:
        print(f"[WARN] Não consegui tratar banner de cookies Kennedy: {erro}")

    return False

def aguardar_produtos_ou_performa_kennedy(driver, timeout=40):
    """
    Aguarda a página sair do carregamento visual.

    A página pode exibir skeletons cinza antes dos produtos aparecerem.
    """

    inicio = time.time()

    while time.time() - inicio < timeout:
        try:
            status = driver.execute_script(
                """
                return {
                    performaDetails: document.querySelectorAll('.performa-details-vitrine').length,
                    performaNames: document.querySelectorAll('.performa-name-vitrine').length,
                    performaPrices: document.querySelectorAll('.performa-price-vitrine').length,
                    textHasPrice: document.body.innerText.includes('R$'),
                    textLength: document.body.innerText.length,
                    hasSkeleton: document.body.innerText.includes('Alicate Universal')
                };
                """
            )

            print(f"[DEBUG] Status carregamento Kennedy: {status}")

            if (
                status.get("performaDetails", 0) > 0
                or status.get("performaNames", 0) > 0
                or status.get("performaPrices", 0) > 0
                or status.get("textHasPrice")
            ):
                print("[INFO] Produtos ou preços apareceram na página Kennedy.")
                return True

            driver.execute_script("window.scrollBy(0, 900);")
            time.sleep(2)

        except Exception as erro:
            print(f"[WARN] Erro aguardando carregamento Kennedy: {erro}")
            time.sleep(2)

    print("[WARN] Produtos/preços não apareceram no HTML dentro do tempo limite.")
    return False

def extrair_jsonp_performa_kennedy(texto):
    """
    Extrai JSON de respostas no formato:
    callBackAjaxPerforma_xxx({...})
    """

    if not texto:
        return None

    texto = texto.strip()

    inicio = texto.find("(")
    fim = texto.rfind(")")

    if inicio == -1 or fim == -1 or fim <= inicio:
        return None

    conteudo = texto[inicio + 1:fim]

    try:
        return json.loads(conteudo)
    except Exception:
        return None


def converter_produto_performa_kennedy(item):
    """
    Converte um item product_data da Performa para o formato padrão do projeto.
    """

    if not item:
        return None

    nome = limpar_texto_kennedy(item.get("name"))
    sku = normalizar_texto(item.get("sku"))
    marca = extrair_marca_pelo_nome_kennedy(nome)
    url = item.get("url") or ""
    gtin = normalizar_texto(item.get("gtin"))

    if not nome:
        return None

    preco_atual = item.get("list_price")
    preco_antigo = item.get("price")
    preco_prazo = item.get("boleto_price")

    mo_payment = item.get("mo_payment") or {}

    quantidade_parcelas = mo_payment.get("installment")
    valor_parcela = mo_payment.get("value")

    try:
        preco_atual = float(preco_atual) if preco_atual is not None else None
    except Exception:
        preco_atual = None

    try:
        preco_antigo = float(preco_antigo) if preco_antigo is not None else None
    except Exception:
        preco_antigo = None

    try:
        preco_prazo = float(preco_prazo) if preco_prazo is not None else None
    except Exception:
        preco_prazo = None

    try:
        quantidade_parcelas = int(quantidade_parcelas) if quantidade_parcelas else None
    except Exception:
        quantidade_parcelas = None

    try:
        valor_parcela = float(valor_parcela) if valor_parcela is not None else None
    except Exception:
        valor_parcela = None

    return {
        "nome": nome,
        "nome_original": nome,
        "url": url,
        "codigo_site": sku,
        "codigo_fabricante": sku,
        "marca_nome": marca,
        "ean": gtin,
        "preco_atual": preco_atual,
        "preco_antigo": preco_antigo,
        "preco_prazo": preco_prazo,
        "quantidade_parcelas": quantidade_parcelas,
        "valor_parcela": valor_parcela,
        "estoque": None,
    }


def extrair_produtos_de_respostas_performa_kennedy(respostas, limite=None):
    """
    Extrai produtos das respostas capturadas da Performa.

    Espera uma lista no formato:
    [
        {"url": "...", "body": "..."},
        ...
    ]
    """

    produtos = []
    chaves_vistas = set()

    for resposta in respostas or []:
        body = resposta.get("body", "")

        dados = extrair_jsonp_performa_kennedy(body)

        if not dados:
            continue

        product_data = dados.get("product_data") or []

        for item in product_data:
            produto = converter_produto_performa_kennedy(item)

            if not produto:
                continue

            chave = produto.get("url") or produto.get("codigo_site") or produto.get("nome")

            if chave in chaves_vistas:
                continue

            chaves_vistas.add(chave)
            produtos.append(produto)

            if limite and len(produtos) >= limite:
                return produtos

    return produtos

def coletar_produtos_ferramentas_kennedy(
    url_inicial=None,
    url_base=None,
    url=None,
    limite=500,
    max_paginas=10,
    headless=False,
    enriquecer_detalhe=False,
    falhar_se_bloqueado=False,
    **kwargs,
):
    """
    Coleta produtos da Ferramentas Kennedy.

    Estratégia:
    1. Abre a página com o driver configurado.
    2. Detecta bloqueio.
    3. Salva diagnóstico de rede.
    4. Tenta extrair produtos do HTML.
    5. Se o HTML não trouxer produtos, tenta extrair das respostas Performa.
    """

    if not url_inicial:
        url_inicial = url_base

    if not url_inicial:
        url_inicial = url

    if not url_inicial:
        url_inicial = kwargs.get("url")

    if not url_inicial:
        url_inicial = kwargs.get("url_base")

    if not url_inicial:
        print("[ERRO] Nenhuma URL inicial foi fornecida para a coleta.")
        return []

    driver = criar_driver_ferramentas_kennedy(headless=headless)

    produtos = []
    chaves_vistas = set()
    url_atual = url_inicial

    def tratar_bloqueio(html, mensagem):
        print(f"[WARN] {mensagem}")

        salvar_debug_texto("debug_kennedy_bloqueio.html", html or "")
        salvar_debug_screenshot("debug_kennedy_bloqueio.png", driver)

        if falhar_se_bloqueado:
            raise RuntimeError(mensagem)

        return []

    try:
        for pagina in range(1, max_paginas + 1):
            print("")
            print(f"[INFO] Acessando Página {pagina}: {url_atual}")

            try:
                driver.get(url_atual)
            except Exception as erro:
                print(f"[ERRO] Não consegui abrir a página: {erro}")
                break

            time.sleep(6)

            html_inicial = driver.page_source

            if detectar_bloqueio_kennedy(driver, html_inicial):
                return tratar_bloqueio(
                    html_inicial,
                    "Coleta bloqueada pela Ferramentas Kennedy. "
                    "A página retornou bloqueio real de segurança.",
                )
            aceitar_cookies_kennedy(driver)

            aguardar_produtos_ou_performa_kennedy(driver, timeout=30)

            html = driver.page_source
            # Rola a página para tentar disparar carregamentos dinâmicos.
            try:
                for _ in range(5):
                    driver.execute_script("window.scrollBy(0, 900);")
                    time.sleep(1.5)
            except Exception as erro:
                print(f"[WARN] Erro ao rolar página Kennedy: {erro}")

            # Tenta aguardar vitrine Performa, se a função existir.
            try:
                aguardar_vitrine_performa_kennedy(driver, timeout=20)
            except NameError:
                pass
            except Exception as erro:
                print(f"[WARN] Erro ao aguardar vitrine Performa Kennedy: {erro}")

            html = driver.page_source

            if detectar_bloqueio_kennedy(driver, html):
                return tratar_bloqueio(
                    html,
                    "Coleta bloqueada pela Ferramentas Kennedy após carregamento da página.",
                )

            # Salva HTML para análise.
            if pagina == 1:
                salvar_debug_texto("debug_kennedy_listagem.html", html)

            # Captura rede e respostas Performa.
            urls_rede = []
            respostas_performa = []

            try:
                urls_rede, respostas_performa = salvar_diagnostico_rede_kennedy(driver)
            except NameError:
                print("[WARN] Função salvar_diagnostico_rede_kennedy não encontrada.")
            except Exception as erro:
                print(f"[WARN] Não consegui salvar diagnóstico de rede Kennedy: {erro}")

            # 1ª tentativa: extrair do HTML.
            produtos_pagina = []

            try:
                produtos_pagina = extrair_produtos_listagem_kennedy(
                    html=html,
                    url_base=url_atual,
                    limite=limite,
                )
            except NameError:
                print("[WARN] Função extrair_produtos_listagem_kennedy não encontrada.")
            except Exception as erro:
                print(f"[WARN] Erro ao extrair produtos do HTML Kennedy: {erro}")

            print(f"[INFO] Produtos extraídos do HTML da página {pagina}: {len(produtos_pagina)}")

            # 2ª tentativa: extrair das respostas Performa.
            if not produtos_pagina:
                try:
                    produtos_pagina = extrair_produtos_de_respostas_performa_kennedy(
                        respostas=respostas_performa,
                        limite=limite,
                    )

                    print(
                        f"[INFO] Produtos extraídos das respostas Performa da página {pagina}: "
                        f"{len(produtos_pagina)}"
                    )

                except NameError:
                    print("[WARN] Função extrair_produtos_de_respostas_performa_kennedy não encontrada.")
                except Exception as erro:
                    print(f"[WARN] Erro ao extrair produtos das respostas Performa Kennedy: {erro}")

            novos = 0

            for item in produtos_pagina:
                url_produto = item.get("url") or ""
                codigo_site = item.get("codigo_site") or ""
                nome = item.get("nome") or item.get("nome_original") or ""

                chave = url_produto or codigo_site or nome

                if not chave:
                    continue

                if chave in chaves_vistas:
                    continue

                chaves_vistas.add(chave)

                if enriquecer_detalhe and url_produto:
                    try:
                        item = enriquecer_produto_com_detalhe_kennedy(driver, item)
                    except NameError:
                        pass
                    except Exception as erro:
                        print(f"[WARN] Erro ao enriquecer produto Kennedy: {erro}")

                item["ranking"] = len(produtos) + 1

                produtos.append(item)
                novos += 1

                if limite and len(produtos) >= limite:
                    print(f"[INFO] Limite de {limite} produtos atingido.")
                    print("")
                    print(f"[FIM] Processo encerrado. Total de produtos coletados com sucesso: {len(produtos)}")
                    return produtos

            print(f"[INFO] Fim da página {pagina}. Extraídos {novos} novos produtos nesta página.")

            # Próxima página, se existir.
            proxima = None

            try:
                proxima = encontrar_proxima_pagina_kennedy(html, url_atual)
            except NameError:
                pass
            except Exception as erro:
                print(f"[WARN] Erro ao procurar próxima página Kennedy: {erro}")

            if not proxima or proxima == url_atual:
                print("[INFO] Botão de próxima página não encontrado. Finalizando paginação.")
                break

            url_atual = proxima

        print("")
        print(f"[FIM] Processo encerrado. Total de produtos coletados com sucesso: {len(produtos)}")
        return produtos

    finally:
        try:
            driver.quit()
        except Exception:
            pass
