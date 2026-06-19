import json
import time
import os
import re
from html import unescape
from decimal import Decimal
from urllib.parse import urljoin, urldefrag, urlsplit, urlunsplit, parse_qsl, urlencode

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


def validar_gtin(codigo):
    if not codigo:
        return False

    codigo = re.sub(r"\D", "", str(codigo))

    if len(codigo) not in [8, 12, 13, 14]:
        return False

    if len(set(codigo)) == 1:
        return False

    digitos = [int(d) for d in codigo]
    digito_verificador = digitos[-1]
    corpo = digitos[:-1]

    soma = 0
    peso = 3

    for digito in reversed(corpo):
        soma += digito * peso
        peso = 1 if peso == 3 else 3

    calculado = (10 - (soma % 10)) % 10

    return calculado == digito_verificador


def normalizar_ean(valor):
    if not valor:
        return None

    codigo = re.sub(r"\D", "", str(valor))

    if validar_gtin(codigo):
        return codigo

    return None


def procurar_ean_em_json_ld(objeto):
    if isinstance(objeto, dict):
        for chave in [
            "gtin",
            "gtin8",
            "gtin12",
            "gtin13",
            "gtin14",
            "ean",
            "barcode",
            "codigoBarras",
            "codigo_barras",
        ]:
            valor = objeto.get(chave)

            ean = normalizar_ean(valor)

            if ean:
                return ean

        for valor in objeto.values():
            ean = procurar_ean_em_json_ld(valor)

            if ean:
                return ean

    elif isinstance(objeto, list):
        for item in objeto:
            ean = procurar_ean_em_json_ld(item)

            if ean:
                return ean

    return None


def gerar_variacoes_texto_json(texto):
    if not texto:
        return []

    variacoes = []

    texto_original = str(texto)
    texto_unescape = unescape(texto_original)

    variacoes.append(texto_original)
    variacoes.append(texto_unescape)

    # Remove escapes comuns de JSON dentro de string
    variacoes.append(texto_original.replace('\\"', '"').replace("\\/", "/"))
    variacoes.append(texto_unescape.replace('\\"', '"').replace("\\/", "/"))

    # Evita repetição
    resultado = []
    vistos = set()

    for item in variacoes:
        if item not in vistos:
            resultado.append(item)
            vistos.add(item)

    return resultado


def buscar_valor_json_texto(texto, campo):
    if not texto or not campo:
        return None

    for texto_base in gerar_variacoes_texto_json(texto):
        # Campo string normal: "ean": "7908591710281"
        padrao_string = rf'"{re.escape(campo)}"\s*:\s*"((?:\\.|[^"\\])*)"'
        match = re.search(padrao_string, texto_base)

        if match:
            valor = match.group(1)

            try:
                return json.loads(f'"{valor}"')
            except Exception:
                return valor

        # Campo string sem espaço: "ean":"7908591710281"
        padrao_string_simples = rf'"{re.escape(campo)}"\s*:\s*"([^"]+)"'
        match = re.search(padrao_string_simples, texto_base)

        if match:
            return match.group(1)

        # Campo numérico: "precoBoleto": 92.9
        padrao_numero = rf'"{re.escape(campo)}"\s*:\s*(-?\d+(?:\.\d+)?)'
        match = re.search(padrao_numero, texto_base)

        if match:
            valor = match.group(1)

            try:
                if "." in valor:
                    return Decimal(valor)
                return int(valor)
            except Exception:
                return valor

        # Campo nulo ou booleano
        padrao_literal = rf'"{re.escape(campo)}"\s*:\s*(null|true|false)'
        match = re.search(padrao_literal, texto_base)

        if match:
            valor = match.group(1)

            if valor == "null":
                return None

            return valor == "true"

    return None

def extrair_dados_detalhe_loja_mecanico(html):
    dados = {}

    if not html:
        return dados

    # Primeiro tenta buscar pelo campo JSON "ean"
    ean = normalizar_ean(buscar_valor_json_texto(html, "ean"))

    # Segunda tentativa: procura diretamente padrões escapados ou normais
    if not ean:
        for texto_base in gerar_variacoes_texto_json(html):
            match = re.search(
                r'"ean"\s*:\s*"(\d{8,14})"',
                texto_base,
                flags=re.IGNORECASE,
            )

            if match:
                ean = normalizar_ean(match.group(1))

                if ean:
                    break

    if ean:
        dados["ean"] = ean

    nome = buscar_valor_json_texto(html, "nome")
    nome_marca = buscar_valor_json_texto(html, "nomeMarca")
    referencia = buscar_valor_json_texto(html, "referencia")

    preco_tabela = buscar_valor_json_texto(html, "precoTabela")
    preco_venda = buscar_valor_json_texto(html, "precoVenda")
    preco_boleto = buscar_valor_json_texto(html, "precoBoleto")

    qtde_parcelas = buscar_valor_json_texto(html, "qtdeParcelas")
    valor_parcela = buscar_valor_json_texto(html, "valorParcela")

    avaliacao = buscar_valor_json_texto(html, "avaliacao")
    avaliacao_total = buscar_valor_json_texto(html, "avaliacaoTotal")
    avaliacao_qtde = buscar_valor_json_texto(html, "avaliacaoQtde")

    desconto_promocao = buscar_valor_json_texto(html, "descontoPromocao")
    estoque = buscar_valor_json_texto(html, "estoque")

    if nome:
        nome_normalizado = normalizar_texto(nome)
        dados["nome"] = nome_normalizado
        dados["nome_original"] = nome_normalizado

    if nome_marca:
        marca_normalizada = normalizar_texto(nome_marca)
        dados["marca"] = marca_normalizada
        dados["marca_nome"] = marca_normalizada

    if referencia:
        dados["codigo_fabricante"] = normalizar_texto(referencia)

    if preco_boleto is not None:
        dados["preco_atual"] = converter_para_decimal(preco_boleto)

    if preco_tabela is not None:
        dados["preco_antigo"] = converter_para_decimal(preco_tabela)

    if preco_venda is not None:
        dados["preco_prazo"] = converter_para_decimal(preco_venda)

    if qtde_parcelas is not None:
        dados["quantidade_parcelas"] = qtde_parcelas

    if valor_parcela is not None:
        dados["valor_parcela"] = converter_para_decimal(valor_parcela)

    if avaliacao is not None:
        dados["nota"] = avaliacao

    if avaliacao_total is not None:
        dados["avaliacoes"] = avaliacao_total
    elif avaliacao_qtde is not None:
        dados["avaliacoes"] = avaliacao_qtde

    if desconto_promocao is not None:
        dados["desconto"] = desconto_promocao

    if estoque is not None:
        try:
            dados["estoque"] = int(estoque)
        except Exception:
            dados["estoque"] = None

    return dados


def extrair_ean_do_html_detalhe(html):
    dados = extrair_dados_detalhe_loja_mecanico(html)
    return dados.get("ean")


def enriquecer_produto_loja_com_detalhe(driver, produto, pausa=2):
    url_produto = produto.get("url") or produto.get("url_produto")

    if not url_produto:
        return produto

    print(f"[INFO] Abrindo detalhe do produto: {url_produto}")

    try:
        driver.get(url_produto)
        time.sleep(pausa)

        html = driver.page_source

        dados_detalhe = extrair_dados_detalhe_loja_mecanico(html)

        if dados_detalhe.get("ean"):
            print(f"[INFO] EAN encontrado: {dados_detalhe.get('ean')}")
        else:
            print("[INFO] EAN não encontrado no detalhe.")

            try:
                with open("debug_loja_mecanico_detalhe.html", "w", encoding="utf-8") as arquivo:
                    arquivo.write(html)

                print("[INFO] HTML salvo em debug_loja_mecanico_detalhe.html")
            except Exception as erro_arquivo:
                print(f"[WARN] Não consegui salvar HTML de debug: {erro_arquivo}")

        for chave, valor in dados_detalhe.items():
            if valor not in [None, ""]:
                produto[chave] = valor

    except Exception as erro:
        print(f"[WARN] Não consegui enriquecer o detalhe: {url_produto}")
        print(f"[WARN] Erro: {erro}")

    return produto

def converter_para_decimal(valor):
    if valor is None or valor == "":
        return None

    try:
        return Decimal(str(valor))
    except Exception:
        return None

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

def montar_url_produto_loja_mecanico(item, url_base):
    cod_produto = item.get("codProduto")
    cod_categoria = item.get("codCategoria")
    cod_subcategoria = item.get("codSubcategoria")
    slug = item.get("slug")

    if cod_produto and cod_categoria and cod_subcategoria and slug:
        caminho = f"/produto/{cod_produto}/{cod_categoria}/{cod_subcategoria}/{slug}"
        return urljoin(url_base, caminho)

    return None

def extrair_produtos_data_product(html, url_base, limite=None):
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one("#view-product-list")

    if not container:
        return []

    input_produtos = container.select_one(
        "input.tagManagerProductImpression[data-product]"
    )

    if not input_produtos:
        input_produtos = container.select_one(
            "input.insiderProductImpression[data-product]"
        )

    if not input_produtos:
        return []

    data_product = input_produtos.get("data-product", "")

    if not data_product:
        return []

    try:
        itens = json.loads(data_product)
    except Exception as erro:
        print("[WARN] Não consegui ler o JSON de data-product da Loja do Mecânico.")
        print(f"[WARN] Erro: {erro}")
        return []

    produtos = []

    for item in itens:
        if limite and len(produtos) >= limite:
            break

        nome = item.get("produto")
        url = montar_url_produto_loja_mecanico(item, url_base)

        if not nome or not url:
            continue

        preco_atual = item.get("billetPrice") or item.get("preco")
        preco_prazo = item.get("preco")
        preco_antigo = item.get("precode")

        quantidade_parcelas = item.get("installmentPaymentQuantity") or item.get(
            "quantidadeParcela"
        )
        valor_parcela = item.get("installmentPaymentValue")

        codigo_fabricante = item.get("codigo")
        marca_nome = item.get("nameManufacturer")

        ranking = item.get("rowNum")

        desconto = item.get("descontoPromocao")
        nota = item.get("avaliacao")
        avaliacoes = item.get("avaliacaoQtde")

        nome_normalizado = normalizar_texto(nome)
        marca_normalizada = normalizar_texto(marca_nome)
        codigo_fabricante_normalizado = normalizar_texto(codigo_fabricante)

        produtos.append(
            {
                "ranking": ranking,

                # Usamos os dois nomes para compatibilidade com o restante do sistema
                "nome": nome_normalizado,
                "nome_original": nome_normalizado,

                # Marca
                "marca": marca_normalizada,
               "marca_nome": marca_normalizada,

                # Códigos
                "codigo_fabricante": codigo_fabricante_normalizado,
                "codigo_site": str(item.get("codProduto")) if item.get("codProduto") else None,

                # EAN ainda será buscado no detalhe do produto
                "ean": None,

                # Preços
                "preco_atual": converter_para_decimal(preco_atual),
                "preco_antigo": converter_para_decimal(preco_antigo),
                "preco_prazo": converter_para_decimal(preco_prazo),
                "quantidade_parcelas": quantidade_parcelas,
                "valor_parcela": converter_para_decimal(valor_parcela),

                # Informações adicionais
                "desconto": item.get("descontoPromocao"),
                "nota": item.get("avaliacao"),
                "avaliacoes": item.get("avaliacaoQtde"),

                # URL
                "url": url,
               "fonte": "data-product",
            }
        )

    return produtos

def extrair_produtos_do_html(html, url_base, limite=None):
    produtos_data_product = extrair_produtos_data_product(html, url_base, limite=limite)
    if produtos_data_product:
        return produtos_data_product
    # Manté, a lógica antiga como fallback, caso alguma página não tenha data-product.
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

def montar_url_produtos_pagina(url_base, pagina):
    if pagina <= 1:
        return url_base

    partes = urlsplit(url_base)

    parametros = dict(parse_qsl(partes.query, keep_blank_values=True))
    parametros["page"] = str(pagina)

    nova_query = urlencode(parametros)

    return urlunsplit((
        partes.scheme,
        partes.netloc,
        partes.path,
        nova_query,
        "",
    ))


def montar_url_mais_vendidos_pagina(pagina):
    return montar_url_produtos_pagina(URL_MAIS_VENDIDOS, pagina)

def limpar_url_paginacao(url):
    url, _fragmento = urldefrag(url)
    return url


def encontrar_url_proxima_pagina(html, url_atual, numero_pagina_atual):
    soup = BeautifulSoup(html, "html.parser")

    numero_proxima_pagina = str(numero_pagina_atual + 1)
    url_atual_limpa = limpar_url_paginacao(url_atual)
    dominio_atual = urlsplit(url_atual).netloc

    candidatos = []

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")

        if not href or href.startswith("javascript:"):
            continue

        texto = normalizar_texto(link.get_text(" ", strip=True)).lower()
        texto_sem_acento = (
            texto
            .replace("ó", "o")
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ú", "u")
            .replace("ã", "a")
            .replace("õ", "o")
            .replace("ç", "c")
        )

        rel = " ".join(link.get("rel", [])).lower() if link.get("rel") else ""

        url_candidata = limpar_url_paginacao(urljoin(url_atual, href))
        dominio_candidato = urlsplit(url_candidata).netloc

        if dominio_candidato and dominio_candidato != dominio_atual:
            continue

        if url_candidata == url_atual_limpa:
            continue

        eh_proxima_pagina = (
            texto == numero_proxima_pagina
            or texto_sem_acento in ["proxima", "proximo", "seguinte", "avancar", ">"]
            or "next" in rel
            or f"pagina={numero_proxima_pagina}" in url_candidata.lower()
            or f"page={numero_proxima_pagina}" in url_candidata.lower()
            or f"p={numero_proxima_pagina}" in url_candidata.lower()
        )

        if eh_proxima_pagina:
            candidatos.append(url_candidata)

    if candidatos:
        return candidatos[0]

    return None

def coletar_mais_vendidos(
    limite=None,
    max_paginas=20,
    url_base=None,
    nome_fonte=None,
):
    if not url_base:
        url_base = URL_MAIS_VENDIDOS

    if not nome_fonte:
        nome_fonte = "Mais vendidos"

    produtos_coletados = []
    urls_coletadas = set()

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
        url_pagina = url_base

        for numero_pagina in range(1, max_paginas + 1):
            if limite and len(produtos_coletados) >= limite:
                print(f"[INFO] Limite de {limite} produtos atingido.")
                break

            print("=" * 80)
            print(f"[INFO] Fonte: {nome_fonte}")
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
                driver.page_source,
                url_pagina,
                limite=itens_restantes,
            )

            print(f"[INFO] Produtos extraídos da página {numero_pagina}: {len(produtos_da_pagina)}")

            if not produtos_da_pagina:
                print("[INFO] Nenhum produto encontrado nesta página. Encerrando paginação.")
                break

            novos_nesta_pagina = 0

            for produto in produtos_da_pagina:
                produto = enriquecer_produto_loja_com_detalhe(driver, produto)
                
                url_produto = produto.get("url")

                if not url_produto:
                    continue

                if url_produto in urls_coletadas:
                    continue

                produtos_coletados.append(produto)
                urls_coletadas.add(url_produto)
                novos_nesta_pagina += 1

                # Ajusta o ranking dinamicamente baseado no total acumulado
                produto["ranking_geral"] = len(produtos_coletados) + 1

                produtos_coletados.append(produto)
                novos_nesta_pagina += 1

                if limite and len(produtos_coletados) >= limite:
                    break

            print(f"[INFO] Produtos novos adicionados da página {numero_pagina}: {novos_nesta_pagina}")
            print(f"[INFO] Total acumulado até agora: {len(produtos_coletados)}")

            proxima_url = encontrar_url_proxima_pagina(
                html_da_pagina,
                url_pagina,
                numero_pagina,
            )

            if novos_nesta_pagina == 0:
                print("[INFO] Página sem produtos novos. Encerrando para evitar repetição infinita.")
                break

            if limite and len(produtos_coletados) >= limite:
                print(f"[INFO] Limite de {limite} produtos atingido.")
                break

            if not proxima_url:
                print("[INFO] Não encontrei link para próxima página. Encerrando paginação.")
                break

            print(f"[INFO] Próxima página encontrada: {proxima_url}")
            url_pagina = proxima_url

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