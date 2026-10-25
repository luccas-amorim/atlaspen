# -*- coding: utf-8 -*-
"""O Relator: o que o STF decidiu, na semana, sobre a lei que vigiamos.

`docs/dados-abertos.md` declarava o limite: "decisão de tribunal superior que
altere o catálogo — uma ADI que retira dispositivo do ordenamento — não passa
pelo Diário Oficial e hoje nenhum robô a vê". Este robô vê uma parte dela: toda
semana, lê no Banco Nacional de Precedentes do CNJ (`fontes/cnj.py`) os
precedentes do STF atualizados na janela — controle concentrado (ADI, ADPF, ADC,
ADO) e temas de repercussão geral — e separa os que tocam um diploma de
`data/fontes.json`.

- No controle concentrado, o diploma e o artigo saem do ato impugnado, que o CNJ
  codifica (`LEG-FED DEL-002848 ANO-1940 ART-00331` é o CP, art. 331).
- No tema de repercussão geral não há ato codificado: o diploma sai da questão e
  da tese, pela citação ("Decreto-lei 3.688/1941") ou pelo nome do código ("Lei
  de Contravenções Penais"), e o artigo, do "art. N" que vem logo antes.

A natureza da decisão — não recepção, inconstitucionalidade, interpretação
conforme, recepção, constitucionalidade — é uma PISTA lida do texto: a ementa da
ADPF 338, que julgou constitucional o aumento do art. 141, II, do CP, cita a
inconstitucionalidade pedida e sai marcada por ela. O que toca registro do
catálogo sobe de prioridade. NADA daqui escreve no catálogo: uma decisão do STF muda um registro
só depois de lida por quem assina, e o banco do CNJ é incompleto (ver
`fontes/cnj.py`). O que o Relator não vê continua não visto: decisão que não
chegou ao banco, e decisão de outro tribunal.

Uso:
    python scripts/robos/relator/decisoes.py               # janela de 8 dias
    python scripts/robos/relator/decisoes.py --dias 30

Saídas: 0 = nada que mude o alcance da lei vigiada; 3 = há decisão a ler;
2 = o CNJ não pôde ser lido.
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
RELATORIOS = RAIZ / "crawler" / "relatorios"

_SIGLA = {"lei": "LEI", "decreto.lei": "DEL", "lei.complementar": "LCP"}
# O nome por que o texto de um tema chama o diploma. A Constituição fica de fora:
# todo tema a cita.
NOMES = {
    "cp": r"C[óo]digo Penal(?!\s+Militar)",
    "cpm": r"C[óo]digo Penal Militar",
    "cpp": r"C[óo]digo de Processo Penal",
    "lcp": r"Lei (?:das|de) Contraven[çc][õo]es Penais",
    "lep": r"Lei de Execu[çc][ãa]o Penal",
    "ctb": r"C[óo]digo de Tr[âa]nsito",
    "ce": r"C[óo]digo Eleitoral",
    "eca": r"Estatuto da Crian[çc]a e do Adolescente",
    "cdc": r"C[óo]digo de Defesa do Consumidor",
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
# Muda o alcance da lei: é o que abre issue.
ALCANCE = {"não recepção", "inconstitucionalidade", "interpretação conforme"}
# 20 páginas de 50 (`cnj.atualizados_desde`). A semana traz uma ou duas dezenas;
# o ano, mais de mil.
LIMITE = 1000


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


def natureza(texto: str) -> str:
    for nome, padrao in NATUREZAS:
        if re.search(padrao, texto or "", re.I):
            return nome
    return "outra"


def ids_do_catalogo(fonte: str, artigos: list[str], chaves: dict[str, list[int]]) -> list[int]:
    ids: set[int] = set()
    for art in artigos:
        alvo = f"{fonte}|art. {art}"
        for chave, lista in chaves.items():
            if chave == alvo or chave.startswith(alvo + ","):
                ids.update(lista)
    return sorted(ids)


def avaliar(p: cnj.Precedente, codigos, padroes, chaves) -> dict | None:
    tocados = pelo_ato(p.ato_impugnado, codigos) if p.ato_impugnado else {}
    for fonte, arts in pelo_texto(p.texto, padroes).items():
        tocados.setdefault(fonte, [])
        tocados[fonte] += [a for a in arts if a not in tocados[fonte]]
    if not tocados:
        return None
    ids = sorted({i for f, arts in tocados.items() for i in ids_do_catalogo(f, arts, chaves)})
    nat = natureza(p.texto)
    return {"id": p.id, "rotulo": p.rotulo, "decisao": p.decisao, "natureza": nat,
            "atualizado_em": p.atualizado_em.isoformat() if p.atualizado_em else None,
            "fontes": tocados, "ids": ids, "paradigmas": list(p.paradigmas),
            "texto": p.texto[:600], "a_ler": nat in ALCANCE or bool(ids)}


def montar_relatorio(achados: list[dict], lidos: int, desde: date, dia: date, erro: str | None) -> str:
    L = [f"## Tribunais — o que o STF atualizou sobre a lei vigiada, desde {desde:%d/%m/%Y} — {dia.isoformat()}", ""]
    if erro:
        return "\n".join(L + [f"> O Banco Nacional de Precedentes do CNJ não pôde ser lido: {erro}", ""]) + "\n"
    a_ler = [a for a in achados if a["a_ler"]]
    citam = [a for a in achados if not a["a_ler"]]
    L += [f"**{lidos}** precedente(s) do STF atualizado(s) na janela; **{len(achados)}** toca(m) diploma "
          f"vigiado; **{len(a_ler)}** pede(m) leitura.", "",
          "> Fonte: Banco Nacional de Precedentes do CNJ, oficial e incompleto — o silêncio dele não prova "
          "nada. A natureza ao lado de cada um é pista lida do texto, não classificação. A decisão muda o "
          "catálogo só depois de lida por quem assina.", ""]
    if lidos >= LIMITE:
        L += [f"> A janela passou de {LIMITE} precedentes, o teto da leitura: o que veio além não foi lido.", ""]

    def linha(a):
        onde = "; ".join(f"`{f}`" + (f", arts. {', '.join(arts)}" if arts else "") for f, arts in a["fontes"].items())
        ids = (" — **toca registro(s) do catálogo**: " + ", ".join(f"[{i}]({SITE}/tipos/{i})" for i in a["ids"][:10])
               if a["ids"] else "")
        par = f" (paradigma: {', '.join(a['paradigmas'])})" if a["paradigmas"] else ""
        return [f"- **{a['rotulo']}**{par} — {a['natureza']} — {onde}{ids}", f"  - {a['texto'][:300]}"]
    if a_ler:
        L += ["### Pedem leitura — mudam o alcance da norma ou tocam registro do catálogo", ""]
        for a in sorted(a_ler, key=lambda x: (-len(x["ids"]), x["rotulo"])):
            L += linha(a)
        L.append("")
    if citam:
        L += ["### Citam diploma vigiado, sem mudar o alcance dele", ""]
        L += [f"- {a['rotulo']} — {a['natureza']} — " + ", ".join(f"`{f}`" for f in a["fontes"]) for a in citam]
        L.append("")
    return "\n".join(L) + "\n"


def codigo_de_saida(achados: list[dict], erro: str | None) -> int:
    if erro:
        return 2
    return 3 if any(a["a_ler"] for a in achados) else 0


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="O que o STF decidiu sobre a lei vigiada.")
    p.add_argument("--dias", type=int, default=8)
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()

    dia = hoje()
    desde = dia - timedelta(days=args.dias)
    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    codigos, padroes = indices(fontes)
    chaves = chaves_do_catalogo()
    erro, achados, lidos = None, [], 0
    try:
        precedentes = cnj.atualizados_desde(desde)
        lidos = len(precedentes)
        achados = [a for a in (avaliar(x, codigos, padroes, chaves) for x in precedentes) if a]
    except (FalhaDeRede, ValueError) as e:
        erro = str(e)
    relatorio = montar_relatorio(achados, lidos, desde, dia, erro)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"tribunais-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    (destino / f"tribunais-{dia.isoformat()}.json").write_text(
        json.dumps(achados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio)
    return codigo_de_saida(achados, erro)


if __name__ == "__main__":
    raise SystemExit(main())
