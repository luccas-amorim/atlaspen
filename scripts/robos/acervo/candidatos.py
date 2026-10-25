# -*- coding: utf-8 -*-
"""Os candidatos ao acervo histórico: o que a lei tirou de vigência e o acervo ainda não tem.

F5 do plano de fontes abertas (.superpowers/planos/). O acervo (`data/acervo.json`)
tem 14 registros; os compilados que o Vigia baixa toda semana marcam centenas
de dispositivos como revogados. Este módulo levanta, entre eles, os que podem
ter sido CRIME — e diz, de cada um, que prova há disso. Não escreve no acervo:
o que entra é juízo de quem assina, e a regra do `_meta` do acervo continua
valendo (só entra o que a lei tirou de vigência; registro errado que saiu do
catálogo vai para a nota da versão).

**Duas frentes.**

1. *Dispositivos revogados dentro dos diplomas vigiados.* Para cada fonte de
   `data/fontes.json`, o snapshot do Planalto é lido com `nucleo/parsear.py`; o
   que vem `revogado`, dentro do intervalo penal que `inventario_diplomas.py`
   delimita, vira candidato, com o nome (a epígrafe), a lei revogadora e o ano —
   tudo do compilado, que é a fonte que vale.

2. *Diplomas penais revogados no todo.* A ficha de cada fonte no Senado
   (`fontes/senado.py`) lista as normas ANTERIORES que ela revogou no todo — a
   Lei 13.869/2019 revogou a Lei 4.898/1965. As que `data/diplomas.json` ainda
   não registra são candidatas, e o texto original no normas.leg.br diz se
   havia pena nelas.

**A prova de que era crime, em níveis** (a decisão 2 do plano pedia "pena no
texto riscado"; medido em 25/10/2026, o compilado do CP NÃO guarda o riscado do
artigo revogado — o art. 240 é só "Art. 240 - (Revogado pela Lei nº 11.106, de
2005)" —, e por isso o nível do original existe; qual nível basta é decisão de
quem assina):

- `pena_no_compilado` — o próprio compilado ainda traz a pena (a LCP mantém o
  texto revogado no lugar). Prova do Planalto.
- `pena_no_original` — a versão ORIGINAL do diploma no normas.leg.br tem a
  pena no artigo. Fonte secundária: o texto é de quando o diploma saiu, não
  necessariamente o da véspera da revogação.
- `pede_juizo` — revogado no intervalo penal, sem pena achada.
- `fora_do_intervalo` — revogado fora do intervalo penal (parte geral,
  processo, administração): nomeado, não some.

Uso:
    python scripts/robos/acervo/candidatos.py                  # snapshots do Vigia
    python scripts/robos/acervo/candidatos.py --fonte cp --fonte lcp
    python scripts/robos/acervo/candidatos.py --sem-rede       # só a frente 1, sem o original
    python scripts/robos/acervo/candidatos.py --snapshots DIR --saida DIR

Saídas: 0 = nada novo; 3 = há candidato novo; 2 = nada pôde ser lido.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import inventario_diplomas as _inv  # noqa: E402
from cotejador.frescor import texto_plano  # noqa: E402
from fontes import normas, senado  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.parsear import como_dicionarios, parsear  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
DIPLOMAS = RAIZ / "data" / "diplomas.json"
ACERVO = RAIZ / "data" / "acervo.json"
SNAPSHOTS = RAIZ / "crawler" / "snapshots"
RELATORIOS = RAIZ / "crawler" / "relatorios"

NIVEIS = ("pena_no_compilado", "pena_no_original", "pede_juizo", "fora_do_intervalo")

_PENA = re.compile(r"\bPena\s*[-–—:]", re.I)
_ART_ORIGINAL = re.compile(r"\bArt(?:igo)?\.?\s*(\d+)\s*[º°o]?((?:-[A-Z])*)\s*[.\-–—]", re.I)
_NUMERO_NA_NORMA = re.compile(r"n[ºo°.\s]*\s*([\d.]+)", re.I)


# ── O mapa fonte -> diploma do inventário ───────────────────────────────────
def _especie_da_urn(urn: str) -> str:
    return urn.split(":")[4] if urn and urn.count(":") >= 4 else ""


def _especie_da_norma(norma: str) -> str:
    n = norma.lower()
    if n.startswith("decreto-lei"):
        return "decreto.lei"
    if n.startswith("lei complementar"):
        return "lei.complementar"
    return "lei" if n.startswith("lei") else ""


def diplomas_do_inventario(meta: dict | None = None) -> dict[tuple[str, int], tuple[str, list]]:
    """{(espécie, número): (id do diploma, faixas penais)} — o id é o de diplomas.json."""
    meta = meta if meta is not None else _inv.META
    saida = {}
    for slug, m in meta.items():
        num = _NUMERO_NA_NORMA.search(m.get("norma", ""))
        # Os revogados do inventário não têm `faixas`: não são fonte vigiada.
        if num and m.get("faixas"):
            saida[(_especie_da_norma(m["norma"]), int(num.group(1).replace(".", "")))] = (slug, m["faixas"])
    return saida


def diploma_da_fonte(fonte: dict, mapa: dict) -> tuple[str, list] | None:
    urn = fonte.get("urn") or ""
    try:
        numero = int(urn.rsplit(";", 1)[1])
    except (IndexError, ValueError):
        return None
    return mapa.get((_especie_da_urn(urn), numero))


def no_intervalo(numero: int, faixas: list) -> bool:
    return any(a <= numero <= b for a, b in faixas)


# ── Frente 1: o compilado ───────────────────────────────────────────────────
def revogados(documento: str) -> list[dict]:
    """Os dispositivos revogados do compilado, um por artigo ou por parágrafo.

    Caput revogado vale pelo artigo inteiro (os parágrafos dele não se repetem);
    parágrafo revogado sob caput vigente é candidato próprio — como o art. 150,
    §2º, do CP, que o acervo já tem.
    """
    ds = como_dicionarios(parsear(documento))
    caput_revogado = {d["artigo"] for d in ds if d["marcador"] == "caput" and d["situacao"] == "revogado"}
    saida = []
    for d in ds:
        if d["situacao"] != "revogado" or d.get("citacao"):
            continue
        if d["marcador"] != "caput" and d["artigo"] in caput_revogado:
            continue
        an = d.get("anotacao") or {}
        saida.append({"artigo": d["artigo"], "marcador": d["marcador"], "nome": _nome(d.get("epigrafe")),
                      "norma": an.get("norma"), "ano": an.get("ano"),
                      "pena_texto": d.get("pena_texto")})
    return saida


def _numero_do_artigo(artigo: str) -> tuple[int, str] | None:
    m = re.match(r"Art\.\s*(\d+)((?:-[A-Z])*)", artigo or "")
    return (int(m.group(1)), m.group(2).lower()) if m else None


def id_no_acervo(diploma: str, artigo: str, marcador: str) -> str | None:
    """("cp", "Art. 150", "§ 2º") -> "cp-150-p2"; ("cp", "Art. 121", "§ 2º-A") -> "cp-121-p2a";
    ("cp", "Art. 240", "caput") -> "cp-240"."""
    n = _numero_do_artigo(artigo)
    if not n:
        return None
    base = f"{diploma}-{n[0]}{n[1].replace('-', '')}"
    if marcador == "caput":
        return base
    p = re.search(r"(\d+)\s*[º°o]?\s*((?:-[A-Za-z])*)", marcador or "")
    if p:
        return f"{base}-p{p.group(1)}{p.group(2).replace('-', '').lower()}"
    if "único" in (marcador or "").lower():
        return f"{base}-pu"
    return None


def ja_registrados(acervo: dict) -> set[str]:
    """Os ids que o acervo já cobre: o de cada registro e os artigos dos que são
    artigo inteiro. `cp-219-222` cobre `cp-219` a `cp-222`; `cp-150-p2` cobre só
    o §2º, e não o `cp-150` que ele lista em `artigos`."""
    regs = acervo.get("registros") or []
    return ({r["id"] for r in regs}
            | {a for r in regs if not re.search(r"-p(\d+|u)$", r["id"]) for a in r.get("artigos") or []})


def segmentos_do_original(texto: str) -> dict[str, str]:
    """{"240": "Art. 240. Cometer adultério: Pena - …"} — o texto de cada artigo."""
    marcas = list(_ART_ORIGINAL.finditer(texto))
    saida: dict[str, str] = {}
    for i, m in enumerate(marcas):
        chave = f"{m.group(1)}{m.group(2).lower()}"
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        saida.setdefault(chave, texto[m.start():fim].strip())
    return saida


def nivel(rev: dict, numero: tuple[int, str], faixas: list, original: dict[str, str] | None) -> str:
    if not no_intervalo(numero[0], faixas):
        return "fora_do_intervalo"
    if rev.get("pena_texto") and _PENA.search(rev["pena_texto"]):
        return "pena_no_compilado"
    # O original é segmentado por ARTIGO: a pena do caput não diz nada sobre o
    # parágrafo revogado, que pode ser causa de aumento ou norma processual.
    if rev.get("marcador") != "caput":
        return "pede_juizo"
    trecho = (original or {}).get(f"{numero[0]}{numero[1]}")
    if trecho and _PENA.search(trecho):
        return "pena_no_original"
    return "pede_juizo"


def _nome(epigrafe: str | None) -> str | None:
    """A epígrafe, quando é nome de crime: título de seção ("DISPOSIÇÕES GERAIS",
    no art. 223 do CP) vem em maiúsculas e não é nome de nada."""
    if not epigrafe or epigrafe.isupper():
        return None
    return epigrafe


def levantar_fonte(fonte: dict, documento: str, diploma: str, faixas: list,
                   registrados: set[str], original: dict[str, str] | None) -> list[dict]:
    saida = []
    for rev in revogados(documento):
        numero = _numero_do_artigo(rev["artigo"])
        ident = id_no_acervo(diploma, rev["artigo"], rev["marcador"])
        if not numero or not ident:
            continue
        trecho = (original or {}).get(f"{numero[0]}{numero[1]}")
        saida.append({
            "fonte": fonte["id"], "diploma": diploma, "id": ident,
            "dispositivo": rev["artigo"] + ("" if rev["marcador"] == "caput" else f", {rev['marcador']}"),
            "nome": rev["nome"], "norma": rev["norma"], "ano": rev["ano"],
            "nivel": nivel(rev, numero, faixas, original),
            "ja_no_acervo": ident in registrados,
            "trecho_original": (trecho or "")[:400] or None,
        })
    return saida


# ── Frente 2: diplomas revogados no todo ────────────────────────────────────
def _numero_e_ano(nome: str) -> tuple[int, int] | None:
    m = re.search(r"n[ºo°]\s*([\d.]+)\s+de\s+\d{2}/\d{2}/(\d{4})", nome or "")
    return (int(m.group(1).replace(".", "")), int(m.group(2))) if m else None


def diplomas_ja_registrados(diplomas: dict) -> set[tuple[int, int]]:
    """(número, ano) de cada diploma de diplomas.json — vigente ou não."""
    saida = set()
    for d in diplomas.get("diplomas") or []:
        m = re.search(r"n[ºo°]\s*([\d.]+)\s*,\s*de\s+.*?(\d{4})", d.get("norma", ""))
        if m:
            saida.add((int(m.group(1).replace(".", "")), int(m.group(2))))
    return saida


def revogados_no_todo(fichas: dict[str, senado.Norma], registrados: set[tuple[int, int]]) -> list[dict]:
    """As normas anteriores que alguma fonte revogou no todo e diplomas.json não tem."""
    saida, vistos = [], set()
    for fid, ficha in fichas.items():
        for a in ficha.anteriores:
            if not a.revogada_no_todo:
                continue
            na = _numero_e_ano(a.nome)
            if not na or na in registrados or a.nome in vistos:
                continue
            vistos.add(a.nome)
            saida.append({"nome": a.nome, "codigo": a.codigo, "revogada_por": ficha.nome,
                          "fonte_revogadora": fid, "penas_no_original": None})
    return sorted(saida, key=lambda x: x["nome"])


def contar_penas(texto: str) -> int:
    return len(_PENA.findall(texto or ""))


# ── Rede (opcional) ─────────────────────────────────────────────────────────
def original_de(urn: str) -> dict[str, str] | None:
    """Os artigos da versão Original no normas.leg.br, ou None se não houver."""
    f = normas.ficha(urn)
    v = f.versao("Original") if f else None
    html = normas.texto(v) if v else None
    return segmentos_do_original(texto_plano(html)) if html else None


def penas_do_original_por_codigo(codigo: str) -> int | None:
    ficha = senado.norma_por_codigo(codigo)
    if not ficha or not ficha.urn:
        return None
    f = normas.ficha(ficha.urn)
    v = f.versao("Original") if f else None
    html = normas.texto(v) if v else None
    return contar_penas(texto_plano(html)) if html else None


# ── Relatório ───────────────────────────────────────────────────────────────
TITULO = {
    "pena_no_compilado": "Pena no próprio compilado — prova do Planalto",
    "pena_no_original": "Pena no texto original (normas.leg.br) — fonte secundária",
    "pede_juizo": "Revogados no intervalo penal, sem pena achada — pede juízo",
    "fora_do_intervalo": "Revogados fora do intervalo penal — nomeados, não somem",
}


def montar_relatorio(candidatos: list[dict], diplomas: list[dict], nao_lidos: list[str], dia) -> str:
    novos = [c for c in candidatos if not c["ja_no_acervo"]]
    L = [f"## Acervo histórico — candidatos levantados do compilado — {dia.isoformat()}", "",
         f"**{len(candidatos)}** dispositivo(s) revogado(s) nos diplomas lidos; **{len(novos)}** "
         f"fora do acervo; **{len(candidatos) - len(novos)}** já registrados. "
         f"**{len(diplomas)}** diploma(s) revogado(s) no todo que `data/diplomas.json` não tem.", "",
         "> Nada aqui entra sozinho: o acervo é juízo de quem assina. O nível diz que prova "
         "há de que o dispositivo era crime — e o do original é fonte secundária, com o texto "
         "de quando o diploma saiu, não o da véspera da revogação.", ""]
    for n in NIVEIS:
        do_nivel = [c for c in novos if c["nivel"] == n]
        if not do_nivel:
            continue
        L += [f"### {TITULO[n]} — {len(do_nivel)}", ""]
        for c in do_nivel:
            revog = f"{c['norma']}/{c['ano']}" if c.get("norma") else "norma não anotada"
            L.append(f"- `{c['id']}` — {c['fonte']}, {c['dispositivo']}"
                     + (f" — **{c['nome']}**" if c.get("nome") else "") + f" — revogado pela {revog}")
            if n != "fora_do_intervalo" and c.get("trecho_original"):
                L.append(f"  - original: {c['trecho_original'][:220]}")
        L.append("")
    if diplomas:
        com_pena = [d for d in diplomas if d["penas_no_original"]]
        sem_pena = [d for d in diplomas if d["penas_no_original"] == 0]
        nao_lido = [d for d in diplomas if d["penas_no_original"] is None]
        L += ["### Diplomas revogados no todo que `data/diplomas.json` não registra", "",
              "> Levantados das fichas do Senado das fontes vigiadas, que listam as normas que "
              "cada uma revogou no todo. A pena é contada no texto ORIGINAL (normas.leg.br).", ""]
        if com_pena:
            L += [f"Com pena no original — **{len(com_pena)}**:", ""]
            L += [f"- **{d['nome']}** — {d['penas_no_original']} \"Pena\" — revogada no todo pela "
                  f"{d['revogada_por']} (`{d['fonte_revogadora']}`)" for d in com_pena]
            L.append("")
        if sem_pena:
            L += [f"Sem pena no original — **{len(sem_pena)}**, provavelmente sem crime: "
                  + "; ".join(d["nome"] for d in sem_pena) + ".", ""]
        if nao_lido:
            L += [f"Original não lido — **{len(nao_lido)}**: " + "; ".join(d["nome"] for d in nao_lido) + ".", ""]
    if nao_lidos:
        L += ["### Não deu para ler", ""] + [f"- {x}" for x in nao_lidos] + [""]
    return "\n".join(L) + "\n"


def propostas(candidatos: list[dict], niveis: tuple[str, ...] = ("pena_no_compilado", "pena_no_original")) -> list[dict]:
    """Registros no formato de `data/acervo.json`, para quem assina copiar e corrigir.

    `data_revogacao` e `texto_original` saem nulos: o `_meta` do acervo admite os
    dois, e o trecho do original não é o texto da véspera da revogação."""
    saida = []
    for c in candidatos:
        if c["ja_no_acervo"] or c["nivel"] not in niveis:
            continue
        norma = (c.get("norma") or "").replace("Lei nº ", "Lei ")
        saida.append({
            "id": c["id"], "dispositivo": c["dispositivo"], "nome": c.get("nome"),
            "diploma": c["diploma"], "artigos": [c["id"].split("-p")[0]],
            "categoria": "revogado",
            "o_que_houve": f"Revogado pela {norma}/{c['ano']}." if norma else None,
            "normas": [{"norma": f"{norma}/{c['ano']}", "ano": c["ano"]}] if norma else [],
            "caso": False, "retirado": None, "data_revogacao": None, "texto_original": None,
            "_nivel": c["nivel"],
        })
    return saida


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Candidatos ao acervo histórico, a partir do compilado.")
    p.add_argument("--fonte", action="append", default=[], metavar="ID")
    p.add_argument("--snapshots", default=str(SNAPSHOTS))
    p.add_argument("--saida", default=str(RELATORIOS))
    p.add_argument("--sem-rede", action="store_true",
                   help="não lê o original no normas.leg.br nem as fichas do Senado")
    args = p.parse_args()

    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    if args.fonte:
        fontes = [f for f in fontes if f["id"] in set(args.fonte)]
    registrados = ja_registrados(json.loads(ACERVO.read_text(encoding="utf-8")))
    mapa = diplomas_do_inventario()
    candidatos, nao_lidos, fichas = [], [], {}

    for f in fontes:
        alvo = diploma_da_fonte(f, mapa)
        if not alvo:
            continue                      # sem intervalo penal: LEP, CPP, CF, Lei 8.072…
        diploma, faixas = alvo
        arquivos = sorted((Path(args.snapshots) / f["id"]).glob("*.html"))
        if not arquivos:
            nao_lidos.append(f"`{f['id']}`: sem snapshot")
            continue
        original = None
        if not args.sem_rede:
            try:
                original = original_de(f["urn"])
                fichas[f["id"]] = senado.norma_por_urn(f["urn"])
            except (FalhaDeRede, ValueError) as e:
                nao_lidos.append(f"`{f['id']}`: {e}")
        candidatos += levantar_fonte(f, arquivos[-1].read_text(encoding="utf-8"), diploma, faixas,
                                     registrados, original)

    diplomas = []
    if fichas:
        reg = diplomas_ja_registrados(json.loads(DIPLOMAS.read_text(encoding="utf-8")))
        diplomas = revogados_no_todo({k: v for k, v in fichas.items() if v}, reg)
        for d in diplomas:
            try:
                d["penas_no_original"] = penas_do_original_por_codigo(d["codigo"])
            except (FalhaDeRede, ValueError) as e:
                nao_lidos.append(f"{d['nome']}: {e}")

    dia = hoje()
    relatorio = montar_relatorio(candidatos, diplomas, nao_lidos, dia)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"acervo-candidatos-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    (destino / f"acervo-candidatos-{dia.isoformat()}.json").write_text(json.dumps(
        {"candidatos": candidatos, "diplomas": diplomas, "propostas": propostas(candidatos)},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio)
    if not candidatos and not diplomas:
        return 2 if nao_lidos else 0
    return 3 if any(not c["ja_no_acervo"] for c in candidatos) or diplomas else 0


if __name__ == "__main__":
    raise SystemExit(main())
