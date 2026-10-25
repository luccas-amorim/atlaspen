# -*- coding: utf-8 -*-
"""O Cotejador, frente 5: o histórico legislativo contra o registro do Senado.

`data/historico-legislativo.json` é lido do compilado do Planalto
(`nucleo/historico.py`): cada evento é uma anotação — "(Redação dada pela Lei
nº 15.402, de 2026)" — num dispositivo. O Senado registra a mesma coisa vista
do outro lado: que dispositivos cada lei posterior tocou. Este módulo cruza os
dois, nos dois sentidos:

- **o Senado não registra** — o histórico diz que a Lei X mexeu no dispositivo
  D, e o Senado não tem a Lei X neste diploma, ou a tem noutro dispositivo. Ou
  o Senado está incompleto (é comum em leis antigas), ou a anotação foi lida
  no lugar errado;
- **o histórico não registra** — o Senado diz que a Lei X tocou D, que o
  histórico acompanha, e o histórico não tem evento da Lei X ali. O compilado
  anota a redação que vale: quando outra lei reescreve o dispositivo, a anotação
  da anterior pode sumir da página, e o evento some com ela.

Nada se corrige daqui: o Senado classifica mal (ver `fontes/senado.py`), e o
histórico só registra o que o compilado anota. Cada linha é pergunta. Roda sob
demanda, não na rodada semanal: o histórico muda pouco.

Uso:
    python scripts/robos/cotejador/historico.py --fonte lep --fonte cp
    python scripts/robos/cotejador/historico.py             # todas as fontes do histórico

Saídas: 0 = nada a cruzar de diferente; 3 = há o que ler; 2 = nada lido.
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

from cotejador.frescor import _abaixo_ou_igual  # noqa: E402
from fontes import senado  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
HISTORICO = RAIZ / "data" / "historico-legislativo.json"
RELATORIOS = RAIZ / "crawler" / "relatorios"

_NORMA = re.compile(r"^(Lei Complementar|Lei|Decreto-Lei|Emenda Constitucional|Medida Provisória)"
                    r"\s+n[ºo°]\s*([\d.]+)", re.I)


def chave_da_norma(texto: str) -> tuple[str, str] | None:
    """ "Lei nº 15.402" -> ("lei", "15402") — a mesma chave dos dois lados."""
    m = _NORMA.match((texto or "").strip())
    return (m.group(1).lower(), m.group(2).replace(".", "")) if m else None


def _sem_caput(unidade: str) -> str:
    return unidade[:-len(", caput")] if unidade.endswith(", caput") else unidade


def _parentes(a: str, b: str) -> bool:
    a, b = _sem_caput(a), _sem_caput(b)
    return _abaixo_ou_igual(a, b) or _abaixo_ou_igual(b, a)


def indice_do_senado(ficha: senado.Norma) -> dict[tuple[str, str], list[str]]:
    """{(espécie, número): [unidades legíveis]} das alterações permanentes."""
    indice: dict[tuple[str, str], list[str]] = {}
    for p in ficha.alteracoes():
        chave = chave_da_norma(p.nome)
        if chave:
            indice.setdefault(chave, []).extend(i.unidade for i in p.itens_vigentes() if i.unidade)
    return indice


def cruzar(fonte: str, eventos: list[dict], ficha: senado.Norma) -> dict:
    indice = indice_do_senado(ficha)
    meus = [e for e in eventos if e["dispositivo"].startswith(fonte + "|") and chave_da_norma(e.get("norma"))]
    acompanhados = sorted({e["dispositivo"].split("|", 1)[1] for e in eventos
                           if e["dispositivo"].startswith(fonte + "|")})
    senado_nao, historico_nao = [], []

    for e in meus:
        chave = chave_da_norma(e["norma"])
        unidade = e["dispositivo"].split("|", 1)[1]
        unidades = indice.get(chave)
        if unidades is None:
            senado_nao.append({"dispositivo": e["dispositivo"], "norma": e["norma"],
                               "motivo": "o Senado não tem esta lei neste diploma"})
        elif unidades and not any(_parentes(unidade, u) for u in unidades):
            senado_nao.append({"dispositivo": e["dispositivo"], "norma": e["norma"],
                               "motivo": "o Senado tem a lei, noutro dispositivo"})

    por_norma: dict[tuple[str, str], list[str]] = {}
    for e in meus:
        por_norma.setdefault(chave_da_norma(e["norma"]), []).append(e["dispositivo"].split("|", 1)[1])
    alteracoes = ficha.alteracoes()
    for i, p in enumerate(alteracoes):
        chave = chave_da_norma(p.nome)
        if not chave:
            continue
        depois = [u for q in alteracoes[i + 1:] if q.assinatura and p.assinatura and q.assinatura > p.assinatura
                  for u in (it.unidade for it in q.itens_vigentes()) if u]
        for u in (it.unidade for it in p.itens_vigentes()):
            if not u or not any(_parentes(a, u) for a in acompanhados):
                continue                          # o histórico não acompanha este dispositivo
            if any(_parentes(u, x) for x in por_norma.get(chave, [])):
                continue
            # Superada: lei posterior tocou o mesmo dispositivo, e o compilado,
            # que anota a redação que vale, pode ter trocado a anotação.
            if any(_parentes(u, d) for d in depois):
                continue
            historico_nao.append({"dispositivo": f"{fonte}|{u}", "norma": p.nome})
    return {"fonte": fonte, "senado_nao_registra": senado_nao, "historico_nao_registra": historico_nao}


def montar_relatorio(cruzamentos: list[dict], nao_lidos: list[str], dia) -> str:
    sn = sum(len(c["senado_nao_registra"]) for c in cruzamentos)
    hn = sum(len(c["historico_nao_registra"]) for c in cruzamentos)
    L = [f"## Histórico legislativo contra o Senado — {dia.isoformat()}", "",
         f"**{len(cruzamentos)}** diploma(s) cruzados: **{sn}** evento(s) do histórico que o Senado não "
         f"registra; **{hn}** alteração(ões) do Senado em dispositivo acompanhado sem evento no histórico.", "",
         "> Cada linha é pergunta. O Senado é incompleto em leis antigas e classifica mal; o histórico "
         "só tem o que o compilado anota, e a anotação some quando outra lei reescreve o dispositivo.", ""]
    for c in cruzamentos:
        if not (c["senado_nao_registra"] or c["historico_nao_registra"]):
            continue
        L += [f"### `{c['fonte']}`", ""]
        for x in c["historico_nao_registra"][:20]:
            L.append(f"- histórico não registra: `{x['dispositivo']}` — {x['norma']}")
        for x in c["senado_nao_registra"][:20]:
            L.append(f"- Senado não registra: `{x['dispositivo']}` — {x['norma']} ({x['motivo']})")
        L.append("")
    if nao_lidos:
        L += ["### Não deu para ler", ""] + [f"- {x}" for x in nao_lidos] + [""]
    return "\n".join(L) + "\n"


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="O histórico legislativo contra o registro do Senado.")
    p.add_argument("--fonte", action="append", default=[], metavar="ID")
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()

    eventos = json.loads(HISTORICO.read_text(encoding="utf-8"))["eventos"]
    no_historico = {e["dispositivo"].split("|", 1)[0] for e in eventos}
    fontes = [f for f in json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
              if f["id"] in no_historico and (not args.fonte or f["id"] in set(args.fonte))]
    cruzamentos, nao_lidos = [], []
    for f in fontes:
        try:
            ficha = senado.norma_por_urn(f["urn"])
        except (FalhaDeRede, ValueError) as e:
            nao_lidos.append(f"`{f['id']}`: {e}")
            continue
        if ficha is None:
            nao_lidos.append(f"`{f['id']}`: sem ficha no Senado")
            continue
        cruzamentos.append(cruzar(f["id"], eventos, ficha))
    dia = hoje()
    relatorio = montar_relatorio(cruzamentos, nao_lidos, dia)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"cotejo-historico-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    print(relatorio)
    if not cruzamentos:
        return 2
    return 3 if any(c["senado_nao_registra"] or c["historico_nao_registra"] for c in cruzamentos) else 0


if __name__ == "__main__":
    raise SystemExit(main())
