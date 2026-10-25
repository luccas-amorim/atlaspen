# -*- coding: utf-8 -*-
"""Testes do cliente do normas.leg.br (`fontes/normas.py`), sem rede."""
import json

from conftest import FIXTURES
from fontes import normas


def _ficha():
    return normas.ler_ficha(json.loads((FIXTURES / "normas-cp-ficha.json").read_text(encoding="utf-8")))


def test_versoes_do_cp():
    f = _ficha()
    assert f.urn == "urn:lex:br:federal:decreto.lei:1940-12-07;2848"
    assert f.ementa == "Código Penal."
    assert [v.versao for v in f.versoes] == ["Original", "Current"]
    original = f.versao("Original")
    assert original.publicada_em == "1940-12-31" and original.tipo == "PublicacaoOriginal"


def test_texto_vai_pelo_endereco_publico():
    """O `contentUrl` da ficha aponta para /api/binario/, que responde 404 fora
    do navegador; o texto está em /api/public/binario/."""
    for v in _ficha().versoes:
        assert "/api/public/binario/" in v.url_texto


def test_nenhuma_versao_tem_valor_oficial():
    assert {v.valor_legal for v in _ficha().versoes} == {"UnofficialLegalValue"}


def test_licenca_cc_by():
    assert _ficha().licenca == "https://creativecommons.org/licenses/by/4.0/"
