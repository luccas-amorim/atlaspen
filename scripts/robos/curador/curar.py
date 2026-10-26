# -*- coding: utf-8 -*-
"""O Curador: a lei penal antiga que o projeto nunca leu, e a que morreu sem aviso.

Três passos, com estado em `data/curadoria.json` (plano em
`.superpowers/planos/2026-10-26-curador.md`):

1. **Triagem no ctresb/leis** (`curador/varrer.py`): toda lei ordinária,
   decreto-lei e lei complementar desde 1889, relida só onde o ctresb mudou.
2. **Confirmação no Planalto** (`curador/confirmar.py`): cada lei apontada, uma
   vez, e de novo a cada `RECONFERIR_DIAS` — é assim que a revogação nova aparece.
3. **Completude** contra o Senado: quantas normas ele lista por ano, e quantas o
   ctresb tem. O que o ctresb não tem o Curador não triou, e o relatório diz.

Uso:
    python scripts/robos/curador/curar.py                     # a rodada mensal
    python scripts/robos/curador/curar.py --orcamento 3000    # a varredura única
    python scripts/robos/curador/curar.py --sem-planalto      # só a triagem
    python scripts/robos/curador/curar.py --estado ARQ --saida DIR

Saídas: 0 = nada novo; 3 = há o que ler; 2 = não deu para ler o ctresb.
NADA daqui escreve no catálogo, no acervo nem em `data/fontes.json`.
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

from curador import confirmar, triagem, varrer  # noqa: E402
from endereco_publico import SITE  # noqa: E402,F401
from fontes import ctresb, senado  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

DATA = RAIZ / "data"
ESTADO = DATA / "curadoria.json"
RELATORIOS = RAIZ / "crawler" / "relatorios"
RECONFERIR_DIAS = 180
ORCAMENTO = 300             # leis confirmadas no Planalto por rodada mensal
A_MOSTRAR = 40              # por seção, no corpo da issue
LEITURA = ("pena_vigente", "revogada", "pena_riscada", "sem_pagina")
# O Código Penal entrou em vigor em 1º/01/1942, com a LCP. A lei anterior com
# pena no texto e sem revogação anunciada pode ter sido revogada tacitamente — e
# o Planalto não anuncia a revogação tácita.
ANO_DO_CP = 1942
# A lei que altera um diploma que o projeto já vigia traz, na página antiga do
# Planalto, o texto novo SEM aspas curvas — a Lei 6.416/77 ("Altera dispositivos
# do Código Penal") saiu como pena vigente na primeira varredura.
_ALTERA = re.compile(r"^\s*(?:altera|acrescenta|acresce|d[áa]\s+nova\s+reda[çc][ãa]o|introduz\s+altera|"
                     r"modifica|revoga|inclui|insere)", re.I)
_SENADO = {"lei": "LEI", "del": "DEL", "lcp": "LCP"}
# Os decretos com força de lei dos governos provisórios, que o ctresb não tem.
GOVERNOS_PROVISORIOS = list(range(1889, 1892)) + list(range(1930, 1935))

META = {
    "descricao": "O estado do Curador (scripts/robos/curador/): o que ele já triou no ctresb/leis e o que o "
                 "Planalto disse de cada lei apontada. Escrito pela rodada, não à mão.",
    "anos": "Por espécie e ano: o sha da árvore do git no ctresb (igual ao da rodada anterior, o ano não é "
            "relido), quantos arquivos, quantos com pena própria e quantos só com pena citada entre aspas.",
    "apontadas": "Cada lei com pena própria que o projeto não conhecia: o que o ctresb diz e, em `planalto`, o "
                 "que o compilado oficial disse e quando. É lista de leitura, não dado do catálogo.",
    "senado": "Quantas normas a API do Senado lista por espécie e ano — a régua da completude do ctresb.",
}


def carregar(caminho: Path) -> dict:
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {"_meta": META}


def gravar(estado: dict, caminho: Path) -> None:
    estado["_meta"] = META
    caminho.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                       encoding="utf-8")


def a_confirmar(estado: dict, dia: date, orcamento: int) -> list[str]:
    """As nunca confirmadas primeiro; depois, as de conferência mais antiga que
    `RECONFERIR_DIAS`."""
    limite = (dia - timedelta(days=RECONFERIR_DIAS)).isoformat()
    novas, velhas = [], []
    for c, a in sorted((estado.get("apontadas") or {}).items()):
        p = a.get("planalto")
        if not p:
            novas.append(c)
        elif p.get("conferido_em", "") < limite:
            velhas.append((p.get("conferido_em", ""), c))
    return (novas + [c for _, c in sorted(velhas)])[:orcamento]


def rodar_confirmacoes(estado: dict, chaves: list[str], dia: date, conf=confirmar.confirmar
                       ) -> tuple[list[str], list[str], list[str]]:
    """(as confirmadas pela primeira vez, as que mudaram de estado, os avisos).
    Planalto fora do ar não vira estado."""
    primeiras, mudaram, avisos, quedas = [], [], [], 0
    for c in chaves:
        registro = estado["apontadas"][c]
        antes = (registro.get("planalto") or {}).get("estado")
        try:
            registro["planalto"] = conf(c, dia=dia)
        except FalhaDeRede as e:
            quedas += 1
            avisos.append(f"`{c}`: o Planalto não respondeu ({e})")
            if quedas >= 5:
                avisos.append("cinco quedas seguidas: o Planalto saiu do ar, e o resto fica para a próxima rodada")
                break
            continue
        quedas = 0
        if not antes:
            primeiras.append(c)
        elif antes != registro["planalto"]["estado"]:
            mudaram.append(c)
    return primeiras, mudaram, avisos


def marcar_alteradoras(estado: dict, conhecidos: dict[str, str]) -> None:
    """`altera`: os diplomas conhecidos que a ementa diz alterar."""
    for a in (estado.get("apontadas") or {}).values():
        alvos = sorted(triagem.chaves_da_norma(a.get("ementa") or "") & set(conhecidos))
        if _ALTERA.search(a.get("ementa") or "") and alvos:
            a["altera"] = alvos
        else:
            a.pop("altera", None)


def contar_senado(estado: dict, avisos: list[str]) -> None:
    """Uma vez por ano e espécie: o passado não muda de tamanho."""
    alvo = estado.setdefault("senado", {})
    pedidos = [(e, a) for e in _SENADO for a in sorted((estado.get("anos") or {}).get(e) or {})]
    pedidos += [("dec", str(a)) for a in GOVERNOS_PROVISORIOS]
    for especie, ano in pedidos:
        if ano in alvo.get(especie, {}):
            continue
        try:
            n = len(senado.leis_do_ano(int(ano), _SENADO.get(especie, "DEC")))
        except (FalhaDeRede, ValueError) as e:
            avisos.append(f"o Senado não deu a contagem de {especie} {ano}: {e}")
            continue
        alvo.setdefault(especie, {})[ano] = n


def lacunas(estado: dict) -> list[tuple[str, str, int, int]]:
    """(espécie, ano, no ctresb, no Senado) onde o ctresb tem menos."""
    saida = []
    for especie, por_ano in (estado.get("senado") or {}).items():
        for ano, n in sorted(por_ano.items()):
            tem = ((estado.get("anos") or {}).get(especie, {}).get(ano) or {}).get("arquivos", 0)
            if n > tem:
                saida.append((especie, ano, tem, n))
    return saida


_NOME = {"lei": "Lei", "del": "Decreto-Lei", "lcp": "Lei Complementar"}
_PLURAL = {"lei": "Leis", "del": "Decretos-lei", "lcp": "Leis complementares"}


def rotulo(c: str) -> str:
    especie, n, ano = c.split("-")
    return f"{_NOME[especie]} nº {confirmar._milhar(int(n))}/{ano}"


def montar_relatorio(estado: dict, novas: list[str], mudaram: list[str], avisos: list[str], dia: date) -> str:
    anos = estado.get("anos") or {}
    arquivos = sum(a.get("arquivos", 0) for e in anos.values() for a in e.values())
    apontadas = estado.get("apontadas") or {}
    por_estado: dict[str, int] = {}
    for a in apontadas.values():
        k = (a.get("planalto") or {}).get("estado", "a confirmar")
        por_estado[k] = por_estado.get(k, 0) + 1
    L = [f"## Curador — a lei penal antiga que o projeto não leu — {dia.isoformat()}", "",
         f"**{arquivos}** leis, decretos-lei e leis complementares triados no ctresb/leis desde "
         f"{triagem.ANO_INICIAL}; **{len(apontadas)}** com pena própria que o projeto não conhecia. No Planalto: "
         + ", ".join(f"**{n}** {k.replace('_', ' ')}" for k, n in sorted(por_estado.items())) + ".", "",
         "> O ctresb aponta, o Planalto confirma: a lista é de leitura, e nada aqui escreve no catálogo, no "
         "acervo nem em `data/fontes.json`. Pena vigente é candidata a `data/fontes.json`; revogada, ao acervo.", ""]

    def secao(titulo, chaves):
        if not chaves:
            return
        L.extend([f"### {titulo}", ""])
        for c in chaves[:A_MOSTRAR]:
            a = apontadas[c]
            p = a.get("planalto") or {}
            onde = f"[Planalto]({p['url']})" if p.get("url") else f"[ctresb](https://github.com/{ctresb.REPO}/blob/main/{a['caminho']})"
            extra = f" — {p['indicio']}" if p.get("indicio") else ""
            L.append(f"- **{rotulo(c)}** — {p.get('estado', 'a confirmar').replace('_', ' ')}{extra} — {onde}")
            if a.get("ementa"):
                L.append(f"  - {a['ementa'][:220]}")
        if len(chaves) > A_MOSTRAR:
            L.append(f"- _e mais {len(chaves) - A_MOSTRAR}, em `data/curadoria.json`._")
        L.append("")

    def linhas(titulo, chaves):
        if not chaves:
            return
        L.extend([f"### {titulo}", "", ", ".join(rotulo(c) for c in chaves[:3 * A_MOSTRAR])
                  + (f" _e mais {len(chaves) - 3 * A_MOSTRAR}._" if len(chaves) > 3 * A_MOSTRAR else ""), ""])

    def de(estados, chaves, alteradora=False):
        return [c for c in chaves if (apontadas[c].get("planalto") or {}).get("estado") in estados
                and bool(apontadas[c].get("altera")) == alteradora]

    def ano(c):
        return int(c.rsplit("-", 1)[1])
    vigentes = de({"pena_vigente"}, novas)
    secao(f"Novas com pena de prisão vigente, desde {ANO_DO_CP} — candidatas a `data/fontes.json`",
          [c for c in vigentes if ano(c) >= ANO_DO_CP])
    secao(f"Novas com pena de prisão vigente, anteriores a {ANO_DO_CP} — podem ter sido revogadas tacitamente "
          "pelo Código Penal e pela LCP, que o Planalto não anuncia", [c for c in vigentes if ano(c) < ANO_DO_CP])
    secao("Novas revogadas — candidatas ao acervo", de({"revogada", "pena_riscada"}, novas)
          + de({"revogada", "pena_riscada"}, novas, alteradora=True))
    secao("Novas sem página no Planalto — pedem juízo", de({"sem_pagina"}, novas) + de({"sem_pagina"}, novas, True))
    secao("Mudaram de estado desde a última conferência", mudaram)
    linhas("Alteram diploma que o projeto já vigia — a pena é provavelmente a do texto que dão a ele",
           de({"pena_vigente"}, novas, alteradora=True))
    linhas("Pena sem prisão — multa, sanção administrativa, ou a palavra na prosa",
           de({"sem_prisao"}, novas) + de({"sem_prisao"}, novas, True))

    gaps = lacunas(estado)
    if gaps:
        L += ["### O que o Curador não triou", "",
              "> O ctresb não tem todas as normas que o Senado lista. As de baixo ficaram sem triagem; os decretos "
              "com força de lei dos governos provisórios (1889–1891, 1930–1934) o ctresb não tem nenhum.", ""]
        faltam = sum(n - tem for _, _, tem, n in gaps)
        L.append(f"**{faltam}** normas em **{len(gaps)}** anos. Os maiores buracos:")
        for especie, ano, tem, n in sorted(gaps, key=lambda g: g[2] - g[3])[:15]:
            L.append(f"- {_PLURAL.get(especie, 'Decretos')} de {ano}: {tem} no ctresb, {n} no Senado")
        L.append("")
    if avisos:
        L += ["### Não deu para ler", ""] + [f"- {x}" for x in avisos[:20]]
        if len(avisos) > 20:
            L.append(f"- _e mais {len(avisos) - 20}._")
        L.append("")
    return "\n".join(L) + "\n"


def codigo_de_saida(novas: list[str], mudaram: list[str], estado: dict, lido: bool) -> int:
    if not lido:
        return 2
    apontadas = estado.get("apontadas") or {}
    if mudaram or any((apontadas[c].get("planalto") or {}).get("estado") in LEITURA
                      and not apontadas[c].get("altera") for c in novas):
        return 3
    return 0


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    p = argparse.ArgumentParser(description="O Curador: a lei penal antiga que o projeto não leu.")
    p.add_argument("--estado", default=str(ESTADO))
    p.add_argument("--saida", default=str(RELATORIOS))
    p.add_argument("--orcamento", type=int, default=ORCAMENTO)
    p.add_argument("--sem-planalto", action="store_true")
    p.add_argument("--sem-senado", action="store_true")
    args = p.parse_args()

    dia = hoje()
    caminho = Path(args.estado)
    estado = carregar(caminho)
    ler = lambda nome: json.loads((DATA / nome).read_text(encoding="utf-8"))  # noqa: E731
    conhecidos = triagem.conhecidos(ler("fontes.json")["fontes"], ler("diplomas.json"), ler("acervo.json"))
    avisos: list[str] = []
    lido = True
    try:
        commit = ctresb.commit_atual()
        _, avisos_v = varrer.varrer(estado, conhecidos, commit, progresso=lambda m: None)
        avisos += avisos_v
    except (FalhaDeRede, ValueError, KeyError) as e:
        avisos.append(f"o ctresb/leis não pôde ser lido: {e}")
        lido = False
    # A lei que entrou no projeto depois de apontada sai da lista.
    for c in [c for c in estado.get("apontadas") or {} if c in conhecidos]:
        del estado["apontadas"][c]
    # "Nova" é a lei que o Planalto confirmou pela primeira vez nesta rodada: a
    # triagem pode ter apontado numa rodada sem Planalto.
    novas: list[str] = []
    mudaram: list[str] = []
    if not args.sem_planalto:
        novas, mudaram, avisos_c = rodar_confirmacoes(estado, a_confirmar(estado, dia, args.orcamento), dia)
        avisos += avisos_c
    marcar_alteradoras(estado, conhecidos)
    if not args.sem_senado:
        contar_senado(estado, avisos)
    gravar(estado, caminho)

    relatorio = montar_relatorio(estado, novas, mudaram, avisos, dia)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"curadoria-{dia.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    print(relatorio)
    return codigo_de_saida(novas, mudaram, estado, lido)


if __name__ == "__main__":
    raise SystemExit(main())
