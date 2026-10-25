# -*- coding: utf-8 -*-
"""O Cotejador, frente 3: o que mudou no ctresb/leis na última semana.

Só observar (decisão 4 do plano de fontes abertas). Três perguntas:

- **O código dele mudou?** Os commits em `scripts/` da janela, para quem
  mantém os robôs saber o que talvez valha a pena trazer (a rede comum, em
  `fontes/rede.py`, veio de lá).
- **O arquivo de um diploma nosso mudou?** Para cada fonte de
  `data/fontes.json`, os commits no arquivo correspondente (`fontes/ctresb.py`
  traduz a URN no caminho). É um terceiro olhar sobre o mesmo texto — e só isso:
  o repositório é operado por agentes e reescreve arquivos em massa.
- **A jurisprudência dele mudou?** Os commits em `jurisprudencia/stf` e
  `jurisprudencia/stj` — súmulas, súmulas vinculantes, controle concentrado,
  repercussão geral —, que ele baixa do mesmo Banco Nacional de Precedentes que
  o Relator lê (`relator/decisoes.py`) e de fontes de cada tribunal. É o segundo
  olhar sobre a decisão de tribunal: o Relator lê o CNJ direto; aqui se vê o que
  um terceiro trouxe de lá e de outros lugares.

Nunca abre issue sozinho, nunca derruba a rodada: sai 0 sempre, e o relatório
entra no corpo da issue quando ela abre por outro motivo.

Uso:
    python scripts/robos/cotejador/ctresb.py              # janela de 8 dias
    python scripts/robos/cotejador/ctresb.py --dias 30
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fontes import ctresb  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
RELATORIOS = RAIZ / "crawler" / "relatorios"
JURISPRUDENCIA = ("jurisprudencia/stf", "jurisprudencia/stj")


def rodar(fontes: list[dict], desde: str, ler=ctresb.commits) -> dict:
    r = {"desde": desde, "scripts": [], "jurisprudencia": {}, "diplomas": [], "nao_lidos": []}
    try:
        r["scripts"] = ler("scripts", desde)
    except (FalhaDeRede, ValueError) as e:
        r["nao_lidos"].append(f"`scripts/`: {e}")
    for pasta in JURISPRUDENCIA:
        try:
            mudancas = ler(pasta, desde)
        except (FalhaDeRede, ValueError) as e:
            r["nao_lidos"].append(f"`{pasta}/`: {e}")
            continue
        if mudancas:
            r["jurisprudencia"][pasta] = mudancas
    for f in fontes:
        caminho = ctresb.caminho_da_urn(f.get("urn") or "")
        if not caminho:
            continue
        try:
            mudancas = ler(caminho, desde)
        except (FalhaDeRede, ValueError) as e:
            r["nao_lidos"].append(f"`{f['id']}`: {e}")
            continue
        if mudancas:
            r["diplomas"].append({"id": f["id"], "caminho": caminho, "commits": mudancas})
    return r


def montar_relatorio(r: dict, dia) -> str:
    L = [f"## ctresb/leis — o que mudou desde {r['desde']} — {dia.isoformat()}", "",
         "> Só observação: o repositório é de terceiro, operado por agentes, e nunca é fonte "
         "de dado do AtlasPen. O que muda no código pode valer a pena trazer; o que muda no "
         "arquivo de um diploma nosso é um terceiro olhar sobre o mesmo texto.", ""]
    juris = sum(len(c) for c in r["jurisprudencia"].values())
    L.append(f"**{len(r['scripts'])}** commit(s) em `scripts/`; **{juris}** na jurisprudência do STF e do "
             f"STJ; **{len(r['diplomas'])}** diploma(s) vigiado(s) com o arquivo alterado.")
    L.append("")
    if r["scripts"]:
        L += ["### Commits em `scripts/`", ""]
        L += [f"- {c.data} [{c.sha[:7]}]({c.url}) — {c.mensagem}" for c in r["scripts"][:15]]
        L.append("")
    if r["jurisprudencia"]:
        L += ["### Commits na jurisprudência", "",
              "> O que ele trouxe de tribunal é pista para o Relator, não decisão lida: a súmula ou o "
              "acórdão entra no catálogo só pelo texto oficial do tribunal.", ""]
        for pasta, commits in r["jurisprudencia"].items():
            L += [f"- {c.data} [{c.sha[:7]}]({c.url}) `{pasta}/` — {c.mensagem}" for c in commits[:10]]
        L.append("")
    if r["diplomas"]:
        L += ["### Diplomas vigiados cujo arquivo mudou", ""]
        for d in r["diplomas"]:
            ultimo = d["commits"][0]
            L.append(f"- `{d['id']}` — [{d['caminho']}](https://github.com/{ctresb.REPO}/blob/main/{d['caminho']})"
                     f": {len(d['commits'])} commit(s), o último em {ultimo.data} — {ultimo.mensagem}")
        L.append("")
    if r["nao_lidos"]:
        L += ["### Não deu para ler", ""] + [f"- {x}" for x in r["nao_lidos"][:20]] + [""]
    return "\n".join(L) + "\n"


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="O que mudou no ctresb/leis na janela.")
    p.add_argument("--dias", type=int, default=8)
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()
    dia = hoje()
    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    r = rodar(fontes, (dia - timedelta(days=args.dias)).isoformat())
    relatorio = montar_relatorio(r, dia)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"cotejo-ctresb-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    print(relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
