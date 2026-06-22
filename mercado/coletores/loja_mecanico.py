import json
import time
import os
import re
import ssl
from html import unescape
from decimal import Decimal
from urllib.parse import urljoin, urldefrag, urlsplit, urlunsplit, parse_qsl, urlencode
from mercado.coletores.debug_utils import salvar_debug_texto

# --- CORREÇÃO DE CERTIFICADO MAC O.S ---
ssl._create_default_https_context = ssl._create_unverified_context 

# IMPORTANTE: Substituído o Selenium padrão pelo undetected-chromedriver para bypass de Captcha
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURAÇÃO GLOBAL DO NAVEGADOR INDETECTÁVEL ---
print("[INFO] Inicializando o navegador indetectável...")
options = uc.ChromeOptions()
options.add_argument("--start-maximized")

# Aponta para a pasta onde está a extensão extraída do GitHub
caminho_extensao = os.path.abspath("./hektcaptcha") 
options.add_argument(f"--load-extension={caminho_extensao}")

# Instancia o driver usando o método nativo do undetected_chromedriver
# (Nota: Não usamos selenium-stealth ou excludeSwitches aqui pois eles quebram o UC)
driver = uc.Chrome(options=options, version_main=149)


URL_MAIS_VENDIDOS = "https://www.lojadomecanico.com.br/hotsite/maisvendidos"


# --- FUNÇÕES DE AUXÍLIO E PARSE ---

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

    if len(codigo) not in (8, 12, 13, 14):
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
            "gtin", "gtin8", "gtin12", "gtin13", "gtin14",
            "ean", "barcode", "codigoBarras", "codigo_barras",
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

    variacoes.append(texto_original.replace('\\"', '"').replace("\\/", "/"))
    variacoes.append(texto_unescape.replace('\\"', '"').replace("\\/", "/"))

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
        padrao_string = rf'"{re.escape(campo)}"\s*:\s*"((?:\\.|[^"\\])*)"'
        match = re.search(padrao_string, texto_base)

        if match:
            valor = match.group(1)
            try:
                return json.loads(f'"{valor}"')
            except Exception:
                return valor

        padrao_string_simples = rf'"{re.escape(campo)}"\s*:\s*"([^"]+)"'
        match = re.search(padrao_string_simples, texto_base)

        if match:
            return match.group(1)

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

        padrao_literal = rf'"{re.escape(campo)}"\s*:\s*(null|true|false)'
        match = re.search(padrao_literal, texto_base)

        if match:
            valor = match.group(1)
            if valor == "null":
                return None
            return valor == "true"

    return None


def converter_para_decimal(valor):
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except Exception:
        return None


# --- FUNÇÃO PRINCIPAL DE EXTRAÇÃO ---

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

    # Lógica de avaliações recuperada com sucesso:
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


# --- FUNÇÃO DE ENRIQUECIMENTO INTEGRADA ---

def enriquecer_produto_loja_com_detalhe(driver, produto, pausa=2):
    url_produto = produto.get("url") or produto.get("url_produto")

    if not url_produto:
        return produto

    print(f"[INFO] Abrindo detalhe do produto: {url_produto}")

    try:
        driver.get(url_produto)
        time.sleep(pausa)
    except Exception as erro:
        print(f"[ERRO] Falha ao abrir página {url_produto}: {erro}")
        return produto
    
    html = driver.page_source
    html_minusculo = html.lower()

    # --- MONITORAMENTO DO hCAPTCHA ---
    if "hcaptcha" in html_minusculo or "captcha" in html_minusculo:
        print("[AVISO] hCaptcha detectado! Aguardando a extensão Hcaptcha Solver agir...")
                
        tempo_maximo = 60  
        inicio = time.time()
        while time.time() - inicio < tempo_maximo:
            try:
                token = driver.execute_script("return hcaptcha.getResponse();")
                if token and len(token) > 0:
                    print("[SUCESSO] hCaptcha foi decodificado pela extensão!")
                    time.sleep(3)  
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            print("[AVISO] A extensão demorou muito. Tentando continuar assim mesmo.")

        # Recarrega o HTML atualizado do driver após a ação da extensão
        html = driver.page_source
        html_minusculo = html.lower()

        if "r$" not in html_minusculo and "adicionar ao carrinho" not in html_minusculo:
            print("[AVISO] Página bloqueada por Captcha persistente. Coleta interrompida.")
            return produto 
    else:
        print("[INFO] Nenhum hCaptcha detectado. Extraindo dados normalmente.")

    # --- PROCESSAMENTO DOS DADOS ---
    dados_detalhe = extrair_dados_detalhe_loja_mecanico(html)

    if dados_detalhe.get("ean"):
        print(f"[INFO] EAN encontrado: {dados_detalhe.get('ean')}")
    else:
        print("[INFO] EAN não encontrado no detalhe.")
        salvar_debug_texto("debug_loja_mecanico_detalhe.html", html)

    for chave, valor in dados_detalhe.items():
        if valor not in [None, ""]:
            produto[chave] = valor

    return produto

def coletar_mais_vendidos(limite=500, max_paginas=10, alvo=None, url_base=None, **kwargs):
    """
    Ponto de entrada do Django. Captura apenas os produtos do grid principal
    e faz o parse seguro dos dados contidos no atributo data-product.
    """
    url_inicial = url_base or URL_MAIS_VENDIDOS
    
    print("[INFO] Iniciando rotina de coleta com seletor de grid restrito.")
    print(f"[INFO] URL Inicial: {url_inicial}")
    
    produtos_coletados = []
    
    try:
        driver.get(url_inicial)
        time.sleep(4)  # Tempo para o JavaScript renderizar o grid principal
        
        for pagina in range(1, max_paginas + 1):
            print(f"[INFO] Processando página de listagem {pagina}...")
            
            html_listagem = driver.page_source
            soup = BeautifulSoup(html_listagem, "html.parser")
            
            # 1. Localiza EXCLUSIVAMENTE o container da listagem real que você identificou
            grid_principal = soup.find("div", class_="container-categorias")
            
            if not grid_principal:
                # Fallback caso a classe mude ligeiramente no futuro, tenta pela classe filha do grid
                grid_principal = soup.find("div", class_="container__grid")
                
            if not grid_principal:
                print(f"[AVISO] Grid principal de produtos não encontrado na página {pagina}. Pulando ou fim de paginação.")
                break

            # 2. Busca os links apenas dentro deste container específico
            tags_produtos = grid_principal.find_all("a", class_="tagManagerProductClick", href=True)
            print(f"[INFO] Encontrados {len(tags_produtos)} produtos legítimos no grid principal.")

            for tag_a in tags_produtos:
                if len(produtos_coletados) >= limite:
                    print(f"[INFO] Limite de {limite} produtos atingido.")
                    break
                
                url_produto = urljoin(url_inicial, tag_a["href"])
                
                # Inicializa o dicionário base
                produto_dados = {
                    "url": url_produto,
                    "url_produto": url_produto
                }
                
                # 3. EXTRAÇÃO ULTRA-RÁPIDA (Bônus): Captura o JSON interno se disponível
                data_product_attr = tag_a.get("data-product")
                if data_product_attr:
                    try:
                        # Faz o unescape e carrega o dicionário limpo vindo do site
                        info_json = json.loads(unescape(data_product_attr))
                        
                        # Mapeia os dados do JSON da listagem diretamente para o formato do seu banco
                        if info_json.get("codigo"):
                            produto_dados["codigo_fabricante"] = normalizar_texto(info_json.get("codigo"))
                        if info_json.get("produto"):
                            produto_dados["nome"] = normalizar_texto(info_json.get("produto"))
                            produto_dados["nome_original"] = produto_dados["nome"]
                        if info_json.get("nameManufacturer"):
                            produto_dados["marca"] = normalizar_texto(info_json.get("nameManufacturer"))
                            produto_dados["marca_nome"] = produto_dados["marca"]
                        if info_json.get("billetPrice"):
                            produto_dados["preco_atual"] = converter_para_decimal(info_json.get("billetPrice"))
                        if info_json.get("precode"):
                            produto_dados["preco_antigo"] = converter_para_decimal(info_json.get("precode"))
                        if info_json.get("preco"):
                            produto_dados["preco_prazo"] = converter_para_decimal(info_json.get("preco"))
                        if info_json.get("quantidadeParcela"):
                            produto_dados["quantidade_parcelas"] = info_json.get("quantidadeParcela")
                        if info_json.get("installmentPaymentValue"):
                            produto_dados["valor_parcela"] = converter_para_decimal(info_json.get("installmentPaymentValue"))
                        if info_json.get("avaliacao"):
                            produto_dados["nota"] = info_json.get("avaliacao")
                        if info_json.get("avaliacaoQtde"):
                            produto_dados["avaliacoes"] = info_json.get("avaliacaoQtde")
                        if info_json.get("estoque"):
                            produto_dados["estoque"] = int(info_json.get("estoque"))
                            
                    except Exception as err_json:
                        print(f"[AVISO] Falha ao ler data-product nativo: {err_json}")

                # 4. CHAMA O ENRIQUECIMENTO (Acessa a página interna para buscar o EAN via hCaptcha)
                # Passamos o dicionário que já possui os preços populados da listagem
                produto_enriquecido = enriquecer_produto_loja_com_detalhe(driver, produto_dados)
                
                # Salva o produto apenas se a extração (EAN ou dados) for bem sucedida
                if produto_enriquecido:
                    produtos_coletados.append(produto_enriquecido)
            
            if len(produtos_coletados) >= limite:
                break
                
            # LÓGICA DE PAGINAÇÃO AVANÇADA
            partes_url = urlsplit(url_inicial)
            query_params = dict(parse_qsl(partes_url.query))
            query_params['p'] = str(pagina + 1)
            nova_query = urlencode(query_params)
            
            proxima_url = urlunsplit((
                partes_url.scheme, partes_url.netloc, partes_url.path, nova_query, partes_url.fragment
            ))
                
            print(f"[INFO] Avançando para a página: {proxima_url}")
            driver.get(proxima_url)
            time.sleep(4)
            
    except Exception as e:
        print(f"[ERRO] Falha crítica no loop principal da coleta: {e}")
        
    print(f"[SUCESSO] Rotina finalizada. Total de produtos coletados: {len(produtos_coletados)}")
    return produtos_coletados