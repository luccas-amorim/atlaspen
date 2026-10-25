# -*- coding: utf-8 -*-
"""O Cotejador, frente 2: a moldura do Planalto é a mesma da compilação da Câmara?

O normas.leg.br serve, de cada norma, a compilação vigente que a Câmara mantém
(`fontes/normas.py`, versão `Current`). É uma segunda compilação, feita por
outra equipe, do mesmo texto legal — e o `nucleo/parsear.py` lê as duas: medido
em 25/10/2026, o CP sai com os mesmos 904 dispositivos de um lado e do outro.

Para cada diploma, este módulo lê a pena de cada dispositivo nas duas páginas,
com o MESMO `pena_parser` que o catálogo usa, e compara espécie, mínimo e
máximo. Onde discordam, uma das duas compilações está errada ou atrasada — e
quem decide é gente, abrindo o texto: as duas valem igual (nenhuma é o DOU), e
o catálogo segue o Planalto (plano de fontes abertas, princípio 1).

Uso:
    python scripts/robos/cotejador/textos.py                  # snapshots do Vigia
    python scripts/robos/cotejador/textos.py --fonte cp --fonte lcp

Saídas: 0 = as molduras conferem; 3 = há divergência ou diploma não lido;
2 = nada pôde ser lido.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fontes import normas  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.parsear import como_dicionarios, parsear  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402
from pena_parser import ler_pena  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
SNAPSHOTS = RAIZ / "crawler" / "snapshots"
RELATORIOS = RAIZ / "crawler" / "relatorios"


def molduras(documento: str) -> dict[str, dict]:
    """{"Art. 121|caput": moldura} dos dispositivos VIGENTES com pena legível."""
    saida = {}
    for d in como_dicionarios(parsear(documento)):
        if d.get("situacao") == "revogado" or d.get("citacao") or not d.get("pena_texto"):
            continue
        m = ler_pena(d["pena_texto"])
        if m:
            saida[f"{d['artigo']}|{d['marcador']}"] = {
                "tipo": m.get("tipo"), "min": m.get("min_meses"), "max": m.get("max_meses"),
                "so_multa": m.get("so_multa", False), "texto": d["pena_texto"][:200]}
    return saida


def _igual(a: dict, b: dict) -> bool:
    return (a["tipo"], a["min"], a["max"], a["so_multa"]) == (b["tipo"], b["min"], b["max"], b["so_multa"])


def comparar(planalto: dict[str, dict], camara: dict[str, dict]) -> dict:
    comuns = sorted(set(planalto) & set(camara))
    return {
        "conferem": sum(1 for k in comuns if _igual(planalto[k], camara[k])),
        "divergentes": [{"dispositivo": k.replace("|", ", "), "planalto": planalto[k], "camara": camara[k]}
                        for k in comuns if not _igual(planalto[k], camara[k])],
        "so_planalto": len(set(planalto) - set(camara)),
        "so_camara": len(set(camara) - set(planalto)),
    }


def _moldura_humana(m: dict) -> str:
    if m["so_multa"]:
        return "só multa"
    return f"{m['tipo']}, {m['min']:g} a {m['max']:g} meses"


def montar_relatorio(vereditos: list[dict], dia) -> str:
    lidos = [v for v in vereditos if "comparacao" in v]
    div = [v for v in lidos if v["comparacao"]["divergentes"]]
    total = sum(v["comparacao"]["conferem"] for v in lidos)
    so_pl = sum(v["comparacao"]["so_planalto"] for v in lidos)
    so_cd = sum(v["comparacao"]["so_camara"] for v in lidos)
    L = [f"## Cotejo de textos — a moldura do Planalto e a da Câmara — {dia.isoformat()}", "",
         f"**{len(lidos)}** diplomas lidos nas duas compilações; **{total}** molduras conferem; "
         f"**{sum(len(v['comparacao']['divergentes']) for v in div)}** divergem, em "
         f"**{len(div)}** diploma(s). Fora da comparação, porque só uma das páginas tem o "
         f"dispositivo com pena legível: **{so_pl}** só no Planalto, **{so_cd}** só na Câmara.", "",
         "> As duas compilações valem igual — nenhuma é o DOU —, e o catálogo segue o Planalto. "
         "Divergência é pergunta: abra as duas páginas no dispositivo e veja qual está em dia.", ""]
    for v in div:
        L += [f"### `{v['id']}` — {len(v['comparacao']['divergentes'])} divergência(s)", ""]
        for d in v["comparacao"]["divergentes"][:25]:
            L.append(f"- {d['dispositivo']}: Planalto **{_moldura_humana(d['planalto'])}**; "
                     f"Câmara **{_moldura_humana(d['camara'])}**")
        L.append("")
    nao = [v for v in vereditos if "motivo" in v]
    if nao:
        L += ["### Não deu para cotejar", ""] + [f"- `{v['id']}` — {v['motivo']}" for v in nao] + [""]
    return "\n".join(L) + "\n"


def codigo_de_saida(vereditos: list[dict]) -> int:
    if vereditos and all("motivo" in v for v in vereditos):
        return 2
    if any("motivo" in v or v["comparacao"]["divergentes"] for v in vereditos):
        return 3
    return 0


def rodar(fontes: list[dict], snapshots: Path, ler_camara=None) -> list[dict]:
    def camara_padrao(urn):
        f = normas.ficha(urn)
        v = f.versao("Current") if f else None
        return normas.texto(v) if v else None
    ler_camara = ler_camara or camara_padrao
    vereditos = []
    for f in fontes:
        arquivos = sorted((snapshots / f["id"]).glob("*.html"))
        if not arquivos or not f.get("urn"):
            vereditos.append({"id": f["id"], "motivo": "sem snapshot do Planalto ou sem `urn`"})
            continue
        planalto = molduras(arquivos[-1].read_text(encoding="utf-8"))
        if not planalto:
            continue                       # diploma sem pena (LEP, CF): nada a cotejar
        try:
            html = ler_camara(f["urn"])
        except (FalhaDeRede, ValueError) as e:
            vereditos.append({"id": f["id"], "motivo": f"o normas.leg.br não respondeu: {e}"})
            continue
        if not html:
            vereditos.append({"id": f["id"], "motivo": "o normas.leg.br não tem a compilação vigente"})
            continue
        vereditos.append({"id": f["id"], "comparacao": comparar(planalto, molduras(html))})
    return vereditos


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="A moldura do Planalto é a da compilação da Câmara?")
    p.add_argument("--fonte", action="append", default=[], metavar="ID")
    p.add_argument("--snapshots", default=str(SNAPSHOTS))
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()

    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    if args.fonte:
        fontes = [f for f in fontes if f["id"] in set(args.fonte)]
    dia = hoje()
    vereditos = rodar(fontes, Path(args.snapshots))
    relatorio = montar_relatorio(vereditos, dia)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"cotejo-textos-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    (destino / f"cotejo-textos-{dia.isoformat()}.json").write_text(
        json.dumps(vereditos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio)
    return codigo_de_saida(vereditos)


if __name__ == "__main__":
    raise SystemExit(main())
