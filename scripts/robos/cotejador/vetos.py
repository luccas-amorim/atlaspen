# -*- coding: utf-8 -*-
"""O Cotejador, frente 4: vetos do ano a leis que mexem nos diplomas vigiados.

Um veto derrubado muda o texto da lei semanas ou meses depois da sanção: o
dispositivo que o compilado marcava "(VETADO)" passa a valer. A fixture
`abuso-art9-veto-derrubado.html` existe porque isso já aconteceu com a Lei de
Abuso de Autoridade. A lista de vetos do Senado (`fontes/senado.py`) diz quais
vetos do ano ainda tramitam — os que ainda podem cair — e de que matéria são;
este módulo separa os que tocam diploma de `data/fontes.json`, pela ementa.

Só informa: nunca abre issue sozinho e sai 0. Quando um veto cai, a
promulgação das partes vetadas é anotada no compilado, e o Cotejador de frescor
e o Vigia a veem como qualquer lei.

Uso:
    python scripts/robos/cotejador/vetos.py               # ano corrente
    python scripts/robos/cotejador/vetos.py --ano 2025
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

from fontes import senado  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
RELATORIOS = RAIZ / "crawler" / "relatorios"

_ESPECIE = {"lei": r"(?<!Decreto-)(?<!Decreto )Lei", "decreto.lei": r"Decreto-Lei",
            "lei.complementar": r"Lei\s+Complementar"}


def _milhar(numero: str) -> str:
    n = int(numero)
    return f"{n // 1000}.{n % 1000:03d}" if n >= 1000 else str(n)


def padroes(fontes: list[dict]) -> dict[str, re.Pattern]:
    """{id da fonte: padrão que casa a citação do diploma numa ementa}."""
    saida = {}
    for f in fontes:
        partes = (f.get("urn") or "").split(":")
        if len(partes) != 6:
            continue
        especie, numero = partes[4], partes[5].split(";")[-1]
        if especie == "constituicao":
            saida[f["id"]] = re.compile(r"Constituição\s+Federal", re.I)
        elif especie in _ESPECIE:
            saida[f["id"]] = re.compile(rf"{_ESPECIE[especie]}\s+n[ºo°]\s*{re.escape(_milhar(numero))}(?!\d)")
    return saida


def vetos_que_tocam(vetos: list[senado.Veto], pads: dict[str, re.Pattern]) -> list[dict]:
    saida = []
    for v in vetos:
        tocados = sorted(fid for fid, p in pads.items() if p.search(v.ementa))
        if tocados:
            saida.append({"veto": v, "fontes": tocados})
    return saida


def montar_relatorio(ano: int, achados: list[dict], erro: str | None, dia) -> str:
    L = [f"## Vetos de {ano} a leis que mexem nos diplomas vigiados — {dia.isoformat()}", ""]
    if erro:
        return "\n".join(L + [f"> A lista de vetos do Senado não pôde ser lida: {erro}", ""]) + "\n"
    abertos = [a for a in achados if a["veto"].em_tramitacao]
    fechados = [a for a in achados if not a["veto"].em_tramitacao]
    L += [f"**{len(abertos)}** em tramitação (ainda podem ser derrubados e mudar o texto); "
          f"**{len(fechados)}** encerrados.", ""]
    for titulo, grupo in (("Em tramitação", abertos), ("Encerrados", fechados)):
        if not grupo:
            continue
        L += [f"### {titulo}", ""]
        for a in grupo:
            v = a["veto"]
            mensagem = f" — [mensagem]({v.url_mensagem})" if v.url_mensagem else ""
            L.append(f"- **VET {v.numero}** ({'total' if v.total else 'parcial'}) — {v.assunto or v.ementa[:90]}"
                     f" — toca {', '.join(f'`{x}`' for x in a['fontes'])}{mensagem}")
        L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Vetos do ano a leis que mexem nos diplomas vigiados.")
    p.add_argument("--ano", type=int, default=hoje().year)
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()
    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    erro, achados = None, []
    try:
        achados = vetos_que_tocam(senado.vetos_do_ano(args.ano), padroes(fontes))
    except (FalhaDeRede, ValueError) as e:
        erro = str(e)
    dia = hoje()
    relatorio = montar_relatorio(args.ano, achados, erro, dia)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"cotejo-vetos-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    print(relatorio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
