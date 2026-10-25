# -*- coding: utf-8 -*-
"""O Relator (`relator/decisoes.py`), sem rede: os precedentes vêm das fixtures
`cnj-*.json`, respostas reais do Banco Nacional de Precedentes de 25/10/2026."""
import json
from datetime import date

import pytest

from conftest import FIXTURES
from fontes import cnj
from relator import decisoes as rel

FONTES = [
    {"id": "cp", "urn": "urn:lex:br:federal:decreto.lei:1940-12-07;2848"},
    {"id": "lcp", "urn": "urn:lex:br:federal:decreto.lei:1941-10-03;3688"},
    {"id": "cpm", "urn": "urn:lex:br:federal:decreto.lei:1969-10-21;1001"},
    {"id": "drogas-11343", "urn": "urn:lex:br:federal:lei:2006-08-23;11343"},
    {"id": "cf", "urn": "urn:lex:br:federal:constituicao:1988-10-05;1988"},
]
# Os ids reais de static/data/crimes.json em 25/10/2026.
CHAVES = {"lcp|art. 25, caput": [766], "cp|art. 331, caput": [269], "cp|art. 121, §2º, i": [3]}


@pytest.fixture
def idx():
    return rel.indices(FONTES)


def _um(nome):
    return cnj.ler_resultados(json.loads((FIXTURES / nome).read_text(encoding="utf-8")))[0]


class TestIndices:
    def test_codigo_do_ato_impugnado(self, idx):
        codigos, _ = idx
        assert codigos["LEG-FED DEL-002848 ANO-1940"] == "cp"
        assert codigos["LEG-FED LEI-011343 ANO-2006"] == "drogas-11343"
        assert all(v != "cf" for v in codigos.values())

    def test_citacao_e_nome(self, idx):
        _, padroes = idx
        assert padroes["lcp"].search("Lei de Contravenções Penais (Decreto-lei 3.688/1941)")
        assert padroes["cp"].search("o art. 331 do Código Penal")
        assert not padroes["cp"].search("o art. 166 do Código Penal Militar")
        assert padroes["cpm"].search("o art. 166 do Código Penal Militar")
        assert padroes["drogas-11343"].search("art. 28 da Lei 11.343/2006")
        assert not padroes["drogas-11343"].search("Lei 11.3430")


class TestLeitura:
    def test_tema_113_toca_o_registro_766(self, idx):
        a = rel.avaliar(_um("cnj-tema-113.json"), *idx, CHAVES)
        assert a["natureza"] == "não recepção"
        assert a["fontes"] == {"lcp": ["25"]}
        assert a["ids"] == [766] and a["a_ler"]

    def test_adpf_496_e_recepcao_do_desacato(self, idx):
        a = rel.avaliar(_um("cnj-adpf-496.json"), *idx, CHAVES)
        assert "331" in a["fontes"]["cp"]
        assert a["natureza"] == "recepção"
        # Toca o registro do desacato: pede leitura, mesmo sem mudar o alcance.
        assert a["ids"] == [269] and a["a_ler"]

    def test_precedente_que_nao_toca_nada(self, idx):
        p = cnj.Precedente("stf-adi-1", "ADI", "1", "MERITO", date(2026, 10, 20),
                           "LEG-FED LEI-007098 ANO-1998", "Taxa estadual inconstitucional.")
        assert rel.avaliar(p, *idx, CHAVES) is None

    def test_citacao_sem_artigo_nao_pede_leitura(self, idx):
        p = cnj.Precedente("stf-rg-9", "RG", "9", None, date(2026, 10, 20), "",
                           "Questão sobre a dosimetria prevista no Código Penal, sem mudar a norma.")
        a = rel.avaliar(p, *idx, CHAVES)
        assert a["fontes"] == {"cp": []} and a["natureza"] == "outra" and not a["a_ler"]

    @pytest.mark.parametrize("texto, esperado", [
        ("O art. 25 não foi recepcionado pela Constituição", "não recepção"),
        ("declarar a não recepção do art. 260", "não recepção"),
        ("julgou procedente para declarar inconstitucional o art. 28", "inconstitucionalidade"),
        ("conferir interpretação conforme à Constituição", "interpretação conforme"),
        ("considerou recepcionado o art. 166", "recepção"),
        ("É constitucional o tipo penal previsto no art. 2º", "constitucionalidade"),
        ("Constitucionalidade do art. 305 do Código de Trânsito", "constitucionalidade"),
        ("É inconstitucional a expressão", "inconstitucionalidade"),
        ("Questão de competência", "outra"),
    ])
    def test_natureza(self, texto, esperado):
        assert rel.natureza(texto) == esperado


class TestRelatorio:
    def test_codigos(self):
        assert rel.codigo_de_saida([], None) == 0
        assert rel.codigo_de_saida([{"a_ler": False}], None) == 0
        assert rel.codigo_de_saida([{"a_ler": True}], None) == 3
        assert rel.codigo_de_saida([], "timeout") == 2

    def test_relatorio(self, idx):
        a = rel.avaliar(_um("cnj-tema-113.json"), *idx, CHAVES)
        texto = rel.montar_relatorio([a], 14, date(2026, 10, 17), date(2026, 10, 25), None)
        assert "Tema 113 de repercussão geral" in texto and "paradigma: 583523" in texto
        assert "toca registro(s) do catálogo" in texto and "o silêncio dele não prova nada" in texto

    def test_janela_no_teto_avisa(self):
        texto = rel.montar_relatorio([], rel.LIMITE, date(2025, 10, 25), date(2026, 10, 25), None)
        assert "o que veio além não foi lido" in texto

    def test_cnj_fora_do_ar_nao_e_silencio(self):
        texto = rel.montar_relatorio([], 0, date(2026, 10, 17), date(2026, 10, 25), "timeout")
        assert "não pôde ser lido" in texto
