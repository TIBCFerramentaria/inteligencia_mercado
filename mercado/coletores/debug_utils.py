import json
import os


def debug_coletores_ativo():
    return os.getenv("COLETORES_DEBUG", "0").strip().lower() in [
        "1",
        "true",
        "sim",
        "yes",
        "on",
    ]


def salvar_debug_texto(nome_arquivo, conteudo):
    if not debug_coletores_ativo():
        return

    try:
        with open(nome_arquivo, "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo or "")
    except Exception as erro:
        print(f"[WARN] Não consegui salvar debug {nome_arquivo}: {erro}")


def salvar_debug_json(nome_arquivo, dados):
    if not debug_coletores_ativo():
        return

    try:
        with open(nome_arquivo, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    except Exception as erro:
        print(f"[WARN] Não consegui salvar debug {nome_arquivo}: {erro}")

def salvar_debug_screenshot(nome_arquivo, driver):
    if not debug_coletores_ativo():
        return

    try:
        driver.save_screenshot(nome_arquivo)
    except Exception as erro:
        print(f"[WARN] Não consegui salvar screenshot debug {nome_arquivo}: {erro}")