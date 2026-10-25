# -*- coding: utf-8 -*-
"""A defesa contra o falso NEGATIVO: a lei penal que ninguém viu.

Não confundir com o que o Vigia faz. O Vigia (`conferir.py`) baixa e compara,
toda semana, os diplomas de `data/fontes.json` — os que o catálogo usa. Ele é
completo sobre o que CONHECE. Este módulo responde à pergunta anterior: **existe
lei penal fora dessa lista?**

O sistema mede falso positivo — o descartado do Sentinela sai nomeado toda
semana. Do inverso não sabia nada: uma lei penal publicada que o filtro semanal
não pegasse não deixaria rastro em lugar nenhum. É o erro que custa meses de
catálogo desatualizado justamente porque não faz barulho.

**Como funciona:** baixa TODAS as leis do ano, uma a uma, e testa cada uma contra
o mesmo critério do Sentinela — o preceito secundário. As que parecerem penais e
não estiverem entre as fontes vigiadas são a lista de leitura.

Não há índice a consultar: o portal de legislação do Planalto está atrás de
proteção anti-bot, e nenhum quadro por ano responde. Mas a página de cada lei
responde, e a numeração é sequencial e nacional — então a enumeração é feita por
sondagem, do primeiro ao último número do ano. Custa alguns minutos por mês, e
roda uma vez por mês.

Uso:
    python scripts/robos/recenseador/leis_do_ano.py                 # ano corrente
    python scripts/robos/recenseador/leis_do_ano.py --ano 2025
    python scripts/robos/recenseador/leis_do_ano.py --de 15400 --ate 15500
    python scripts/robos/recenseador/leis_do_ano.py --orcamento 200 # teto de requisições

Saídas: 0 = nenhuma lei penal fora da vigilância; 2 = erro; 3 = há o que ler.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
# `scripts/robos` para os pacotes dos robôs e do núcleo; `scripts` para o
# `pena_parser`, que é compartilhado com o construtor do catálogo e por isso
# não mora aqui.
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fontes.rede import UA_NAVEGADOR, FalhaDeRede, Rede  # noqa: E402
from nucleo.preceito import comina_pena  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
RELATORIOS = RAIZ / "crawler" / "relatorios"

CABECALHOS = {
    "User-Agent": UA_NAVEGADOR,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
# Uma tentativa só: a caminhada sonda centenas de números, e o que não abre
# conta como vazio.
REDE = Rede(CABECALHOS, tentativas=1, timeout=60)
PAUSA = 1.2                 # educação com o planalto.gov.br, como no baixar.py
VAZIOS_ATE_PARAR = 5        # 404 seguidos que encerram a caminhada

_CABECALHO = re.compile(
    r"LEI\s+(?:COMPLEMENTAR\s+)?N[ºo°.\s]*\s*[\d.]+\s*,?\s*DE\s+[^,]{0,40}?(\d{4})", re.I)
_TAG = re.compile(r"(?s)<[^>]+>")
# O compilado do Planalto embute folha de estilo e script no corpo. Sem retirar
# os dois ANTES de tirar as tags, a "ementa" sai como um bloco de CSS.
_ESTILO = re.compile(r"(?is)<(style|script)[^>]*>.*?</\1>")
# A ementa acaba onde começa a fórmula de promulgação.
_PROMULGACAO = re.compile(
    r"O\s+PRESIDENTE|A\s+PRESIDENTE|O\s+VICE-PRESIDENTE|Mensagem\s+de\s+veto|"
    r"FA[ÇC]O\s+SABER", re.IGNORECASE)
_NUMERO_NA_URL = re.compile(r"/l(?:cp)?([\d.]+)(?:compilado|orig)?\.html?$", re.I)


# ── Endereços ───────────────────────────────────────────────────────────────
def pasta_do_ato(ano: int) -> str:
    """A pasta por quadriênio que o Planalto usa desde 2007 (`_ato2023-2026`)."""
    inicio = 2007 + ((ano - 2007) // 4) * 4
    return f"_ato{inicio}-{inicio + 3}"


def url_da_lei(numero: int, ano: int) -> str:
    return (f"https://www.planalto.gov.br/ccivil_03/{pasta_do_ato(ano)}/{ano}/"
            f"lei/l{numero}.htm")


def url_da_lcp(numero: int) -> str:
    """Lei complementar tem numeração e pasta próprias, sem recorte por ano."""
    return f"https://www.planalto.gov.br/ccivil_03/leis/lcp/Lcp{numero}.htm"


# ── Leitura ─────────────────────────────────────────────────────────────────
def baixar(url: str) -> str | None:
    """O texto da lei, ou None quando o número não existe (404)."""
    try:
        bruto = REDE.obter(url, ausentes=(403, 404, 500))
    except FalhaDeRede as e:
        # Outro erro HTTP sobe; conexão que não abre conta como vazio.
        if isinstance(e.causa, urllib.error.HTTPError) or not isinstance(
                e.causa, (urllib.error.URLError, TimeoutError)):
            raise e.causa from e
        return None
    if bruto is None:
        return None
    try:
        return bruto.decode("utf-8")
    except UnicodeDecodeError:
        return bruto.decode("cp1252", errors="replace")


def limpar(html: str) -> str:
    """Texto legível a partir do HTML — com as entidades desfeitas.

    Desfazer entidade não é detalhe: o Planalto escreve o cabeçalho como
    `LEI N&ordm; 15.487`, e sem `unescape` o `&ordm;` fica literal, o cabeçalho
    não casa e a lei entra sem ano declarado — o que desliga o corte de ano da
    caminhada e faz ela invadir o ano anterior.
    """
    import html as _h
    sem_estilo = _ESTILO.sub(" ", html or "")
    return re.sub(r"\s+", " ", _h.unescape(_TAG.sub(" ", sem_estilo))).strip()


def ementa_do_texto(texto: str) -> str:
    """O que a lei DIZ que faz — entre o cabeçalho e "O PRESIDENTE DA REPÚBLICA".

    É o campo que decide a leitura humana: uma linha por lei, e o revisor sabe
    se precisa abrir. Sem o recorte, sairia o começo do articulado, que é onde
    todas as leis se parecem.

    A âncora é o CABEÇALHO da própria lei, não uma data qualquer: a ementa de
    uma lei alteradora cita outras leis com as datas delas — "o Decreto-Lei nº
    2.848, de 7 de dezembro de 1940" —, e ancorar em "DE … DE <ano>" fazia o
    recorte começar no meio da própria ementa.
    """
    cab = _CABECALHO.search(texto or "")
    if not cab:
        return (texto or "")[:220]
    resto = texto[cab.end():].lstrip(" .")
    fim = _PROMULGACAO.search(resto)
    ementa = (resto[:fim.start()] if fim else resto[:400]).strip()
    return ementa or resto[:220]


def ano_do_texto(texto: str) -> int | None:
    """O ano que o cabeçalho da própria lei declara."""
    m = _CABECALHO.search(texto or "")
    return int(m.group(1)) if m else None


def numeros_vigiados() -> set[int]:
    """Os números de lei que `data/fontes.json` já acompanha."""
    dados = json.loads(FONTES.read_text(encoding="utf-8"))
    numeros = set()
    for f in dados["fontes"]:
        m = _NUMERO_NA_URL.search(f["url"])
        if m:
            numeros.add(int(m.group(1).replace(".", "")))
    return numeros


# ── A caminhada ─────────────────────────────────────────────────────────────
def examinar(numero: int, ano: int, buscar=None) -> dict | None:
    """Baixa uma lei e diz se ela comina pena. None quando não existe."""
    buscar = buscar or baixar
    html = buscar(url_da_lei(numero, ano))
    if html is None:
        return None
    texto = limpar(html)
    return {
        "numero": numero,
        "ano_declarado": ano_do_texto(texto),
        "penal": comina_pena(texto),
        "url": url_da_lei(numero, ano),
        "ementa": ementa_do_texto(texto),
    }


def caminhar(ano: int, semente: int, buscar=None, orcamento: int = 900,
             pausa: float = PAUSA) -> tuple[dict[int, dict], list[str]]:
    """Todas as leis do ano, sondadas a partir de uma semente que exista nele.

    Sobe até `VAZIOS_ATE_PARAR` ausências seguidas — que é o fim do ano — e desce
    até sair do ano, porque abaixo do primeiro número o mesmo endereço passa a
    404: as leis anteriores moram na pasta do ano anterior.

    `orcamento` é o teto de requisições. Existe para que uma semente errada não
    vire uma varredura de milhares de páginas.
    """
    achadas: dict[int, dict] = {}
    avisos: list[str] = []
    gastos = 0

    for passo in (1, -1):
        vazios, n = 0, semente
        while vazios < VAZIOS_ATE_PARAR and gastos < orcamento:
            if n in achadas:
                n += passo
                continue
            lei = examinar(n, ano, buscar)
            gastos += 1
            if pausa:
                time.sleep(pausa)
            if lei is None:
                vazios += 1
            elif lei["ano_declarado"] and lei["ano_declarado"] != ano:
                # Saiu do ano: a numeração é contínua entre anos, e o corte é
                # o que o cabeçalho da lei declara.
                break
            else:
                vazios = 0
                achadas[n] = lei
            n += passo

    if gastos >= orcamento:
        avisos.append(
            f"orçamento de {orcamento} requisições esgotado — a varredura pode "
            "estar incompleta; confira a semente ou eleve `--orcamento`")
    return achadas, avisos


# ── Relatório ───────────────────────────────────────────────────────────────
def montar_relatorio(ano: int, achadas: dict[int, dict], vigiados: set[int],
                     avisos: list[str]) -> str:
    L = [f"## Leis de {ano} — o que o filtro semanal não examinou "
         f"— {hoje().isoformat()}", ""]

    if not achadas:
        L += ["> Nenhuma lei foi lida. Sem isso esta conferência **não afirma "
              "nada** — e não afirmar é o certo: reportar zero sem ter lido a "
              "fonte seria produzir exatamente o silêncio que ela existe para "
              "quebrar.", ""]
        return "\n".join(L + [f"> {a}" for a in avisos]) + "\n"

    penais = {n: v for n, v in achadas.items() if v["penal"]}
    fora = {n: v for n, v in penais.items() if n not in vigiados}

    L += [f"Foram lidas **{len(achadas)}** leis de {ano}, uma a uma, contra o "
          f"mesmo critério do Sentinela (o preceito secundário). Destas, "
          f"**{len(penais)}** cominam pena, e **{len(penais) - len(fora)}** já "
          "estão entre os diplomas vigiados.", ""]

    if not fora:
        L += ["**Nenhuma lei penal ficou de fora da vigilância.** A janela do "
              "falso negativo está fechada para este ano.", ""]
        return "\n".join(L + [f"> {a}" for a in avisos]) + "\n"

    L += [f"### {len(fora)} lei(s) cominam pena e NÃO são vigiadas", "",
          "> Cominar pena não é criar tipo penal novo: a lei pode estar apenas "
          "alterando diploma que já acompanhamos por outro número, ou repetindo "
          "preceito. A leitura é humana e curta — basta a ementa. O que criar "
          "tipo próprio vira entrada em `data/fontes.json`.", ""]
    for n in sorted(fora):
        v = fora[n]
        formatado = f"{n // 1000}.{n % 1000:03d}" if n >= 1000 else str(n)
        L += [f"- **Lei nº {formatado}/{ano}** — {v['url']}",
              f"  - {v['ementa'][:180]}"]
    L.append("")
    return "\n".join(L + [f"> {a}" for a in avisos]) + "\n"


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(
        description="Baixa todas as leis do ano e acha as penais que ninguém vigia.")
    p.add_argument("--ano", type=int, default=hoje().year)
    p.add_argument("--de", type=int, help="semente: um número de lei que exista no ano")
    p.add_argument("--orcamento", type=int, default=900)
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()

    vigiados = numeros_vigiados()
    semente = args.de or (max(vigiados) if vigiados else 15000)
    achadas, avisos = caminhar(args.ano, semente, orcamento=args.orcamento)

    relatorio = montar_relatorio(args.ano, achadas, vigiados, avisos)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"leis-do-ano-{args.ano}.md").write_text(relatorio, encoding="utf-8")
    (destino / f"leis-do-ano-{args.ano}.json").write_text(
        json.dumps({"ano": args.ano, "semente": semente, "avisos": avisos,
                    "leis": achadas}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(relatorio)

    fora = [n for n, v in achadas.items() if v["penal"] and n not in vigiados]
    return 3 if fora else 0


if __name__ == "__main__":
    raise SystemExit(main())
