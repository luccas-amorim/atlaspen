# -*- coding: utf-8 -*-
"""O texto de uma norma no normas.leg.br (LexML, Congresso Nacional).

A API pública devolve, por URN, a ficha da norma em JSON-LD (schema.org), com
as VERSÕES de texto que o portal guarda:

- `Original`: a publicação original no DOU — o CP de 31/12/1940, por exemplo;
- `Current`: a compilação vigente da Câmara;
- `Intermediate`: republicação ou retificação, quando há.

Não há versões intermediárias de redação: para a história de um patamar (o
art. 112 da LEP de 40% a 70%) o compilado do Planalto, que guarda o riscado,
continua sendo a fonte. O que este módulo dá é o texto ORIGINAL, para cotejar
o `texto_original` do acervo, e uma segunda leitura do vigente.

As duas versões vêm marcadas `UnofficialLegalValue`: valor legal, só o DOU. O
conteúdo é CC BY 4.0, e é por isso que publicar texto daqui exige o crédito.

O endereço é o que o `scripts/baixar_federal.py` do ctresb/leis usa (MIT, ver
`LICENSE-ctresb-leis.txt`): a ficha em `/api/public/normas`, e o texto em
`/api/public/binario/` — o `contentUrl` da ficha aponta para `/api/binario/`,
que responde 404 fora do navegador.
"""
from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass

from fontes.rede import Rede
from nucleo.baixar import decodificar

FICHA = "https://normas.leg.br/api/public/normas?urn={urn}&tipo_documento=maior-detalhe"
REDE = Rede({"User-Agent": "AtlasPen (+https://github.com/luccas-amorim/atlaspen)",
             "Accept": "application/json, text/html;q=0.9"},
            tentativas=3, timeout=90, intervalo=0.5)


@dataclass(frozen=True)
class Versao:
    versao: str                 # "Original", "Current", "Intermediate"
    tipo: str                   # "PublicacaoOriginal", "CompilacaoMonoVigenteNaCD"…
    publicada_em: str | None    # AAAA-MM-DD, quando o portal informa
    url_texto: str
    valor_legal: str            # "UnofficialLegalValue"…


@dataclass(frozen=True)
class Ficha:
    urn: str
    nome: str
    ementa: str
    licenca: str | None
    versoes: tuple[Versao, ...]

    def versao(self, nome: str) -> Versao | None:
        return next((v for v in self.versoes if v.versao == nome), None)


def _publica(url: str) -> str:
    return url.replace("/api/binario/", "/api/public/binario/")


def ler_ficha(dados: dict) -> Ficha:
    """A ficha JSON-LD, sem rede. Só as versões em HTML: é o que se lê."""
    versoes = []
    encs = dados.get("encoding") or []
    for e in (encs if isinstance(encs, list) else [encs]):
        if not isinstance(e, dict) or not e.get("contentUrl"):
            continue
        if "html" not in (e.get("encodingFormat") or "text/html"):
            continue
        versoes.append(Versao(e.get("version") or "", e.get("additionalType") or "",
                              e.get("datePublished"), _publica(e["contentUrl"]),
                              e.get("legislationLegalValue") or ""))
    return Ficha(dados.get("legislationIdentifier") or "", dados.get("name") or "",
                 dados.get("abstract") or "", dados.get("license"), tuple(versoes))


def ficha(urn: str) -> Ficha | None:
    bruto = REDE.obter(FICHA.format(urn=urllib.parse.quote(urn, safe=":;")), ausentes=(404,))
    return ler_ficha(json.loads(bruto)) if bruto else None


def texto(versao: Versao) -> str | None:
    """O HTML da versão, decodificado com o mesmo rigor do Planalto."""
    bruto = REDE.obter(versao.url_texto, ausentes=(404,))
    if bruto is None:
        return None
    html, _ = decodificar(bruto)
    return html
