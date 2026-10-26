# -*- coding: utf-8 -*-
"""O Curador, frente 3: o normas.leg.br onde o Planalto e o ctresb não chegam.

Duas lacunas que a varredura de 26/10/2026 declarou:

1. **As leis sem página no Planalto** — o ctresb as tinha e apontou pena, mas
   nenhum endereço do Planalto respondeu com a lei certa (60 na primeira rodada,
   quase todas decretos-lei de 1937–1946 e leis de 1890–1930).
2. **Os decretos dos governos provisórios** (1889–1891 e 1930–1934), que tinham
   força de lei — o Código Penal de 1890 é o Decreto 847 — e que o ctresb não
   tem: 8.193, pela lista do Senado.

Para as duas, o texto vem do normas.leg.br (LexML, Congresso), que a API marca
como sem valor legal oficial ("UnofficialLegalValue"). A decisão de 26/10/2026
abre uma exceção estreita à regra "fonte secundária aponta, não escreve": quando
o Planalto não tem a norma, o texto do normas.leg.br pode sustentar um registro
do ACERVO — e o registro diz de onde veio. O catálogo ativo continua só com o
Planalto. Este módulo não escreve em lugar nenhum além do estado do Curador: ele
diz onde há pena, e a entrada no acervo é juízo de quem assina.

Uso:
    python scripts/robos/curador/lexml.py --sem-pagina
    python scripts/robos/curador/lexml.py --decretos 1889-1891,1930-1934
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from curador import confirmar, curar, triagem  # noqa: E402
from fontes import normas, senado  # noqa: E402
from fontes.rede import FalhaDeRede  # noqa: E402
from nucleo.preceito import comina_pena  # noqa: E402

PARALELO = 3                # o normas.leg.br divide um limitador de 0,5 s entre as threads
_LINHA_PENA = re.compile(r"[^.;:]{0,120}(?:pena|punid|incorrer)[^.;]{0,160}", re.I)


def chave_decreto(numero: str, complemento: str | None, ano: int | str) -> str:
    """"dec-1232c-1890": o número, a letra do complemento quando há, e o ano."""
    return f"dec-{int(numero)}{(complemento or '').lower()}-{int(ano)}"


def urn_decreto(numero: str, complemento: str | None, data_iso: str) -> str:
    """A URN que o normas.leg.br reconhece: letra minúscula depois de hífen
    (`;1232-c`). Medido em 26/10/2026 — `;1232-C` e `;1232c` voltam vazias."""
    return f"urn:lex:br:federal:decreto:{data_iso};{int(numero)}" + (f"-{complemento.lower()}" if complemento else "")


def ler_lista_decretos(dados: dict) -> list[dict]:
    """A lista de decretos do ano no Senado, com o complemento que o `Resumo`
    do cliente não guarda."""
    docs = ((dados or {}).get("ListaDocumento") or {}).get("documentos") or {}
    docs = docs.get("documento") or []
    saida = []
    for d in docs if isinstance(docs, list) else [docs]:
        m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", d.get("dataassinatura") or "")
        if not (d.get("numero") or "").isdigit() or not m:
            continue
        data_iso = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        comp = d.get("complemento") or None
        saida.append({"chave": chave_decreto(d["numero"], comp, m.group(3)), "urn": urn_decreto(d["numero"], comp, data_iso),
                      "nome": d.get("normaNome") or "", "ementa": (d.get("ementa") or "")[:300]})
    return saida


def classificar_texto(html: str, ano: int) -> dict:
    """Pena própria (fora das aspas), forma antiga antes de 1941, e se tira a
    liberdade — o mesmo critério da confirmação no Planalto."""
    texto = confirmar._texto(html, sem_riscado=False)
    propria = triagem._CITACAO.sub(" ", texto)
    pena = comina_pena(propria) or (ano < triagem.ANO_DA_FORMA_ANTIGA and bool(triagem.FORMA_ANTIGA.search(propria)))
    if not pena:
        return {"estado": "sem_pena"}
    privativa = bool(confirmar._PRIVATIVA.search(propria))
    amostra = next((m.group(0).strip() for m in _LINHA_PENA.finditer(propria)
                    if confirmar._PRIVATIVA.search(m.group(0))), None) if privativa else None
    return {"estado": "pena_privativa" if privativa else "sem_prisao", "amostra": (amostra or "")[:280] or None}


def ler(urn: str, ano: int, dia: date, ficha=normas.ficha, texto=normas.texto) -> dict:
    f = ficha(urn)
    if not f or not f.versoes:
        return {"estado": "sem_texto", "conferido_em": dia.isoformat()}
    v = f.versao("Original") or f.versoes[0]
    html = texto(v)
    if not html:
        return {"estado": "sem_texto", "conferido_em": dia.isoformat()}
    r = classificar_texto(html, ano)
    r.update({"url_texto": v.url_texto, "versao": v.versao or v.tipo, "conferido_em": dia.isoformat()})
    return r


def ler_sem_pagina(estado: dict, dia: date, progresso=print) -> dict:
    """As apontadas que o Planalto não tem: o resultado vai em `lexml`."""
    feitas = {}
    for c, a in sorted((estado.get("apontadas") or {}).items()):
        if (a.get("planalto") or {}).get("estado") != "sem_pagina" or not a.get("urn"):
            continue
        try:
            a["lexml"] = ler(a["urn"], int(c.rsplit("-", 1)[1]), dia)
        except (FalhaDeRede, ValueError) as e:
            progresso(f"{c}: não lido ({e})")
            continue
        feitas[c] = a["lexml"]["estado"]
        progresso(f"{c}: {a['lexml']['estado']}")
    return feitas


def ler_decretos(estado: dict, anos: list[int], dia: date, progresso=print) -> None:
    """Os decretos dos governos provisórios. Por ano: quantos, quantos lidos, e
    só os que têm pena ficam em `decretos`; o ano inteiro lido não volta."""
    por_ano = estado.setdefault("lexml_anos", {})
    achados = estado.setdefault("decretos", {})
    for ano in anos:
        if (por_ano.get(str(ano)) or {}).get("completo"):
            continue
        lista = ler_lista_decretos(senado._json(senado.url_lista(ano, "DEC")))
        contagem = {"decretos": len(lista), "sem_texto": 0, "sem_pena": 0, "sem_prisao": 0, "pena_privativa": 0,
                    "nao_lidos": 0}

        def um(d):
            try:
                return d, ler(d["urn"], ano, dia)
            except (FalhaDeRede, ValueError):
                return d, None
        with cf.ThreadPoolExecutor(PARALELO) as ex:
            for d, r in ex.map(um, lista):
                if r is None:
                    contagem["nao_lidos"] += 1
                    continue
                contagem[r["estado"]] += 1
                if r["estado"] in ("pena_privativa", "sem_prisao"):
                    achados[d["chave"]] = {**d, "lexml": r}
        contagem["completo"] = contagem["nao_lidos"] == 0
        por_ano[str(ano)] = contagem
        curar.gravar(estado, curar.ESTADO)          # um ano por vez: a varredura longa não se perde
        progresso(f"decretos de {ano}: {contagem}")


def _anos(spec: str) -> list[int]:
    anos = []
    for parte in spec.split(","):
        de, _, ate = parte.partition("-")
        anos += list(range(int(de), int(ate or de) + 1))
    return anos


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    p = argparse.ArgumentParser(description="O Curador no normas.leg.br, onde o Planalto e o ctresb não chegam.")
    p.add_argument("--sem-pagina", action="store_true")
    p.add_argument("--decretos", help="anos, como 1889-1891,1930-1934")
    args = p.parse_args()
    from nucleo.tempo import hoje
    dia = hoje()
    estado = curar.carregar(curar.ESTADO)
    if args.sem_pagina:
        ler_sem_pagina(estado, dia)
        curar.gravar(estado, curar.ESTADO)
    if args.decretos:
        ler_decretos(estado, _anos(args.decretos), dia)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
