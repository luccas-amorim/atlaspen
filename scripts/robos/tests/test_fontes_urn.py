# -*- coding: utf-8 -*-
"""A URN de cada diploma em `data/fontes.json` (plano de fontes abertas, F2).

Errada, ela não quebra nada: aponta para outra norma, e o Cotejador passa a
comparar o diploma com a lei errada. Por isso o construtor reprova URN ausente,
malformada ou repetida.
"""
import json

from catalogo.validacoes import validar_fontes


def _fontes(tmp_path, *fontes):
    caminho = tmp_path / "fontes.json"
    caminho.write_text(json.dumps({"fontes": list(fontes)}), encoding="utf-8")
    return caminho


def test_urns_do_repositorio_passam():
    assert validar_fontes() == []


def test_urn_bem_formada(tmp_path):
    c = _fontes(tmp_path,
                {"id": "lep", "urn": "urn:lex:br:federal:lei:1984-07-11;7210"},
                {"id": "cp", "urn": "urn:lex:br:federal:decreto.lei:1940-12-07;2848"},
                {"id": "lc64", "urn": "urn:lex:br:federal:lei.complementar:1990-05-18;64"})
    assert validar_fontes(c) == []


def test_sem_urn(tmp_path):
    assert validar_fontes(_fontes(tmp_path, {"id": "lep"})) == ["fontes.json: lep sem `urn`"]


def test_urn_malformada(tmp_path):
    problemas = validar_fontes(_fontes(tmp_path, {"id": "lep", "urn": "urn:lex:br:federal:lei:1984;7210"}))
    assert problemas and "malformada" in problemas[0]


def test_urn_repetida(tmp_path):
    urn = "urn:lex:br:federal:lei:1984-07-11;7210"
    problemas = validar_fontes(_fontes(tmp_path, {"id": "lep", "urn": urn}, {"id": "outra", "urn": urn}))
    assert len(problemas) == 2 and all("repete" in p for p in problemas)
