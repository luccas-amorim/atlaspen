# -*- coding: utf-8 -*-
"""Lê frações de pena como a lei as escreve.

"de um a dois terços", "de 1/3 (um terço) até metade", "ao dobro", "duplicada",
"à metade", "até a metade". Compartilhado pelo Proponente (que propõe modificador
com a fração lida) e pelo Vigia (que recalcula as linhas de pena derivada): os
dois têm de ler a mesma fração do mesmo texto, senão um propõe o que o outro
acusa.
"""
from __future__ import annotations

import re

VALOR = {
    "um terço": 1 / 3, "1/3": 1 / 3, "dois terços": 2 / 3, "2/3": 2 / 3,
    "metade": 0.5, "1/2": 0.5, "um sexto": 1 / 6, "1/6": 1 / 6,
    "um quarto": 0.25, "1/4": 0.25, "um oitavo": 0.125, "1/8": 0.125,
    "um quinto": 0.2, "1/5": 0.2, "dobro": 1.0, "triplo": 2.0,
    "sexta parte": 1 / 6, "terça parte": 1 / 3, "quarta parte": 0.25,
    "quinta parte": 0.2, "oitava parte": 0.125,
    "duplicada": 1.0, "duplicadas": 1.0, "duplica": 1.0, "triplicada": 2.0,
    "triplicadas": 2.0, "triplica": 2.0,
}
_TOKEN = re.compile(
    r"\b(?:um|dois)\s+(?:t[eê]r[çc]os?|sexto|quarto|oitavo|quinto)\b|\b[12]/[2-8]\b"
    r"|\b(?:sexta|ter[çc]a|quarta|quinta|oitava)\s+parte\b"
    r"|\bmetade\b|\bd[ôo]bro\b|\btriplo\b|\bduplicad[ao]s?\b|\bduplica\b"
    r"|\btriplicad[ao]s?\b|\btriplica\b", re.I)
_UM_A_DOIS_TERCOS = re.compile(r"\bde\s+um\s+a\s+dois\s+t[eê]r[çc]os\b", re.I)
_ATE = re.compile(r"\b(?:em\s+)?at[ée]\s+(?:a\s+|o\s+)?(?:metade|d[ôo]bro|triplo|um\b|dois\b|[12]/)", re.I)
_DE_FRACAO = re.compile(r"\bde\s+(?:um|dois|[12]/|metade)", re.I)
# "acrescida de uma terça parte" (DL 16/1966, art. 3º): o particípio preso ao "de",
# para não casar a anotação "acrescido pela Lei…".
_SOBE = re.compile(r"aument|agravad|majorad|acrescid[ao]s?\s+de\b|d[ôo]bro|duplic|triplo|triplic", re.I)
# Verbo de redução, ou "metade" como A pena ("Pena: metade da cominada",
# "reduzida à metade" — o à com crase). "até a metade" é teto de AUMENTO e
# não entra aqui: foi o que fazia o leitor ver descida em "aumentada de 1/3
# até a metade".
# O verbo tem de estar preso à PENA: "não procura diminuir as consequências do
# seu ato" (CP, art. 121, § 4º) não é minorante, e fazia o leitor ver descida
# num parágrafo que só aumenta.
_DESCE_VERBO = re.compile(
    r"(?:reduz|diminu)\w*\s+(?:a\s+|as\s+|sua\s+)?penas?\b"
    r"|penas?\s+(?:\w+\s+){0,4}(?:reduzid|diminu[íi]d)"
    r"|(?:reduzid|diminu[íi]d)[ao]s?\s+(?:de|à|em|at[ée])\b|diminu[íi]-l[ao]|reduz-se", re.I)
_DESCE_METADE = re.compile(r"\bmetade\s+d[ao]s?\b|penas?\s*[-–—:]\s*metade|\bà\s+metade", re.I)


def _valor(token: str) -> float | None:
    t = re.sub(r"\s+", " ", token.lower()).replace("ê", "e").replace("ô", "o")
    t = t.replace("terco", "terço").replace("terca", "terça")
    if t == "um terços":
        t = "um terço"
    return VALOR.get(t)


def todas_as_fracoes(texto: str) -> list[float]:
    """Cada fração distinta do texto, na ordem em que a lei a escreve.

    Para dispositivo com duas hipóteses no mesmo texto ("aumentadas de um
    terço, se… lesão grave; duplicadas, se… morte"): a 1ª parte é a primeira
    fração, a 2ª parte é a segunda.
    """
    vals: list[float] = []
    for m in _TOKEN.finditer(texto):
        v = _valor(m.group(0))
        if v is not None and (not vals or abs(vals[-1] - v) > 1e-9):
            vals.append(v)
    return vals


_PARTES = re.compile(r";|\.\s+(?=[A-ZÀ-Ú])")


def parte(texto: str, n: int) -> str:
    """A N-ésima oração de um dispositivo com mais de uma hipótese.

    O art. 127 do CP aumenta de um terço "se… lesão corporal de natureza grave;
    e são duplicadas, se… morte"; o art. 121, § 4º trata o culposo numa frase e
    o doloso na seguinte. O catálogo chama cada uma de "1ª parte" e "2ª parte".
    """
    partes = [x.strip() for x in _PARTES.split(texto) if x.strip()]
    return partes[n - 1] if len(partes) >= n else ""


def fracoes_do_texto(texto: str) -> tuple[float, float] | None:
    """(mínima, máxima) lidas do texto; None quando não há fração legível.

    A lei repete cada fração por extenso e em algarismo — "1/3 (um terço)" — e
    a repetição é descartada. "até a metade" sem mínimo declarado parte de
    zero, pela regra `fracoes_de_teto` do catálogo de modificadores.
    """
    if _UM_A_DOIS_TERCOS.search(texto):
        return (1 / 3, 2 / 3)
    vals: list[float] = []
    for m in _TOKEN.finditer(texto):
        v = _valor(m.group(0))
        if v is None:
            continue
        if not vals or abs(vals[-1] - v) > 1e-9:
            vals.append(v)
    if not vals:
        return None
    if len(vals) == 1:
        if _ATE.search(texto) and not _DE_FRACAO.search(texto):
            return (0.0, vals[0])
        return (vals[0], vals[0])
    return (min(vals[:2]), max(vals[:2]))


def direcao(texto: str) -> str | None:
    """'aumento', 'diminuicao', ou None quando o texto não diz (ou diz os dois)."""
    sobe = bool(_SOBE.search(texto))
    verbo = bool(_DESCE_VERBO.search(texto))
    if sobe and not verbo:
        return "aumento"
    if (verbo or _DESCE_METADE.search(texto)) and not sobe:
        return "diminuicao"
    return None


def fracao_humana(fmin: float, fmax: float) -> str:
    nomes = {1 / 3: "1/3", 2 / 3: "2/3", 0.5: "1/2", 1 / 6: "1/6", 0.25: "1/4",
             0.125: "1/8", 0.2: "1/5", 1.0: "dobro", 2.0: "triplo"}

    def nome(v: float) -> str:
        return next((n for k, n in nomes.items() if abs(k - v) < 1e-9), f"{v:.3f}")
    if abs(fmin - fmax) < 1e-9:
        return nome(fmin)
    if fmin == 0:
        return f"até {nome(fmax)}"
    return f"{nome(fmin)} a {nome(fmax)}"


def aplicar(base_min: float, base_max: float, natureza: str,
            fracao: tuple[float, float]) -> tuple[float, float]:
    """A moldura derivada, como o catálogo a calcula.

    Aumento com intervalo: o mínimo sobe pela fração mínima e o máximo pela
    máxima (roubo majorado: 6–10 anos, +1/3 até 1/2, dá 8–15). Diminuição com
    intervalo: o mínimo cai pela fração MÁXIMA e o máximo pela mínima (furto
    privilegiado: 1–6 anos, −1/3 a −2/3, dá 4 meses a 4 anos). É a leitura mais
    larga da moldura, e é a que o site publica.
    """
    fmin, fmax = fracao
    if natureza == "aumento":
        return (base_min * (1 + fmin), base_max * (1 + fmax))
    return (base_min * (1 - fmax), base_max * (1 - fmin))
