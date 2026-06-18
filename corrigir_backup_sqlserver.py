import json
from pathlib import Path

ARQUIVO_ENTRADA = Path("backups/backup_sqlite_antes_sqlserver.json")
ARQUIVO_SAIDA = Path("backups/backup_sqlite_antes_sqlserver_corrigido.json")


def normalizar_nome(valor):
    if valor is None:
        return ""

    texto = str(valor).strip()
    texto = " ".join(texto.split())
    return texto.upper()


def substituir_pk_marca(valor, mapa_substituicao):
    if isinstance(valor, int):
        return mapa_substituicao.get(valor, valor)

    if isinstance(valor, str) and valor.isdigit():
        valor_int = int(valor)
        novo_valor = mapa_substituicao.get(valor_int, valor_int)
        return novo_valor

    if isinstance(valor, list):
        return [substituir_pk_marca(item, mapa_substituicao) for item in valor]

    return valor


with ARQUIVO_ENTRADA.open("r", encoding="utf-8") as arquivo:
    dados = json.load(arquivo)

marcas_por_nome = {}
mapa_substituicao_marca = {}
dados_corrigidos = []

total_marcas = 0
total_marcas_removidas = 0

for objeto in dados:
    modelo = objeto.get("model")

    if modelo == "mercado.marca":
        total_marcas += 1

        pk = objeto.get("pk")
        campos = objeto.get("fields", {})
        nome = campos.get("nome")

        chave = normalizar_nome(nome)

        if not chave:
            dados_corrigidos.append(objeto)
            continue

        # Limpa espaços extras no nome
        campos["nome"] = " ".join(str(nome).strip().split())

        if chave in marcas_por_nome:
            pk_principal = marcas_por_nome[chave]
            mapa_substituicao_marca[pk] = pk_principal
            total_marcas_removidas += 1
            print(f"Marca duplicada removida: {nome!r} | pk {pk} -> pk {pk_principal}")
            continue

        marcas_por_nome[chave] = pk
        dados_corrigidos.append(objeto)

    else:
        dados_corrigidos.append(objeto)


# Atualiza todas as referências para marcas duplicadas
for objeto in dados_corrigidos:
    campos = objeto.get("fields", {})

    if "marca" in campos:
        campos["marca"] = substituir_pk_marca(
            campos["marca"],
            mapa_substituicao_marca,
        )

print()
print(f"Total de marcas no backup original: {total_marcas}")
print(f"Marcas duplicadas removidas: {total_marcas_removidas}")
print(f"Total de substituições de FK: {len(mapa_substituicao_marca)}")

with ARQUIVO_SAIDA.open("w", encoding="utf-8") as arquivo:
    json.dump(dados_corrigidos, arquivo, ensure_ascii=False, indent=2)

print()
print(f"Arquivo corrigido gerado em: {ARQUIVO_SAIDA}")