# -*- coding: utf-8 -*-
"""O Curador no normas.leg.br (`curador/lexml.py`), sem rede."""
from datetime import date

from curador import lexml
from fontes.normas import Ficha, Versao


def test_chave_e_urn_do_decreto_com_letra():
    assert lexml.chave_decreto("1232", "C", "1890") == "dec-1232c-1890"
    assert lexml.chave_decreto("847", None, "1890") == "dec-847-1890"
    # Medido em 26/10/2026: só a forma com hífen e minúscula responde.
    assert lexml.urn_decreto("1232", "C", "1890-12-31") == "urn:lex:br:federal:decreto:1890-12-31;1232-c"
    assert lexml.urn_decreto("847", None, "1890-10-11") == "urn:lex:br:federal:decreto:1890-10-11;847"


def test_lista_do_senado():
    dados = {"ListaDocumento": {"documentos": {"documento": [
        {"numero": "1232", "complemento": "C", "dataassinatura": "31/12/1890",
         "normaNome": "Decreto nº 1.232-C de 31/12/1890", "ementa": "PRORROGA O PRAZO."},
        {"numero": "847", "complemento": None, "dataassinatura": "11/10/1890",
         "normaNome": "Decreto nº 847 de 11/10/1890", "ementa": "Promulga o Codigo Penal."},
        {"numero": "S/N", "dataassinatura": "01/01/1890"}]}}}
    lista = lexml.ler_lista_decretos(dados)
    assert [d["chave"] for d in lista] == ["dec-1232c-1890", "dec-847-1890"]


def _ficha(html, versao="Original"):
    return Ficha("urn", "Decreto", "", None, (Versao(versao, "PublicacaoOriginal", None, "http://texto", "Unofficial"),))


def test_le_pena_antiga_no_texto_original():
    html = "<p>Art. 1º Incorrerá na pena de prisão cellular por um a seis mezes quem...</p>"
    r = lexml.ler("urn", 1890, date(2026, 10, 26), ficha=lambda u: _ficha(html), texto=lambda v: html)
    assert r["estado"] == "pena_privativa" and r["url_texto"] == "http://texto" and r["versao"] == "Original"
    assert "prisão cellular" in r["amostra"]


def test_so_multa_e_sem_texto():
    html = "<p>Art. 1º Os infractores incorrerão na pena de multa de 200$000.</p>"
    r = lexml.ler("urn", 1890, date(2026, 10, 26), ficha=lambda u: _ficha(html), texto=lambda v: html)
    assert r["estado"] == "sem_prisao"
    vazia = Ficha("", "", "", None, ())
    assert lexml.ler("urn", 1890, date(2026, 10, 26), ficha=lambda u: vazia)["estado"] == "sem_texto"


def test_pena_citada_nao_conta():
    html = "<p>Art. 1º O art. 2º passa a vigorar: “Art. 2º Pena – reclusão, de um a quatro annos.”</p>"
    r = lexml.ler("urn", 1932, date(2026, 10, 26), ficha=lambda u: _ficha(html), texto=lambda v: html)
    assert r["estado"] == "sem_pena"
