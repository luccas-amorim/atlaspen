# -*- coding: utf-8 -*-
"""O Curador, frente 2: o Planalto confirma o que o ctresb/leis apontou.

Para cada lei apontada pela triagem (`curador/triagem.py`), procura a página no
Planalto e deixa o compilado oficial decidir. Nenhuma das duas fichas que temos
(Senado, normas.leg.br) traz o link, e o endereço muda conforme a época — então
o Curador tenta, em ordem, os endereços que o Planalto usa para cada período, e
só aceita a página cujo cabeçalho declara o MESMO número e o MESMO ano: a Lei
4.242 existe em 1921 e em 1963, e `leis/l4242.htm` é a de 1963 — a de 1921
não tem página.

O que a página diz vira um de seis estados:

- `pena_vigente` — o texto não riscado comina pena privativa de liberdade:
  candidato a `data/fontes.json`.
- `sem_prisao` — comina só multa ou sanção administrativa, ou a palavra "pena"
  está na prosa: lista curta, de baixa prioridade.
- `revogada` — o topo anuncia a revogação do diploma inteiro: candidato ao
  acervo.
- `pena_riscada` — só o texto riscado comina pena: candidato ao acervo, como
  dispositivo revogado.
- `sem_pena` — a página não comina pena fora das aspas: descartado, nomeado.
- `sem_pagina` — nenhum endereço da época respondeu com a lei certa: pede juízo,
  porque só o ctresb a tem.
"""
from __future__ import annotations

import re
import time
from datetime import date

from curador import triagem
from fontes.rede import FalhaDeRede, Rede, UA_NAVEGADOR
from nucleo import revogacao
from nucleo.baixar import decodificar
from nucleo.preceito import comina_pena

PLANALTO = "https://www.planalto.gov.br/ccivil_03/"
REDE = Rede({"User-Agent": UA_NAVEGADOR,
             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
             "Accept-Language": "pt-BR,pt;q=0.9"}, tentativas=2, timeout=60, espera=lambda n: 3)
PAUSA = 1.0                 # educação com o planalto.gov.br


def _milhar(n: int) -> str:
    return f"{n // 1000}.{n % 1000:03d}" if n >= 1000 else str(n)


def enderecos(especie: str, n: int, ano: int) -> list[str]:
    """Os endereços que o Planalto usa para a época, do mais provável ao menos.

    Medido em 26/10/2026: `leis/l1521.htm` (1951), `leis/1930-1949/L0038.htm`
    (1935), `leis/1950-1969/l1164.htm` (1950), `leis/leis_2001/l10257.htm`,
    `leis/2002/L10406.htm`, `leis/2003/L10.826.htm`, `_ato2004-2006/2005/lei/l11101.htm`,
    `decreto-lei/del2848.htm` (1940) e `decreto-lei/del1001.htm` (1969),
    `leis/lcp/lcp105.htm`, `leis/lim/LIM3353.htm` (Império).
    """
    if especie == "lcp":
        return [f"leis/lcp/lcp{n}.htm", f"leis/lcp/Lcp{n}.htm"]
    if especie == "del":
        return [f"decreto-lei/del{n}.htm", f"decreto-lei/Del{n}.htm", f"decreto-lei/Del{n:04d}.htm",
                f"decreto-lei/1937-1946/Del{n}.htm", f"decreto-lei/1937-1946/Del{n:04d}.htm",
                f"decreto-lei/1965-1988/Del{n}.htm", f"decreto-lei/1965-1988/Del{n:04d}.htm"]
    m = _milhar(n)
    if ano >= 2007:
        ini = 2007 + ((ano - 2007) // 4) * 4
        pasta = f"_ato{ini}-{ini + 3}/{ano}/lei"
        return [f"{pasta}/l{n}.htm", f"{pasta}/L{n}.htm", f"{pasta}/l{m}.htm"]
    if ano >= 2004:
        return [f"_ato2004-2006/{ano}/lei/l{n}.htm", f"_ato2004-2006/{ano}/lei/L{n}.htm",
                f"_ato2004-2006/{ano}/lei/l{m}.htm"]
    if ano >= 2002:
        return [f"leis/{ano}/L{n}.htm", f"leis/{ano}/L{m}.htm", f"leis/{ano}/l{n}.htm"]
    if ano == 2001:
        return [f"leis/leis_2001/l{n}.htm", f"leis/leis_2001/L{n}.htm"]
    base = [f"leis/l{n}.htm", f"leis/L{n}.htm"]
    # A Lei 6.620/78 (Segurança Nacional) só responde em `leis/1970-1979/`.
    if ano >= 1980 and ano <= 1988:
        return base + [f"leis/1980-1988/L{n}.htm", f"leis/1980-1988/l{n}.htm"]
    if ano >= 1970 and ano <= 1979:
        return base + [f"leis/1970-1979/L{n}.htm", f"leis/1970-1979/l{n}.htm"]
    if ano >= 1950:
        return base + [f"leis/1950-1969/l{n}.htm", f"leis/1950-1969/L{n}.htm"]
    if ano >= 1930:
        return [f"leis/1930-1949/L{n:04d}.htm", f"leis/1930-1949/l{n}.htm"] + base
    if ano >= 1901:
        return base + [f"leis/1901-1929/L{n}.htm", f"leis/1901-1929/L{n:04d}.htm"]
    return base + [f"leis/1851-1900/L{n}.htm", f"leis/1851-1900/L{n:04d}.htm",
                   f"leis/lim/LIM{n}.htm", f"leis/lim/lim{n}.htm"]


_ESPECIE_NO_CABECALHO = {"lei": r"LEI(?!\s+COMPLEMENTAR)", "del": r"DECRETO[-\s]*LEI",
                         "lcp": r"LEI\s+COMPLEMENTAR"}


def cabecalho_confere(texto: str, especie: str, n: int, ano: int) -> bool:
    """O topo da página declara esta espécie, este número e este ano."""
    topo = re.sub(r"\s+", " ", texto[:6000])
    padrao = (_ESPECIE_NO_CABECALHO[especie] + r"\s*N?\s*[ºo°.]*\s*" + re.escape(_milhar(n)).replace(r"\.", r"\.?")
              + r"(?!\d).{0,60}?(?<!\d)(\d{4})(?!\d)")
    return any(int(m.group(1)) == ano for m in re.finditer(padrao, topo, re.I))


_RISCADO = re.compile(r"<(strike|s|del)\b[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def _texto(html: str, sem_riscado: bool) -> str:
    import html as _h
    html = re.sub(r"<!--.*?-->|<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    if sem_riscado:
        html = _RISCADO.sub(" ", html)
    return re.sub(r"\s+", " ", _h.unescape(_TAG.sub(" ", html))).replace("\xa0", " ")


def _tem_pena(texto: str, ano: int) -> bool:
    propria = triagem._CITACAO.sub(" ", texto)
    return comina_pena(propria) or (ano < triagem.ANO_DA_FORMA_ANTIGA and bool(triagem.FORMA_ANTIGA.search(propria)))


# A pena que tira a liberdade. Na primeira varredura, em 26/10/2026, 50 das 89
# leis com "pena" no texto vigente só tinham multa ou sanção administrativa — a
# CLT, os decretos-lei fiscais dos anos 1940, a Política Nacional de Turismo
# ("Pena - multa e interdição do local") — ou a palavra na prosa da ementa
# ("modifica a pena cominada"). O catálogo é de tipos penais; o crime punido só
# com multa existe, e por isso essas não somem: vão para `sem_prisao`.
_PRIVATIVA = re.compile(
    r"reclus[ãa]o|deten[çc][ãa]o|pris[ãa]o\s+(?:simples|cell?ular|com\s+trabalho|de\s+\d|por\s+\d)|"
    r"pena\s*[-–—:]\s*pris[ãa]o", re.I)


def classificar(html: str, ano: int) -> tuple[str, str | None]:
    vigente = _texto(html, sem_riscado=True)
    rev = revogacao.detectar(vigente)
    if rev.revogado:
        return "revogada", rev.indicio
    if _tem_pena(vigente, ano):
        propria = triagem._CITACAO.sub(" ", vigente)
        return ("pena_vigente" if _PRIVATIVA.search(propria) else "sem_prisao"), None
    if _tem_pena(_texto(html, sem_riscado=False), ano):
        return "pena_riscada", None
    return "sem_pena", None


def confirmar(chave: str, obter=None, pausa: float = PAUSA, dia: date | None = None) -> dict:
    """{"estado", "url", "indicio", "conferido_em"} — ou levanta `FalhaDeRede`
    quando o Planalto não respondeu a nenhum endereço."""
    obter = obter or (lambda u: REDE.obter(u, ausentes=(403, 404, 500)))
    especie, numero, ano = chave.split("-")
    n, a = int(numero), int(ano)
    falhas = 0
    for caminho in enderecos(especie, n, a):
        url = PLANALTO + caminho
        try:
            bruto = obter(url)
        except FalhaDeRede:
            falhas += 1
            continue
        finally:
            if pausa:
                time.sleep(pausa)
        if not bruto:
            continue
        html, _ = decodificar(bruto)
        if not cabecalho_confere(_texto(html, sem_riscado=False), especie, n, a):
            continue
        estado, indicio = classificar(html, a)
        return {"estado": estado, "url": url, "indicio": indicio,
                "conferido_em": (dia or date.today()).isoformat()}
    if falhas == len(enderecos(especie, n, a)):
        raise FalhaDeRede(PLANALTO, falhas, None)
    return {"estado": "sem_pagina", "url": None, "indicio": None,
            "conferido_em": (dia or date.today()).isoformat()}
