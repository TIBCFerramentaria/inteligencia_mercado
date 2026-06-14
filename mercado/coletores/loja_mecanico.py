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


def extrair_precos(texto_bloco):
    precos_encontrados = re.findall(r"R\$\s*[\d\.]+,\d{2}", texto_bloco)

    preco_antigo = None
    preco_atual = None

    if not precos_encontrados:
        return preco_atual, preco_antigo

    if "DE:" in texto_bloco.upper() and len(precos_encontrados) >= 2:
        preco_antigo = converter_preco_para_decimal(precos_encontrados[0])
        preco_atual = converter_preco_para_decimal(precos_encontrados[-1])
    else:
        preco_atual = converter_preco_para_decimal(precos_encontrados[0])

    return preco_atual, preco_antigo


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

        candidatos.append({
            "nome": texto,
            "url": url,
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

        if "R$" not in texto_bloco:
            continue

        preco_atual, preco_antigo = extrair_precos(texto_bloco)

        if preco_atual is None:
            continue

        desconto_percentual = extrair_desconto(texto_bloco)
        nota_media, quantidade_avaliacoes = extrair_nota_avaliacoes(texto_bloco)
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


# --- FUNÇÃO ADAPTADA COM SELENIUM, STEALTH E A EXTENSÃO ---
def coletar_mais_vendidos(limite=None):
    # Configurando o navegador Chrome
    options = Options()
    options.add_argument("start-maximized")

    # Caminho onde você deve colocar a pasta 'hektcaptcha' extraída do GitHub
    caminho_extensao = os.path.abspath("./hektcaptcha") 
    options.add_argument(f"--load-extension={caminho_extensao}")

    # Remove os rastros de automação padrão que denunciam o robô
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)

    # Aplica a camuflagem profunda anti-detecção
    stealth(driver,
            languages=["pt-BR", "pt"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True)

    html_da_pagina = ""

    try:
        print("[INFO] Abrindo o navegador e acessando o site...")
        driver.get(URL_MAIS_VENDIDOS)
        
        # Aguarda até 20 segundos para ver se um iframe do hCaptcha surge na tela
        print("[INFO] Verificando se há hCaptcha impedindo o acesso...")
        try:
            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'hCaptcha')]")))
            print("[INFO] hCaptcha detectado! Aguardando o Hcaptcha Solver resolver...")
            
            # Fica monitorando a resposta do hCaptcha até a extensão terminar a resolução visual
            tempo_maximo = 60  
            inicio = time.time()
            while time.time() - inicio < tempo_maximo:
                try:
                    token = driver.execute_script("return hcaptcha.getResponse();")
                    if token and len(token) > 0:
                        print("[SUCESSO] hCaptcha foi decodificado e resolvido pela IA da extensão!")
                        break
                except Exception:
                    pass
                time.sleep(2)
            
            # Pequeno tempo extra de estabilização pós-resolução
            time.sleep(5)
            
        except Exception:
            print("[INFO] Nenhum hCaptcha imediato travando a tela ou ele já foi pulado.")

        # Captura o HTML final renderizado após a liberação da segurança
        html_da_pagina = driver.page_source
        print("[INFO] HTML obtido com sucesso. Iniciando extração dos produtos...")

    finally:
        # Fecha a janela do navegador aberta de forma limpa para não deixar processos soltos no PC
        driver.quit()

    # Passa o conteúdo do HTML obtido pela janela segura para a sua rotina clássica do BeautifulSoup
    if html_da_pagina:
        return extrair_produtos_do_html(html_da_pagina, limite=limite)
    return []


# --- BLOCO DE TESTE ---
if __name__ == "__main__":
    # Executa o extrator coletando apenas os 3 primeiros produtos como teste rápido
    lista_produtos = coletar_mais_vendidos(limite=3)
