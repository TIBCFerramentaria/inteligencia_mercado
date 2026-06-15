import time
import os
import re
from decimal import Decimal
from urllib.parse import urljoin, urldefrag, urlsplit, urlunsplit

# IMPORTANTE: Removido 'import requests' para a coleta da página,
# pois agora usamos o Selenium para gerenciar o tráfego com segurança.
from bs4 import BeautifulSoup

# Importações do Selenium e das ferramentas de proteção adicionadas:
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth


URL_MAIS_VENDIDOS = "https://www.lojadomecanico.com.br/hotsite/maisvendidos"


def normalizar_texto(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto).strip()


def limpar_url(url):
    url, _fragmento = urldefrag(url)
    partes = urlsplit(url)
    return urlunsplit((partes.scheme, partes.netloc, partes.path, "", ""))


def converter_preco_para_decimal(texto_preco):
    if not texto_preco:
        return None

    texto = texto_preco.replace("R$", "").replace("\xa0", " ").strip()
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

    # Normaliza "R$" com espaço padrão.
    texto = re.sub(r"R\$\s*", "R$ ", texto)

    # Corrige casos como:
    # R$ 5.321 ,11 -> R$ 5.321,11
    texto = re.sub(r"(\d)\s+,\s*(\d{2})", r"\1,\2", texto)

    return texto.strip()


def encontrar_precos_no_texto(texto):
    texto = normalizar_texto_monetario(texto)

    return re.findall(
        r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2}",
        texto,
    )


def extrair_preco_em_texto(texto):
    precos = encontrar_precos_no_texto(texto)

    if not precos:
        return None

    return converter_preco_para_decimal(precos[0])


def extrair_preco_a_vista(bloco_produto):
    if not hasattr(bloco_produto, "select_one"):
        return None

    seletores_preco_vista = [
        ".container__price p.price",
        "p.price",
        "div.price",
        ".price",
    ]

    for seletor in seletores_preco_vista:
        elemento_preco = bloco_produto.select_one(seletor)

        if not elemento_preco:
            continue

        texto_preco = elemento_preco.get_text(" ", strip=True)
        preco = extrair_preco_em_texto(texto_preco)

        if preco is not None:
            return preco

    return None


def extrair_preco_prazo_e_parcela(bloco_produto):
    preco_prazo = None
    quantidade_parcelas = None
    valor_parcela = None

    if not hasattr(bloco_produto, "select_one"):
        return preco_prazo, quantidade_parcelas, valor_parcela

    div_parcelamento = bloco_produto.select_one(
        "div.parcel, .parcel, [class*='parcel']"
    )

    if not div_parcelamento:
        return preco_prazo, quantidade_parcelas, valor_parcela

    texto_parcelamento = div_parcelamento.get_text(" ", strip=True)
    texto_parcelamento = normalizar_texto_monetario(texto_parcelamento)

    precos_encontrados = encontrar_precos_no_texto(texto_parcelamento)

    # Exemplos aceitos:
    # "ou R$ 5.321,11 em 10x R$ 532,12 sem juros no cartão"
    # "à vista em 10x R$ 113,90 sem juros no cartão"

    parcelas_match = re.search(
        r"(\d+)\s*x\s*(?:de\s*)?(R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2})",
        texto_parcelamento,
        flags=re.IGNORECASE,
    )

    if parcelas_match:
        quantidade_parcelas = int(parcelas_match.group(1))
        valor_parcela = converter_preco_para_decimal(parcelas_match.group(2))

    # Se houver dois preços:
    # primeiro = preço total a prazo
    # segundo = valor da parcela
    if len(precos_encontrados) >= 2:
        preco_prazo = converter_preco_para_decimal(precos_encontrados[0])

        if valor_parcela is None:
            valor_parcela = converter_preco_para_decimal(precos_encontrados[1])

    # Se houver só um preço, normalmente ele é o valor da parcela.
    elif len(precos_encontrados) == 1 and valor_parcela is None:
        valor_parcela = converter_preco_para_decimal(precos_encontrados[0])

    # Se não houver preço total a prazo, calcula:
    # preco_prazo = parcelas x valor_parcela
    if preco_prazo is None and quantidade_parcelas and valor_parcela:
        preco_prazo = valor_parcela * quantidade_parcelas

    return preco_prazo, quantidade_parcelas, valor_parcela


def extrair_precos(bloco_produto):
    preco_atual = None
    preco_antigo = None

    # 1. Preço à vista / Pix / boleto.
    preco_atual = extrair_preco_a_vista(bloco_produto)

    # 2. Texto geral do card para preço antigo e fallback.
    if hasattr(bloco_produto, "get_text"):
        texto_bloco = bloco_produto.get_text(" ", strip=True)
    else:
        texto_bloco = str(bloco_produto)

    texto_bloco = normalizar_texto_monetario(texto_bloco)
    texto_bloco_upper = texto_bloco.upper()

    # 3. Preço antigo, quando existir "DE:".
    if "DE:" in texto_bloco_upper:
        precos_encontrados = encontrar_precos_no_texto(texto_bloco)

        if len(precos_encontrados) >= 2:
            preco_antigo = converter_preco_para_decimal(precos_encontrados[0])

            if preco_atual is None:
                preco_atual = converter_preco_para_decimal(precos_encontrados[1])

    # 4. Fallback para preço atual.
    if preco_atual is None:
        preco_atual = extrair_preco_em_texto(texto_bloco)

    # 5. Preço a prazo e parcelamento.
    preco_prazo, quantidade_parcelas, valor_parcela = extrair_preco_prazo_e_parcela(
        bloco_produto
    )

    return (
        preco_atual,
        preco_antigo,
        preco_prazo,
        quantidade_parcelas,
        valor_parcela,
    )

def extrair_desconto(texto_bloco):
    match = re.search(r"(\d{1,3})\s*%\s*R\$", texto_bloco)
    if not match:
        return None

    try:
        return Decimal(match.group(1))
    except Exception:
        return None


def extrair_nota_avaliacoes(texto_bloco):
    match = re.search(r"(\d{1,2}[,.]\d{1,2})\s*\((\d+)\)", texto_bloco)
    if not match:
        return None, None

    nota = match.group(1).replace(",", ".")
    avaliacoes = match.group(2)

    try:
        nota = Decimal(nota)
    except Exception:
        nota = None

    try:
        avaliacoes = int(avaliacoes)
    except Exception:
        avaliacoes = None

    return nota, avaliacoes


def extrair_marca_codigo_fabricante(nome_produto):
    nome = normalizar_texto(nome_produto).upper()

    match = re.search(r"\b([A-Z][A-Z0-9]{1,})-([A-Z0-9][A-Z0-9\.\+\/-]*)$", nome)
    if not match:
        return None, None

    marca = match.group(1).strip()
    codigo = match.group(2).strip()

    return marca, codigo


def extrair_codigo_site(url):
    match = re.search(r"/produto/(\d+)", url)
    if not match:
        return None

    return match.group(1)


def parece_titulo_produto(texto):
    texto = normalizar_texto(texto)

    if len(texto) < 25:
        return False

    if "R$" in texto:
        return False

    termos_ruido = [
        "cupons de desconto",
        "frete grátis",
        "vendas corporativas",
        "nossas lojas",
        "atendimento",
        "meus pedidos",
        "minha conta",
        "carrinho",
        "tudo em",
        "ver todos",
        "departamento",
        "categoria",
    ]

    texto_lower = texto.lower()

    for termo in termos_ruido:
        if termo in texto_lower:
            return False

    if "-" in texto and len(texto.split("-")[-1]) >= 2:
        return True

    termos_produto = [
        "pol",
        "w",
        "v",
        "hp",
        "litros",
        "toneladas",
        "profissional",
        "bivolt",
        "monofásico",
        "trifásico",
    ]

    return any(termo in texto_lower for termo in termos_produto)

def localizar_card_produto(link):
    atual = link

    for _ in range(10):
        if not atual:
            break

        if not hasattr(atual, "get_text"):
            break

        texto = atual.get_text(" ", strip=True)

        tem_preco = "R$" in texto
        tem_link_produto = atual.find(
            "a",
            href=lambda href: href and "/produto/" in href
        )

        tem_area_preco = atual.select_one(
            ".container__price, p.price, div.price, .price, div.parcel, .parcel, [class*='parcel']"
        )

        if tem_preco and tem_link_produto and tem_area_preco:
            return atual

        atual = atual.parent

    return link.parent

def montar_mapa_links(soup):
    candidatos = []

    for link in soup.find_all("a", href=True):
        texto = normalizar_texto(link.get_text(" ", strip=True))
        href = link.get("href", "")

        if not parece_titulo_produto(texto):
            continue

        if not href or href.startswith("javascript:"):
            continue

        url = limpar_url(urljoin(URL_MAIS_VENDIDOS, href))
        card_produto = localizar_card_produto(link)

        candidatos.append({
            "nome": texto,
            "url": url,
            "card": card_produto,
        })

    return candidatos

def localizar_indice_linha(linhas, texto, inicio=0):
    texto_normalizado = normalizar_texto(texto)

    for indice in range(inicio, len(linhas)):
        if normalizar_texto(linhas[indice]) == texto_normalizado:
            return indice

    return None

def extrair_produtos_do_html(html, limite=None):
    soup = BeautifulSoup(html, "html.parser")

    linhas = [
        normalizar_texto(linha)
        for linha in soup.get_text("\n", strip=True).split("\n")
        if normalizar_texto(linha)
    ]

    candidatos = montar_mapa_links(soup)

    produtos = []
    nomes_vistos = set()
    ultimo_indice_usado = 0

    for candidato in candidatos:
        nome = candidato["nome"]
        url = candidato["url"]
        card_produto = candidato.get("card")

        chave = nome.upper()

        if chave in nomes_vistos:
            continue

        indice = localizar_indice_linha(linhas, nome, inicio=ultimo_indice_usado)

        if indice is None:
            indice = localizar_indice_linha(linhas, nome, inicio=0)

        if indice is None:
            continue

        bloco_linhas = linhas[indice: indice + 18]
        texto_bloco = " ".join(bloco_linhas)

        if card_produto and hasattr(card_produto, "get_text"):
            texto_card = card_produto.get_text(" ", strip=True)
        else:
            texto_card = texto_bloco

        texto_para_extracao = texto_card or texto_bloco

        if "R$" not in texto_para_extracao:
            continue

        (
            preco_atual,
            preco_antigo,
            preco_prazo,
            quantidade_parcelas,
            valor_parcela,
        ) = extrair_precos(card_produto if card_produto else texto_para_extracao)

        if preco_atual is None:
            continue

        desconto_percentual = extrair_desconto(texto_para_extracao)
        nota_media, quantidade_avaliacoes = extrair_nota_avaliacoes(texto_para_extracao)
        marca_nome, codigo_fabricante = extrair_marca_codigo_fabricante(nome)
        codigo_site = extrair_codigo_site(url)

        produto = {
            "nome_original": nome,
            "url": url,
            "codigo_site": codigo_site,
            "marca_nome": marca_nome,
            "codigo_fabricante": codigo_fabricante,
            "preco_atual": preco_atual,
            "preco_antigo": preco_antigo,
            "preco_prazo": preco_prazo,
            "quantidade_parcelas": quantidade_parcelas,
            "valor_parcela": valor_parcela,
            "desconto_percentual": desconto_percentual,
            "nota_media": nota_media,
            "quantidade_avaliacoes": quantidade_avaliacoes,
            "ranking_geral": len(produtos) + 1,
            "disponivel": True,
            "texto_disponibilidade": "Disponível na página pública",
        }

        produtos.append(produto)
        nomes_vistos.add(chave)
        ultimo_indice_usado = indice + 1

        if limite and len(produtos) >= limite:
            break

    return produtos

def montar_url_mais_vendidos_pagina(pagina):
    if pagina <= 1:
        return URL_MAIS_VENDIDOS

    return f"{URL_MAIS_VENDIDOS}?page={pagina}"

def coletar_mais_vendidos(limite=None, max_paginas=20):
    produtos_coletados = []
    urls_ja_coletadas = set()

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

    print("[INFO] Configurando o navegador Chrome com Selenium-Stealth...")

    # --- CONFIGURAÇÃO DO SELENIUM E EXTENSÃO HCAPTCHA SOLVER ---
    options = Options()
    options.add_argument("start-maximized")

    # Aponta para a pasta onde está a extensão extraída do GitHub
    caminho_extensao = os.path.abspath("./hektcaptcha") 
    options.add_argument(f"--load-extension={caminho_extensao}")

    # Remove os alertas visuais e travas de automação do Chrome
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)

    # Aplica as camuflagens do Selenium-Stealth no navegador
    stealth(driver,
            languages=["pt-BR", "pt"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)

    try:
        for numero_pagina in range(1, max_paginas + 1):
            if limite and len(produtos_coletados) >= limite:
                print(f"[INFO] Limite de {limite} produtos atingido.")
                break

            # Usa a sua função auxiliar para gerar o link da página atual
            url_pagina = montar_url_mais_vendidos_pagina(numero_pagina)

            print("=" * 80)
            print(f"[INFO] Acessando página {numero_pagina}: {url_pagina}")
            print("=" * 80)

            try:
                # O Selenium abre a URL da página atual
                driver.get(url_pagina)
                time.sleep(5)  # Tempo padrão de espera para o carregamento

            except Exception as erro:
                print(f"[ERRO] Falha ao abrir página {numero_pagina}: {erro}")
                break

            # --- MONITORAMENTO E QUEBRA AUTOMÁTICA DO hCAPTCHA ---
            html_da_pagina = driver.page_source
            html_minusculo = html_da_pagina.lower()

            if "hcaptcha" in html_minusculo or "captcha" in html_minusculo:
                print("[AVISO] hCaptcha detectado! Aguardando a extensão Hcaptcha Solver agir...")
                
                # Monitora o token do hCaptcha por até 60 segundos por página
                tempo_maximo = 60  
                inicio = time.time()
                while time.time() - inicio < tempo_maximo:
                    try:
                        token = driver.execute_script("return hcaptcha.getResponse();")
                        if token and len(token) > 0:
                            print("[SUCESSO] hCaptcha foi decodificado pela extensão!")
                            time.sleep(3)  # Aguarda a tela atualizar após o sumiço do captcha
                            break
                    except Exception:
                        pass
                    time.sleep(2)
                else:
                    print("[AVISO] A extensão demorou muito para responder. Tentando continuar assim mesmo.")

                # Atualiza o código HTML após a liberação do Captcha
                html_da_pagina = driver.page_source
                html_minusculo = html_da_pagina.lower()

            if "r$" not in html_minusculo and "adicionar ao carrinho" not in html_minusculo:
                print("[AVISO] Página não parece conter produtos/preços válidos. Coleta interrompida.")
                break

            itens_restantes = None
            if limite:
                itens_restantes = limite - len(produtos_coletados)

            # Envia o HTML limpo obtido pelo Selenium para a sua função BeautifulSoup original
            produtos_da_pagina = extrair_produtos_do_html(
                html_da_pagina,
                limite=itens_restantes,
            )

            print(f"[INFO] Produtos extraídos da página {numero_pagina}: {len(produtos_da_pagina)}")

            if not produtos_da_pagina:
                print("[INFO] Nenhum produto encontrado nesta página. Encerrando paginação.")
                break

            novos_nesta_pagina = 0

            for produto in produtos_da_pagina:
                url_produto = produto.get("url")

                if not url_produto or url_produto in urls_ja_coletadas:
                    continue

                urls_ja_coletadas.add(url_produto)

                # Ajusta o ranking dinamicamente baseado no total acumulado
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

    finally:
        # Garante que o Chrome seja fechado no final, mesmo se ocorrer algum erro no loop
        print("[INFO] Fechando navegador...")
        driver.quit()

    print(f"[INFO] Coleta finalizada. Total de produtos coletados: {len(produtos_coletados)}")
    return produtos_coletados

def encontrar_precos_no_texto(texto):
    texto = normalizar_texto_monetario(texto)

    return re.findall(
        r"R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2}",
        texto,
    )


def extrair_preco_prazo_e_parcela(bloco_produto):
    preco_prazo = None
    quantidade_parcelas = None
    valor_parcela = None

    if not hasattr(bloco_produto, "select_one"):
        return preco_prazo, quantidade_parcelas, valor_parcela

    div_parcelamento = bloco_produto.select_one(
        "div.parcel, .parcel, [class*='parcel']"
    )

    if not div_parcelamento:
        return preco_prazo, quantidade_parcelas, valor_parcela

    texto_parcelamento = div_parcelamento.get_text(" ", strip=True)
    texto_parcelamento = normalizar_texto_monetario(texto_parcelamento)

    # Exemplo 1:
    # "já com 10% de desconto à vista no Pix ou boleto ou R$ 5.321,11 em até 10x de R$ 532,11"
    #
    # Exemplo 2:
    # "à vista em 10x R$ 113,90 sem juros no cartão"

    precos_encontrados = encontrar_precos_no_texto(texto_parcelamento)

    # Busca quantidade de parcelas + valor da parcela.
    # Aceita:
    # 10x de R$ 532,11
    # 10x R$ 113,90
    parcelas_match = re.search(
        r"(\d+)\s*x\s*(?:de\s*)?(R\$\s*\d{1,3}(?:\.\d{3})*,\d{2}|R\$\s*\d+,\d{2})",
        texto_parcelamento,
        flags=re.IGNORECASE,
    )

    if parcelas_match:
        quantidade_parcelas = int(parcelas_match.group(1))
        valor_parcela = converter_preco_para_decimal(parcelas_match.group(2))

    # Se houver dois preços na div.parcel:
    # primeiro = preço total a prazo
    # segundo = valor da parcela
    if len(precos_encontrados) >= 2:
        preco_prazo = converter_preco_para_decimal(precos_encontrados[0])

        if valor_parcela is None:
            valor_parcela = converter_preco_para_decimal(precos_encontrados[1])

    # Se houver só um preço e ele veio junto do parcelamento,
    # esse preço é o valor da parcela.
    elif len(precos_encontrados) == 1 and valor_parcela is None:
        valor_parcela = converter_preco_para_decimal(precos_encontrados[0])

    # Quando o site não informa o preço total a prazo,
    # calculamos pelo parcelamento.
    if preco_prazo is None and quantidade_parcelas and valor_parcela:
        preco_prazo = valor_parcela * quantidade_parcelas

    return preco_prazo, quantidade_parcelas, valor_parcela