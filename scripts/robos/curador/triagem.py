# -*- coding: utf-8 -*-
"""O Curador, frente 1: a triagem da legislação federal no ctresb/leis.

O Recenseador varre o ano corrente; a legislação penal brasileira tem quase dois
séculos. O Curador lê, desde 1889, toda lei ordinária, decreto-lei e lei
complementar que o ctresb/leis converteu para Markdown, e aponta as que cominam
pena e que o projeto não conhece — nem em `data/fontes.json`, nem em
`data/diplomas.json` (com os excluídos), nem no acervo.

O ctresb APONTA (decisão 1 do plano, `.superpowers/planos/2026-10-26-curador.md`):
o que ele diz vira lista de leitura, e quem decide é o Planalto, na frente 2
(`curador/confirmar.py`). Nada daqui escreve no catálogo.

**A pena própria e a pena citada.** Depois de 1940, quase toda lei que altera o
CP traz "Pena –" dentro do texto que dá ao CP, entre aspas (“Art. 121. …” (NR)).
Essa é a pena de um diploma que o Vigia já lê. A triagem tira o que está entre
“ e ” antes de procurar a pena: o que sobra é da própria lei.

**A forma antiga.** O critério do núcleo (`nucleo/preceito.py`) é o do Sentinela e
do Recenseador, e não reconhece "incorrerá na pena de prisão cellular". Ele não
muda — "pena de multa" também é sanção administrativa moderna, e o Sentinela se
encheria de falso positivo. A forma antiga soma-se a ele só para a lei anterior a
1941, ano anterior ao do Código Penal e da LCP em vigor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from nucleo.preceito import comina_pena

# Desde 1889: decisão 2 do plano. Os decretos com força de lei dos governos
# provisórios (1889–1891, 1930–1934) não estão no ctresb, que só tem decretos de
# 1945 em diante — lacuna declarada no relatório, com as contagens do Senado.
ANO_INICIAL = 1889
PASTAS = {"lei": "federal/leis-ordinarias", "del": "federal/decretos-lei",
          "lcp": "federal/leis-complementares"}
ANO_DA_FORMA_ANTIGA = 1941

FORMA_ANTIGA = re.compile(
    r"incorrer[áa]o?\s+n[ao]s?\s+penas?\s+de|"
    r"\bpenas?\s*(?:de|:)?\s*(?:pris[ãa]o|reclus[ãa]o|deten[çc][ãa]o|degredo|desterro|gal[ée]s)|"
    r"pris[ãa]o\s+cell?ular|"
    r"ser[áa]o?\s+punid[oa]s?\s+com\s+(?:a\s+)?(?:pena|pris[ãa]o|multa)",
    re.I)
_CITACAO = re.compile(r"“[^”]*”", re.S)
_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_ARQUIVO = re.compile(r"^(lei|del|lcp)-(\d+)-(\d{4})-\d{2}-\d{2}\.md$")


def chave(especie: str, numero: int | str, ano: int | str) -> str:
    """"lei-1521-1951": a espécie, o número e o ano — a Lei 4.242 existe em 1921 e
    em 1963, e o número sozinho não identifica."""
    return f"{especie}-{int(str(numero).replace('.', ''))}-{int(ano)}"


def chave_do_arquivo(nome: str) -> str | None:
    m = _ARQUIVO.match(nome)
    return chave(m.group(1), m.group(2), m.group(3)) if m else None


_URN = {"lei": "lei", "decreto.lei": "del", "lei.complementar": "lcp"}


def chave_da_urn(urn: str | None) -> str | None:
    partes = (urn or "").split(":")
    if len(partes) != 6 or partes[4] not in _URN or ";" not in partes[5]:
        return None
    data, numero = partes[5].split(";", 1)
    return chave(_URN[partes[4]], numero, data[:4])


# "Lei nº 1.521, de 26 de dezembro de 1951", "Decreto-Lei nº 201/1967",
# "LEP (7.210/1984)", "Lei Complementar nº 64/1990".
_NORMA = re.compile(
    r"(?:(Lei\s+Complementar|Decreto[-\s]Lei|DL|Lei)\s*n?[ºo°.]*\s*)?"
    r"\(?(\d{1,2}\.?\d{3}|\d{1,4})\s*(?:/\s*|,\s*de\s+\d{1,2}[ºo°]?\s+de\s+\w+\s+de\s+)(\d{4})", re.I)


def chaves_da_norma(texto: str) -> set[str]:
    saida = set()
    for m in _NORMA.finditer(texto or ""):
        especie = (m.group(1) or "lei").lower()
        prefixo = "lcp" if "complementar" in especie else "del" if especie.startswith(("decreto", "dl")) else "lei"
        saida.add(chave(prefixo, m.group(2), m.group(3)))
    return saida


def conhecidos(fontes: list[dict], diplomas: dict, acervo: dict) -> dict[str, str]:
    """{chave: onde o projeto já a conhece}."""
    saida: dict[str, str] = {}
    for f in fontes:
        c = chave_da_urn(f.get("urn"))
        if c:
            saida[c] = f"fontes.json ({f['id']})"
    for d in diplomas.get("diplomas") or []:
        for c in chaves_da_norma(d.get("norma") or ""):
            saida.setdefault(c, f"diplomas.json ({d['id']})")
    for d in diplomas.get("excluidos") or []:
        for c in chaves_da_norma(d.get("norma") or ""):
            saida.setdefault(c, "diplomas.json (excluído)")
    for r in acervo.get("registros") or []:
        for n in r.get("normas") or []:
            for c in chaves_da_norma(f"{n.get('norma', '')}"):
                saida.setdefault(c, f"acervo.json ({r['id']})")
    return saida


def frontmatter(md: str) -> tuple[dict[str, str], str]:
    m = _FRONT.match(md.replace("\r\n", "\n"))
    if not m:
        return {}, md
    campos = {}
    for linha in m.group(1).splitlines():
        k, _, v = linha.partition(":")
        campos[k.strip()] = v.strip().strip('"')
    return campos, md.replace("\r\n", "\n")[m.end():]


@dataclass(frozen=True)
class Triada:
    chave: str
    caminho: str
    titulo: str
    ementa: str
    urn: str | None
    revogada: bool | None        # o que o ctresb diz; o Planalto confirma
    pena_propria: bool
    pena_citada: bool            # só entre aspas: redação dada a outro diploma


def triar(caminho: str, md: str) -> Triada | None:
    nome = caminho.rsplit("/", 1)[-1]
    c = chave_do_arquivo(nome)
    if not c:
        return None
    ano = int(c.rsplit("-", 1)[1])
    campos, corpo = frontmatter(md)
    propria = _CITACAO.sub(" ", corpo)
    pena = comina_pena(propria) or (ano < ANO_DA_FORMA_ANTIGA and bool(FORMA_ANTIGA.search(propria)))
    citada = not pena and comina_pena(corpo)
    rev = campos.get("revogada")
    return Triada(c, caminho, campos.get("titulo", ""), campos.get("ementa", "")[:300], campos.get("urn"),
                  {"true": True, "false": False}.get(rev), pena, citada)
