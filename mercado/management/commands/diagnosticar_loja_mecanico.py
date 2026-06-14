from pathlib import Path

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from playwright.sync_api import sync_playwright


URL = "https://www.lojadomecanico.com.br/hotsite/maisvendidos"


class Command(BaseCommand):
    help = "Diagnostica o conteúdo recebido da página de mais vendidos da Loja do Mecânico."

    def handle(self, *args, **options):
        pasta_debug = Path("debug_loja_mecanico")
        pasta_debug.mkdir(exist_ok=True)

        self.stdout.write(self.style.WARNING("Iniciando diagnóstico da Loja do Mecânico..."))

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }

        # Diagnóstico com requests
        self.stdout.write("1) Baixando HTML com requests...")

        resposta = requests.get(URL, headers=headers, timeout=60)

        html_requests = resposta.text
        arquivo_requests = pasta_debug / "requests.html"
        arquivo_requests.write_text(html_requests, encoding="utf-8")

        soup_requests = BeautifulSoup(html_requests, "html.parser")
        texto_requests = soup_requests.get_text("\n", strip=True)

        arquivo_texto_requests = pasta_debug / "requests_texto.txt"
        arquivo_texto_requests.write_text(texto_requests, encoding="utf-8")

        links_requests = soup_requests.find_all("a", href=True)

        self.stdout.write(f"Status requests: {resposta.status_code}")
        self.stdout.write(f"Tamanho HTML requests: {len(html_requests)} caracteres")
        self.stdout.write(f"Quantidade de links requests: {len(links_requests)}")
        self.stdout.write(f"Ocorrências de R$ requests: {html_requests.count('R$')}")
        self.stdout.write(f"Ocorrências de /produto/ requests: {html_requests.count('/produto/')}")
        self.stdout.write(f"Ocorrências de maisvendidos requests: {html_requests.lower().count('maisvendidos')}")

        # Diagnóstico com Playwright
        self.stdout.write("")
        self.stdout.write("2) Abrindo página com Playwright/Chromium...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            page = browser.new_page(
                viewport={"width": 1366, "height": 1000},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0 Safari/537.36"
                ),
            )

            page.goto(URL, wait_until="domcontentloaded", timeout=90000)

            try:
                page.wait_for_load_state("load", timeout=30000)
            except Exception:
                pass

            page.wait_for_timeout(8000)

            for _ in range(6):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(1500)

            html_playwright = page.content()
            texto_playwright = page.locator("body").inner_text(timeout=30000)

            arquivo_playwright = pasta_debug / "playwright.html"
            arquivo_playwright.write_text(html_playwright, encoding="utf-8")

            arquivo_texto_playwright = pasta_debug / "playwright_texto.txt"
            arquivo_texto_playwright.write_text(texto_playwright, encoding="utf-8")

            arquivo_screenshot = pasta_debug / "playwright_screenshot.png"
            page.screenshot(path=str(arquivo_screenshot), full_page=True)

            browser.close()

        soup_playwright = BeautifulSoup(html_playwright, "html.parser")
        links_playwright = soup_playwright.find_all("a", href=True)

        self.stdout.write(f"Tamanho HTML Playwright: {len(html_playwright)} caracteres")
        self.stdout.write(f"Tamanho texto Playwright: {len(texto_playwright)} caracteres")
        self.stdout.write(f"Quantidade de links Playwright: {len(links_playwright)}")
        self.stdout.write(f"Ocorrências de R$ Playwright HTML: {html_playwright.count('R$')}")
        self.stdout.write(f"Ocorrências de R$ Playwright texto: {texto_playwright.count('R$')}")
        self.stdout.write(f"Ocorrências de /produto/ Playwright: {html_playwright.count('/produto/')}")
        self.stdout.write(f"Ocorrências de produto Playwright: {html_playwright.lower().count('produto')}")
        self.stdout.write(f"Ocorrências de javascript Playwright: {html_playwright.lower().count('javascript')}")
        self.stdout.write(f"Ocorrências de bloqueio Playwright: {html_playwright.lower().count('bloqueio')}")
        self.stdout.write(f"Ocorrências de captcha Playwright: {html_playwright.lower().count('captcha')}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Arquivos criados em: debug_loja_mecanico/"))
        self.stdout.write("Confira principalmente estes arquivos:")
        self.stdout.write("- debug_loja_mecanico/playwright_screenshot.png")
        self.stdout.write("- debug_loja_mecanico/playwright_texto.txt")
        self.stdout.write("- debug_loja_mecanico/playwright.html")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Copie aqui o resumo impresso no terminal."))