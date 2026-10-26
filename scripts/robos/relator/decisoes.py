# -*- coding: utf-8 -*-
"""O Relator: o que o STF e o STJ decidiram, na semana, sobre a lei que vigiamos.

`docs/dados-abertos.md` declarava o limite: "decisão de tribunal superior que
altere o catálogo — uma ADI que retira dispositivo do ordenamento — não passa
pelo Diário Oficial e hoje nenhum robô a vê". Este robô vê uma parte dela: toda
semana, lê no Banco Nacional de Precedentes do CNJ (`fontes/cnj.py`) os
precedentes atualizados na janela — do STF, o controle concentrado (ADI, ADPF,
ADC, ADO), os temas de repercussão geral, as súmulas e as súmulas vinculantes; do
STJ, as súmulas, os repetitivos e os IAC (`cnj.CONSULTAS`) — e separa os que
tocam um diploma de `data/fontes.json`.

- No controle concentrado, o diploma e o artigo saem do ato impugnado, que o CNJ
  codifica (`LEG-FED DEL-002848 ANO-1940 ART-00331` é o CP, art. 331).
- No tema, no repetitivo e na súmula não há ato codificado: o diploma sai da
  questão e da tese, pela citação ("Decreto-lei 3.688/1941"), pelo nome do código
  ("Lei de Contravenções Penais") ou pela sigla que o STJ usa ("art. 155, § 4º,
  do CP"), e o artigo, do "art. N" que vem logo antes.

A natureza da decisão — não recepção, inconstitucionalidade, interpretação
conforme, recepção, constitucionalidade — é uma PISTA lida do texto: a ementa da
ADPF 338, que julgou constitucional o aumento do art. 141, II, do CP, cita a
inconstitucionalidade pedida e sai marcada por ela. O que toca registro do
catálogo, ou dispositivo em que um atributo penal se apoia (`dispositivos` de
`data/atributos.json`: a remição é o art. 126 da LEP), sobe de prioridade. Na súmula e no tema, a situação que o CNJ registra
fala primeiro: súmula cancelada, superada ou alterada, e tese revisada, mudam a
leitura da lei tanto quanto uma ADI. NADA daqui escreve no catálogo: uma decisão
muda um registro só depois de lida por quem assina, e o banco do CNJ é incompleto
(ver `fontes/cnj.py`). O que o Relator não vê continua não visto: decisão que não
chegou ao banco, e decisão de outro tribunal — o STM, que julga os registros do
CPM, não tem nenhum precedente lá.

Uso:
    python scripts/robos/relator/decisoes.py               # janela de 8 dias
    python scripts/robos/relator/decisoes.py --dias 30

Saídas: 0 = nada que mude o alcance da lei vigiada; 3 = há decisão a ler;
2 = o CNJ não pôde ser lido, para um dos tribunais ou para os dois.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cotejador.frescor import chaves_do_catalogo  # noqa: E402
from endereco_publico import SITE  # noqa: E402
from fontes import cnj  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
ATRIBUTOS = RAIZ / "data" / "atributos.json"
RELATORIOS = RAIZ / "crawler" / "relatorios"

_SIGLA = {"lei": "LEI", "decreto.lei": "DEL", "lei.complementar": "LCP"}
# O nome por que o texto de um tema chama o diploma. A Constituição fica de fora:
# todo tema a cita. A sigla é a do texto do STJ ("do CP"), e casa só em
# maiúsculas — `(?-i:…)` desliga, ali, o `re.I` do resto do padrão.
NOMES = {
    "cp": r"C[óo]digo Penal(?!\s+Militar)|(?-i:\bCP\b)",
    "cpm": r"C[óo]digo Penal Militar|(?-i:\bCPM\b)",
    "cpp": r"C[óo]digo de Processo Penal|(?-i:\bCPP\b)",
    "lcp": r"Lei (?:das|de) Contraven[çc][õo]es Penais|(?-i:\bLCP\b)",
    "lep": r"Lei de Execu[çc][ãa]o Penal|(?-i:\bLEP\b)",
    "ctb": r"C[óo]digo de Tr[âa]nsito|(?-i:\bCTB\b)",
    "ce": r"C[óo]digo Eleitoral",
    "eca": r"Estatuto da Crian[çc]a e do Adolescente|(?-i:\bECA\b)",
    "cdc": r"C[óo]digo de Defesa do Consumidor|(?-i:\bCDC\b)",
    "drogas-11343": r"Lei (?:de Drogas|Antidrogas|de T[óo]xicos)",
    "desarmamento-10826": r"Estatuto do Desarmamento",
    "maria-penha-11340": r"Lei Maria da Penha",
    "hediondos-8072": r"Lei dos Crimes Hediondos",
    "idoso-10741": r"Estatuto (?:do Idoso|da Pessoa Idosa)",
    "juizados-9099": r"Lei dos Juizados Especiais",
    "abuso-13869": r"Lei de Abuso de Autoridade",
    "lavagem-9613": r"Lei de Lavagem",
    "orgcrim-12850": r"Lei (?:de|das) Organiza[çc][õo]es Criminosas",
}
NATUREZAS = [
    ("não recepção", r"n[ãa]o\s+(?:foi\s+|foram\s+)?recep(?:cion|[çc][ãa]o)"),
    ("inconstitucionalidade", r"(?<!n[ãa]o )inconstitucional"),
    ("interpretação conforme", r"interpreta[çc][ãa]o conforme"),
    ("recepção", r"recepcionad|recep[çc][ãa]o"),
    # Depois de "inconstitucional": o `\b` não casa dentro de "inconstitucionalidade".
    ("constitucionalidade", r"\b(?:é|são)\s+constitucional\b|\bconstitucionalidade\b"),
]
# A situação que o CNJ registra, por tipo. Tema de repetitivo ou de repercussão
# geral cancelado é afetação desfeita — não houve tese —, e por isso não está em
# ALCANCE; súmula cancelada é enunciado que deixou de valer.
SITUACOES = {
    ("SUM", "SV"): [("súmula cancelada", "cancel"), ("súmula superada", "superad"),
                    ("súmula alterada", "alterad")],
    ("RR", "IAC", "RG"): [("tese revisada", "revisad"), ("tema cancelado", "cancel")],
}
# Muda o alcance da lei: é o que abre issue.
ALCANCE = {"não recepção", "inconstitucionalidade", "interpretação conforme",
           "súmula cancelada", "súmula superada", "súmula alterada", "tese revisada"}
# 20 páginas de 50 (`cnj.atualizados_desde`), por tribunal. A semana traz uma ou
# duas dezenas; o ano, mais de mil.
LIMITE = 1000
# No corpo da issue, o que pede leitura vai até aqui; o resto fica no JSON do
# artifact. Uma recarga em massa do CNJ (as 734 súmulas do STF têm todas a mesma
# data de atualização) estouraria o teto de 65.536 caracteres do corpo.
A_MOSTRAR = 40
# A súmula que muda de alcance e fala de crime sem citar o diploma — "No crime
# de roubo, a intimidação feita com arma de brinquedo autoriza o aumento da
# pena" (Súmula 174 do STJ, cancelada) — não casa com fonte nenhuma, e calaria.
PENAL = re.compile(r"\b(?:crimes?|delitos?|contraven[çc][ãa]o|penal|penas?|r[ée]us?|"
                   r"tipicidade|punibilidade|dosimetria)\b", re.I)


def _milhar(n: int) -> str:
    return f"{n // 1000}.{n % 1000:03d}" if n >= 1000 else str(n)


def indices(fontes: list[dict]) -> tuple[dict[str, str], dict[str, re.Pattern]]:
    """({código do ato impugnado: id da fonte}, {id da fonte: padrão de citação no texto})."""
    codigos, padroes = {}, {}
    for f in fontes:
        partes = (f.get("urn") or "").split(":")
        if len(partes) != 6 or partes[4] not in _SIGLA:
            continue
        data, numero = partes[5].split(";")
        n = int(numero)
        codigos[f"LEG-FED {_SIGLA[partes[4]]}-{n:06d} ANO-{data[:4]}"] = f["id"]
        especie = {"lei": r"(?<!Decreto-)(?<!Decreto )Lei", "decreto.lei": r"Decreto-?\s*[Ll]ei",
                   "lei.complementar": r"Lei\s+Complementar"}[partes[4]]
        citacao = rf"{especie}\s*(?:n[ºo°.]*\s*)?{re.escape(_milhar(n))}(?![\d.])"
        nome = NOMES.get(f["id"])
        padroes[f["id"]] = re.compile(citacao + (rf"|{nome}" if nome else ""), re.I)
    return codigos, padroes


_ART_CODIGO = re.compile(r"ART-0*(\d+)([A-Z]?)\b")


def pelo_ato(ato: str, codigos: dict[str, str]) -> dict[str, list[str]]:
    """{fonte: [artigos]} do ato impugnado codificado."""
    saida: dict[str, list[str]] = {}
    for trecho in re.split(r"(?=LEG-FED )", ato or ""):
        fonte = next((fid for cod, fid in codigos.items() if trecho.startswith(cod)), None)
        if not fonte:
            continue
        arts = [n + (f"-{s.lower()}" if s else "") for n, s in _ART_CODIGO.findall(trecho)]
        saida.setdefault(fonte, [])
        saida[fonte] += [a for a in arts if a not in saida[fonte]]
    return saida


_ART_TEXTO = re.compile(r"\barts?\.\s*(\d+)\s*[ºo°]?((?:-[A-Z])?)", re.I)


def pelo_texto(texto: str, padroes: dict[str, re.Pattern]) -> dict[str, list[str]]:
    """{fonte: [artigos]} das citações no texto: o artigo é o "art. N" até 80
    caracteres antes da menção ao diploma ("o art. 25 da Lei de Contravenções…")."""
    saida: dict[str, list[str]] = {}
    for fonte, padrao in padroes.items():
        for m in padrao.finditer(texto or ""):
            arts = saida.setdefault(fonte, [])
            for a in _ART_TEXTO.finditer(texto[max(0, m.start() - 80):m.start()]):
                art = a.group(1) + a.group(2).lower()
                if art not in arts:
                    arts.append(art)
    return saida


def natureza(texto: str, situacao: str | None = None, tipo: str | None = None) -> str:
    s = (situacao or "").lower()
    for tipos, regras in SITUACOES.items():
        if tipo in tipos:
            for nome, marca in regras:
                if marca in s:
                    return nome
    for nome, padrao in NATUREZAS:
        if re.search(padrao, texto or "", re.I):
            return nome
    return "outra"


def ids_do_catalogo(fonte: str, artigos: list[str], chaves: dict) -> list:
    """O que está indexado pelo artigo, em qualquer parágrafo dele: os ids do
    catálogo em `chaves_do_catalogo`, os atributos em `indice_atributos`."""
    ids: set = set()
    for art in artigos:
        alvo = f"{fonte}|art. {art}"
        for chave, lista in chaves.items():
            if chave == alvo or chave.startswith(alvo + ","):
                ids.update(lista)
    return sorted(ids)


def indice_atributos(caminho: Path = ATRIBUTOS) -> dict[str, list[str]]:
    """{dispositivo: [slug]} dos atributos penais — a mesma chave do catálogo."""
    if not caminho.exists():
        return {}
    indice: dict[str, list[str]] = {}
    for a in json.loads(caminho.read_text(encoding="utf-8"))["atributos"]:
        for d in a.get("dispositivos") or []:
            indice.setdefault(d, []).append(a["slug"])
    return indice


def avaliar(p: cnj.Precedente, codigos, padroes, chaves, atributos=None) -> dict | None:
    tocados = pelo_ato(p.ato_impugnado, codigos) if p.ato_impugnado else {}
    for fonte, arts in pelo_texto(p.texto, padroes).items():
        tocados.setdefault(fonte, [])
        tocados[fonte] += [a for a in arts if a not in tocados[fonte]]
    nat = natureza(p.texto, p.situacao, p.tipo)
    if not tocados and not (nat in ALCANCE and PENAL.search(p.texto)):
        return None
    ids = sorted({i for f, arts in tocados.items() for i in ids_do_catalogo(f, arts, chaves)})
    attrs = sorted({s for f, arts in tocados.items() for s in ids_do_catalogo(f, arts, atributos or {})})
    return {"id": p.id, "orgao": p.orgao, "rotulo": p.rotulo, "decisao": p.decisao,
            "situacao": p.situacao, "natureza": nat,
            "atualizado_em": p.atualizado_em.isoformat() if p.atualizado_em else None,
            "fontes": tocados, "ids": ids, "atributos": attrs, "paradigmas": list(p.paradigmas),
            "texto": p.texto[:600], "a_ler": nat in ALCANCE or bool(ids) or bool(attrs)}


def montar_relatorio(achados: list[dict], lidos: dict[str, int], desde: date, dia: date,
                     erros: dict[str, str]) -> str:
    L = [f"## Tribunais — o que o STF e o STJ atualizaram sobre a lei vigiada, desde {desde:%d/%m/%Y} "
         f"— {dia.isoformat()}", ""]
    for orgao, erro in erros.items():
        L += [f"> O Banco Nacional de Precedentes do CNJ não pôde ser lido para o {orgao}: {erro}", ""]
    if not lidos:
        return "\n".join(L) + "\n"
    a_ler = [a for a in achados if a["a_ler"]]
    citam = [a for a in achados if not a["a_ler"]]
    contagem = "; ".join(f"**{n}** do {o}" for o, n in lidos.items())
    L += [f"Precedentes atualizados na janela: {contagem}. **{len(achados)}** toca(m) diploma "
          f"vigiado; **{len(a_ler)}** pede(m) leitura.", "",
          "> Fonte: Banco Nacional de Precedentes do CNJ, oficial e incompleto — o silêncio dele não prova "
          "nada. A natureza ao lado de cada um é pista lida do texto, não classificação. A decisão muda o "
          "catálogo só depois de lida por quem assina.", ""]
    for orgao, n in lidos.items():
        if n >= LIMITE:
            L += [f"> No {orgao}, a janela passou de {LIMITE} precedentes, o teto da leitura: o que veio "
                  "além não foi lido.", ""]

    def linha(a):
        onde = ("; ".join(f"`{f}`" + (f", arts. {', '.join(arts)}" if arts else "") for f, arts in a["fontes"].items())
                or "fala de matéria penal sem citar diploma")
        ids = (" — **toca registro(s) do catálogo**: " + ", ".join(f"[{i}]({SITE}/tipos/{i})" for i in a["ids"][:10])
               if a["ids"] else "")
        if a.get("atributos"):
            ids += " — **toca atributo(s)**: " + ", ".join(f"[{s}]({SITE}/atributos/{s})" for s in a["atributos"])
        par = f" (paradigma: {', '.join(a['paradigmas'][:3])})" if a["paradigmas"] else ""
        return [f"- **{a['rotulo']}**{par} — {a['natureza']} — {onde}{ids}", f"  - {a['texto'][:300]}"]
    if a_ler:
        L += ["### Pedem leitura — mudam o alcance da norma, ou tocam registro do catálogo ou atributo penal", ""]
        ordem = sorted(a_ler, key=lambda x: (x["natureza"] not in ALCANCE, -len(x["ids"]) - len(x.get("atributos", [])),
                                             x["rotulo"]))
        for a in ordem[:A_MOSTRAR]:
            L += linha(a)
        if len(ordem) > A_MOSTRAR:
            L.append(f"- _e mais {len(ordem) - A_MOSTRAR}, no `tribunais-{dia.isoformat()}.json` do artifact._")
        L.append("")
    if citam:
        L += ["### Citam diploma vigiado, sem mudar o alcance dele", ""]
        L += [f"- {a['rotulo']} — {a['natureza']} — " + ", ".join(f"`{f}`" for f in a["fontes"])
              for a in citam[:A_MOSTRAR]]
        if len(citam) > A_MOSTRAR:
            L.append(f"- _e mais {len(citam) - A_MOSTRAR}._")
        L.append("")
    return "\n".join(L) + "\n"


def codigo_de_saida(achados: list[dict], erros) -> int:
    if erros:
        return 2
    return 3 if any(a["a_ler"] for a in achados) else 0


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="O que o STF e o STJ decidiram sobre a lei vigiada.")
    p.add_argument("--dias", type=int, default=8)
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()

    dia = hoje()
    desde = dia - timedelta(days=args.dias)
    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    codigos, padroes = indices(fontes)
    chaves = chaves_do_catalogo()
    atributos = indice_atributos()
    erros, achados, lidos = {}, [], {}
    for orgao in cnj.CONSULTAS:
        try:
            precedentes = cnj.atualizados_desde(desde, orgao)
        except (FalhaDeRede, ValueError) as e:
            erros[orgao] = str(e)
            continue
        lidos[orgao] = len(precedentes)
        achados += [a for a in (avaliar(x, codigos, padroes, chaves, atributos) for x in precedentes) if a]
    relatorio = montar_relatorio(achados, lidos, desde, dia, erros)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"tribunais-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    (destino / f"tribunais-{dia.isoformat()}.json").write_text(
        json.dumps(achados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio)
    return codigo_de_saida(achados, erros)


if __name__ == "__main__":
    raise SystemExit(main())
