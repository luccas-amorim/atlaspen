# -*- coding: utf-8 -*-
"""O Cotejador, frente 1: o compilado anota a lei que o Senado registra?

Toda semana o Vigia baixa os compilados do Planalto e confere o catálogo contra
eles. O que ele não tem como saber é se o próprio compilado está em dia: se o
Planalto demora a incorporar uma lei, o Vigia confere o catálogo contra texto
velho e diz "tudo certo". A sentinela de cada fonte prova frescor só até a lei
que alguém já conhecia.

Este módulo pergunta a uma segunda fonte. Para cada diploma de
`data/fontes.json`, lê no Senado (`fontes/senado.py`, pela `urn`) as alterações
permanentes recentes — lei, lei complementar, emenda, MP — e procura cada uma na
página que o Vigia baixou. O compilado do Planalto anota TODA lei que muda o
texto ("Redação dada pela Lei nº 15.517, de 2026"); se o número não aparece na
página, uma das duas fontes está atrasada ou errada, e quem decide é gente,
abrindo o compilado.

Nada aqui escreve no catálogo nem em `fontes.json` (plano de fontes abertas,
princípio 1). A classificação do Senado erra — ver `fontes/senado.py` —, e por
isso o que sai é pergunta, não correção.

Uso:
    python scripts/robos/cotejador/frescor.py                    # snapshots do Vigia
    python scripts/robos/cotejador/frescor.py --fonte cp --fonte lep
    python scripts/robos/cotejador/frescor.py --snapshots DIR --saida DIR

Saídas: 0 = toda lei recente que o Senado registra está anotada no compilado;
3 = há lei que o compilado não anota, ou diploma que não deu para conferir;
2 = nada pôde ser conferido.
"""
from __future__ import annotations

import argparse
import html as _html
import io
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from endereco_publico import SITE  # noqa: E402
from fontes import senado  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
CATALOGO = RAIZ / "static" / "data" / "crimes.json"
SNAPSHOTS = RAIZ / "crawler" / "snapshots"
RELATORIOS = RAIZ / "crawler" / "relatorios"

# Quanto para trás olhar. Um ano cobre o atraso de qualquer compilação, e não
# reabre a cada semana as alterações de 1984 que o Planalto anota de outro jeito.
JANELA_DIAS = 400

_TAG = re.compile(r"(?s)<[^>]+>")
_ESTILO = re.compile(r"(?is)<(style|script)[^>]*>.*?</\1>")


def texto_plano(html: str) -> str:
    sem = _ESTILO.sub(" ", html or "")
    t = _html.unescape(_TAG.sub(" ", sem)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t)


def _padrao(posterior: senado.Posterior) -> re.Pattern | None:
    """ "Lei nº 15.517" -> casa "Lei nº 15.517", "Lei n° 15517", "LEI Nº 15.517"…

    Inclusive "Lei n º 13.105", com espaço antes do ordinal, que é como o
    compilado da Lei 5.478 anota as revogações pelo CPC de 2015."""
    if not posterior.numero:
        return None
    especie = r"\s+".join(re.escape(p) for p in posterior.especie.split())
    digitos = posterior.numero.replace(".", "")
    numero = r"\.?".join(digitos[i] for i in range(len(digitos)))
    return re.compile(rf"{especie}\s+n\s*[ºo°.]*\s*{numero}(?!\d)", re.I)


def anotada(texto: str, posterior: senado.Posterior) -> bool:
    padrao = _padrao(posterior)
    return bool(padrao and padrao.search(texto))


def chaves_do_catalogo(caminho: Path = CATALOGO) -> dict[str, list[int]]:
    """{chave canônica: [ids]} — a chave é a do histórico (`cp|art. 121, §2º, i`)."""
    if not caminho.exists():
        return {}
    chaves: dict[str, list[int]] = {}
    for c in json.loads(caminho.read_text(encoding="utf-8")):
        if c.get("dispositivo_canonico"):
            chaves.setdefault(c["dispositivo_canonico"], []).append(c["id"])
    return chaves


def ids_tocados(fonte: str, itens: tuple[senado.Item, ...], chaves: dict[str, list[int]]) -> list[int]:
    """Os registros do catálogo cujo dispositivo a lei tocou."""
    ids: set[int] = set()
    for i in itens:
        if not i.unidade:
            continue
        alvo = f"{fonte}|{i.unidade}"
        for chave, lista in chaves.items():
            if chave == alvo or chave.startswith(alvo + ", "):
                ids.update(lista)
    return sorted(ids)


def _abaixo_ou_igual(unidade: str, outra: str) -> bool:
    """`art. 171, §5º, iii` está abaixo de `art. 171, §5º` e de `art. 171`."""
    return unidade == outra or unidade.startswith(outra + ", ")


def superada_por(p: senado.Posterior, posteriores: list[senado.Posterior]) -> str | None:
    """A lei posterior que tocou TODO dispositivo legível de `p`, ou None.

    O compilado anota a redação que vale: quando outra lei reescreve ou revoga
    o mesmo dispositivo, a anotação da anterior pode sumir da página. Foi o caso
    medido em 25/10/2026: a Lei 15.229/2025 incluiu o art. 171, §5º, III, do
    CP, e a Lei 15.397/2026 reescreveu o art. 171 — o compilado cita a segunda,
    não a primeira. Sem esta regra, a semana abriria issue para o que não
    falta.
    """
    minhas = [i.unidade for i in p.itens_vigentes() if i.unidade]
    if not minhas or not p.assinatura:
        return None
    for q in sorted(posteriores, key=lambda x: x.assinatura or date.min, reverse=True):
        if not q.assinatura or q.assinatura <= p.assinatura:
            continue
        delas = [i.unidade for i in q.itens_vigentes() if i.unidade]
        if all(any(_abaixo_ou_igual(u, v) for v in delas) for u in minhas):
            return q.nome
    return None


def cotejar(fonte: dict, norma: senado.Norma | None, texto: str,
            chaves: dict[str, list[int]], dia: date) -> dict:
    """O veredito de um diploma. `texto` é o texto plano do snapshot."""
    r = {"id": fonte["id"], "sentinela": fonte.get("sentinela"), "faltando": [],
         "superadas": [], "ultima": None, "situacao": "confere"}
    if norma is None:
        r["situacao"] = "nao_lido"
        r["motivo"] = "o Senado não devolveu a ficha da URN"
        return r
    alteracoes = norma.alteracoes()
    if not alteracoes:
        r["situacao"] = "sem_registro"
        return r
    ultima = alteracoes[-1]
    r["ultima"] = ultima.nome
    recentes = [p for p in alteracoes if p.assinatura and p.assinatura >= dia - timedelta(days=JANELA_DIAS)]
    if ultima not in recentes:
        recentes.append(ultima)
    for p in recentes:
        if anotada(texto, p):
            continue
        linha = {
            "norma": p.nome,
            "assinatura": p.assinatura.isoformat() if p.assinatura else None,
            "dispositivos": [i.dispositivo for i in p.itens_vigentes()][:12],
            "ids": ids_tocados(fonte["id"], p.itens_vigentes(), chaves),
        }
        posterior = superada_por(p, alteracoes)
        if posterior:
            r["superadas"].append({**linha, "por": posterior})
        else:
            r["faltando"].append(linha)
    if r["faltando"]:
        r["situacao"] = "planalto_nao_anota"
    return r


def snapshot_mais_recente(pasta: Path, fonte: str) -> Path | None:
    arquivos = sorted((pasta / fonte).glob("*.html"))
    return arquivos[-1] if arquivos else None


def rodar(fontes: list[dict], snapshots: Path, dia: date, ler=senado.norma_por_urn,
          chaves: dict[str, list[int]] | None = None) -> list[dict]:
    chaves = chaves if chaves is not None else chaves_do_catalogo()
    vereditos = []
    for f in fontes:
        arquivo = snapshot_mais_recente(snapshots, f["id"])
        if arquivo is None:
            vereditos.append({"id": f["id"], "situacao": "nao_lido", "faltando": [],
                              "motivo": "sem snapshot do Planalto nesta rodada"})
            continue
        if not f.get("urn"):
            vereditos.append({"id": f["id"], "situacao": "nao_lido", "faltando": [],
                              "motivo": "sem `urn` em data/fontes.json"})
            continue
        try:
            norma = ler(f["urn"])
        except FalhaDeRede as e:
            vereditos.append({"id": f["id"], "situacao": "nao_lido", "faltando": [],
                              "motivo": f"o Senado não respondeu: {e}"})
            continue
        except ValueError as e:              # JSON que chegou ilegível
            vereditos.append({"id": f["id"], "situacao": "nao_lido", "faltando": [],
                              "motivo": f"a ficha do Senado veio ilegível: {e}"})
            continue
        texto = texto_plano(arquivo.read_text(encoding="utf-8"))
        vereditos.append(cotejar(f, norma, texto, chaves, dia))
    return vereditos


def codigo_de_saida(vereditos: list[dict]) -> int:
    if vereditos and all(v["situacao"] == "nao_lido" for v in vereditos):
        return 2
    if any(v["situacao"] in ("planalto_nao_anota", "nao_lido") for v in vereditos):
        return 3
    return 0


def montar_relatorio(vereditos: list[dict], dia: date) -> str:
    por = {s: [v for v in vereditos if v["situacao"] == s]
           for s in ("confere", "planalto_nao_anota", "sem_registro", "nao_lido")}
    L = [f"## Cotejo com o Senado — o compilado anota as leis recentes? — {dia.isoformat()}", "",
         f"De **{len(vereditos)}** diplomas: **{len(por['confere'])}** com toda lei recente "
         f"que o Senado registra anotada no compilado; **{len(por['planalto_nao_anota'])}** "
         f"com lei que o compilado não anota; **{len(por['sem_registro'])}** sem alteração "
         f"registrada no Senado; **{len(por['nao_lido'])}** que não deu para conferir.", "",
         "> O Senado aponta, não decide: a classificação dele erra (registra como "
         "\"alteração\" revogações do CP), e a data é a de assinatura. Cada linha abaixo "
         "é uma pergunta — abra o compilado e veja se a lei está lá.", ""]

    if por["planalto_nao_anota"]:
        L += ["### O Senado registra, e a página baixada do Planalto não cita", ""]
        ordem = sorted(por["planalto_nao_anota"],
                       key=lambda v: (-sum(len(f["ids"]) for f in v["faltando"]), v["id"]))
        for v in ordem:
            for f in v["faltando"]:
                tocados = (f" — **toca {len(f['ids'])} registro(s) do catálogo**: "
                           + ", ".join(f"[{i}]({SITE}/tipos/{i})" for i in f["ids"][:10])
                           if f["ids"] else "")
                L.append(f"- `{v['id']}` — **{f['norma']}**{tocados}")
                if f["dispositivos"]:
                    L.append("  - dispositivos, como o Senado os escreve: "
                             + "; ".join(f["dispositivos"]))
        L.append("")

    superadas = [(v["id"], s) for v in vereditos for s in v.get("superadas") or []]
    if superadas:
        L += ["### Provavelmente superadas — o Senado registra lei posterior no mesmo dispositivo", "",
              "> O compilado anota a redação que vale: quando outra lei reescreve ou revoga o "
              "dispositivo, a anotação da anterior pode sumir. Estas não abrem issue sozinhas; "
              "ficam aqui para quem quiser conferir.", ""]
        L += [f"- `{fid}` — {s['norma']}, superada por {s['por']}" for fid, s in superadas]
        L.append("")

    if por["nao_lido"]:
        L += ["### Não deu para conferir", ""]
        L += [f"- `{v['id']}` — {v.get('motivo', '')}" for v in por["nao_lido"]]
        L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="O compilado anota as leis que o Senado registra?")
    p.add_argument("--fonte", action="append", default=[], metavar="ID")
    p.add_argument("--snapshots", default=str(SNAPSHOTS))
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()

    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    if args.fonte:
        fontes = [f for f in fontes if f["id"] in set(args.fonte)]
    dia = hoje()
    vereditos = rodar(fontes, Path(args.snapshots), dia)
    relatorio = montar_relatorio(vereditos, dia)

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"cotejo-frescor-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    (destino / f"cotejo-frescor-{dia.isoformat()}.json").write_text(
        json.dumps(vereditos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio)
    return codigo_de_saida(vereditos)


if __name__ == "__main__":
    raise SystemExit(main())
