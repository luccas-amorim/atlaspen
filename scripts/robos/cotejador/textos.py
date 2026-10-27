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

A divergência já julgada — a Câmara atrasada numa lei que o Planalto anota —
vai para `excecoes-textos.json` e sai da conta, mas não do relatório. Ela casa
pelas duas molduras como o relatório as escreve: quando uma das compilações
muda, deixa de casar e o relatório manda retirá-la.

Saídas: 0 = as molduras conferem; 3 = há divergência, diploma não lido ou
exceção sem efeito; 2 = nada pôde ser lido.
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
EXCECOES = Path(__file__).resolve().parent / "excecoes-textos.json"


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


# ── As exceções julgadas ────────────────────────────────────────────────────
def carregar_excecoes(caminho: Path = EXCECOES) -> list[dict]:
    if not caminho.exists():
        return []
    return json.loads(caminho.read_text(encoding="utf-8")).get("excecoes") or []


def _excecao_de(fonte: str, d: dict, excecoes: list[dict]) -> dict | None:
    for e in excecoes:
        if (e.get("fonte") == fonte and e.get("dispositivo") == d["dispositivo"]
                and e.get("planalto") == _moldura_humana(d["planalto"])
                and e.get("camara") == _moldura_humana(d["camara"])):
            return e
    return None


def separar_julgadas(fonte: str, comparacao: dict, excecoes: list[dict]) -> dict:
    """Tira das divergências as que casam com exceção julgada, e as guarda à parte."""
    abertas, julgadas = [], []
    for d in comparacao["divergentes"]:
        e = _excecao_de(fonte, d, excecoes)
        if e:
            julgadas.append({**d, "motivo": e.get("motivo"), "data": e.get("data")})
        else:
            abertas.append(d)
    return {**comparacao, "divergentes": abertas, "julgadas": julgadas}


def excecoes_sem_efeito(vereditos: list[dict], excecoes: list[dict]) -> list[dict]:
    """As exceções de um diploma lido que não casaram com nenhuma divergência.

    A Câmara atualizou a compilação, ou o Planalto mudou: a exceção já não
    descreve o que as páginas dizem, e calaria o próximo caso parecido."""
    lidos = {v["id"]: v for v in vereditos if "comparacao" in v}
    saida = []
    for e in excecoes:
        v = lidos.get(e.get("fonte"))
        if v is None:
            continue
        if not any(j["dispositivo"] == e.get("dispositivo") for j in v["comparacao"].get("julgadas", [])):
            saida.append(e)
    return saida


def montar_relatorio(vereditos: list[dict], dia, sem_efeito: list[dict] | None = None) -> str:
    lidos = [v for v in vereditos if "comparacao" in v]
    div = [v for v in lidos if v["comparacao"]["divergentes"]]
    total = sum(v["comparacao"]["conferem"] for v in lidos)
    so_pl = sum(v["comparacao"]["so_planalto"] for v in lidos)
    so_cd = sum(v["comparacao"]["so_camara"] for v in lidos)
    julgadas = [(v["id"], j) for v in lidos for j in v["comparacao"].get("julgadas", [])]
    L = [f"## Cotejo de textos — a moldura do Planalto e a da Câmara — {dia.isoformat()}", "",
         f"**{len(lidos)}** diplomas lidos nas duas compilações; **{total}** molduras conferem; "
         f"**{sum(len(v['comparacao']['divergentes']) for v in div)}** divergem, em "
         f"**{len(div)}** diploma(s)"
         + (f", e **{len(julgadas)}** divergência(s) já julgada(s)" if julgadas else "")
         + f". Fora da comparação, porque só uma das páginas tem o "
         f"dispositivo com pena legível: **{so_pl}** só no Planalto, **{so_cd}** só na Câmara.", "",
         "> As duas compilações valem igual — nenhuma é o DOU —, e o catálogo segue o Planalto. "
         "Divergência é pergunta: abra as duas páginas no dispositivo e veja qual está em dia.", ""]
    for v in div:
        L += [f"### `{v['id']}` — {len(v['comparacao']['divergentes'])} divergência(s)", ""]
        for d in v["comparacao"]["divergentes"][:25]:
            L.append(f"- {d['dispositivo']}: Planalto **{_moldura_humana(d['planalto'])}**; "
                     f"Câmara **{_moldura_humana(d['camara'])}**")
        L.append("")
    if julgadas:
        L += [f"### Já julgadas — {len(julgadas)}", "",
              "> Divergências cujo motivo já foi lido no texto da lei alteradora "
              "(`scripts/robos/cotejador/excecoes-textos.json`). Ficam visíveis: uma dispensa "
              "que ninguém vê é indistinguível de um achado que nunca apareceu.", ""]
        L += [f"- `{fid}` — {j['dispositivo']}: Planalto **{_moldura_humana(j['planalto'])}**; "
              f"Câmara **{_moldura_humana(j['camara'])}**. {j['motivo']}" for fid, j in julgadas]
        L.append("")
    if sem_efeito:
        L += ["### Exceções sem efeito — retirar de `excecoes-textos.json`", "",
              "> A divergência julgada não aparece mais como foi escrita: uma das compilações mudou.", ""]
        L += [f"- `{e.get('fonte')}` — {e.get('dispositivo')} (julgada em {e.get('data')})" for e in sem_efeito]
        L.append("")
    nao = [v for v in vereditos if "motivo" in v]
    if nao:
        L += ["### Não deu para cotejar", ""] + [f"- `{v['id']}` — {v['motivo']}" for v in nao] + [""]
    return "\n".join(L) + "\n"


def codigo_de_saida(vereditos: list[dict], sem_efeito: list[dict] | None = None) -> int:
    if vereditos and all("motivo" in v for v in vereditos):
        return 2
    if any("motivo" in v or v["comparacao"]["divergentes"] for v in vereditos) or sem_efeito:
        return 3
    return 0


def rodar(fontes: list[dict], snapshots: Path, ler_camara=None,
          excecoes: list[dict] | None = None) -> list[dict]:
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
        comparacao = comparar(planalto, molduras(html))
        vereditos.append({"id": f["id"], "comparacao": separar_julgadas(f["id"], comparacao, excecoes or [])})
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
    excecoes = carregar_excecoes()
    vereditos = rodar(fontes, Path(args.snapshots), excecoes=excecoes)
    sem_efeito = excecoes_sem_efeito(vereditos, excecoes)
    relatorio = montar_relatorio(vereditos, dia, sem_efeito)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"cotejo-textos-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    (destino / f"cotejo-textos-{dia.isoformat()}.json").write_text(
        json.dumps(vereditos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio)
    return codigo_de_saida(vereditos, sem_efeito)


if __name__ == "__main__":
    raise SystemExit(main())
