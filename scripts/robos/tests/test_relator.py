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
    {"id": "lep", "urn": "urn:lex:br:federal:lei:1984-07-11;7210"},
    {"id": "cf", "urn": "urn:lex:br:federal:constituicao:1988-10-05;1988"},
]
# Os ids reais de static/data/crimes.json em 25/10/2026.
CHAVES = {"lcp|art. 25, caput": [766], "cp|art. 331, caput": [269], "cp|art. 121, §2º, i": [3],
          "cp|art. 157, §2º, i": [1186], "cp|art. 155, §4º, i": [1003], "cp|art. 155, caput": [1002]}


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

    def test_sumula_cancelada_do_stj(self, idx):
        # "No crime de roubo, a intimidação feita com arma de brinquedo…" não cita
        # diploma nem artigo. Cancelada e penal, pede leitura mesmo assim.
        p = _um("cnj-stj-sumula-174.json")
        a = rel.avaliar(p, *idx, CHAVES)
        assert a["natureza"] == "súmula cancelada" and a["fontes"] == {} and a["a_ler"]
        texto = rel.montar_relatorio([a], {"STJ": 1}, date(2026, 10, 17), date(2026, 10, 25), {})
        assert "fala de matéria penal sem citar diploma" in texto

    def test_sumula_cancelada_fora_do_penal_nao_entra(self, idx):
        p = cnj.Precedente("stj-sum-2", "SUM", "2", None, date(2026, 10, 20), "",
                           "O prazo para a ação de cobrança do seguro é de um ano.", (), "STJ", "Cancelado")
        assert rel.avaliar(p, *idx, CHAVES) is None

    def test_repetitivo_do_stj_toca_o_furto(self, idx):
        a = rel.avaliar(_um("cnj-stj-tema-1087.json"), *idx, CHAVES)
        assert a["orgao"] == "STJ" and a["fontes"]["cp"] == ["155"]
        assert a["ids"] == [1002, 1003] and a["a_ler"]

    def test_sigla_do_stj(self, idx):
        p = cnj.Precedente("stj-sum-1", "SUM", "1", None, date(2026, 10, 20), "",
                           "A qualificadora do art. 155, § 4º, I, do CP não se aplica.", (), "STJ", "Cancelado")
        a = rel.avaliar(p, *idx, CHAVES)
        assert a["fontes"] == {"cp": ["155"]} and a["natureza"] == "súmula cancelada" and a["a_ler"]
        assert rel.pelo_texto("a cp de lei", idx[1]) == {}          # a sigla só casa em maiúsculas
        assert "cp" not in rel.pelo_texto("art. 3º do CPP", idx[1])

    def test_tese_sobre_atributo_pede_leitura(self, idx):
        # Tema 1270 do STJ, 25/10/2026: remição pelo Enem, LEP, art. 126.
        p = cnj.Precedente("stj-rr-1270", "RR", "1270", None, date(2026, 10, 20), "",
                           "É cabível a remição proporcional da pena, nos termos do art. 126 da Lei de "
                           "Execução Penal.", (), "STJ", "Acórdão Publicado")
        a = rel.avaliar(p, *idx, CHAVES, {"lep|art. 126": ["remicao"], "cp|art. 33, §2º": ["regime"]})
        assert a["atributos"] == ["remicao"] and a["ids"] == [] and a["a_ler"]
        texto = rel.montar_relatorio([a], {"STJ": 1}, date(2026, 10, 17), date(2026, 10, 25), {})
        assert "**toca atributo(s)**: [remicao](" in texto

    def test_indice_dos_atributos_reais(self):
        indice = rel.indice_atributos()
        assert indice["lep|art. 126"] == ["remicao"] and "regime" in indice["cp|art. 33, §2º"]

    def test_tema_cancelado_nao_muda_alcance(self):
        assert rel.natureza("Questão sobre o art. 33", "Cancelado", "RR") == "tema cancelado"
        assert rel.natureza("Questão", "Revisado", "RR") == "tese revisada"
        assert "tema cancelado" not in rel.ALCANCE and "tese revisada" in rel.ALCANCE

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
        texto = rel.montar_relatorio([a], {"STF": 14, "STJ": 3}, date(2026, 10, 17), date(2026, 10, 25), {})
        assert "Tema 113 de repercussão geral" in texto and "paradigma: 583523" in texto
        assert "toca registro(s) do catálogo" in texto and "o silêncio dele não prova nada" in texto

    def test_janela_no_teto_avisa(self):
        texto = rel.montar_relatorio([], {"STF": rel.LIMITE}, date(2025, 10, 25), date(2026, 10, 25), {})
        assert "o que veio além não foi lido" in texto

    def test_cnj_fora_do_ar_nao_e_silencio(self):
        texto = rel.montar_relatorio([], {}, date(2026, 10, 17), date(2026, 10, 25),
                                     {"STF": "timeout", "STJ": "timeout"})
        assert "não pôde ser lido para o STF" in texto and "para o STJ" in texto

    def test_um_tribunal_fora_do_ar_nao_cala_o_outro(self, idx):
        a = rel.avaliar(_um("cnj-stj-tema-1087.json"), *idx, CHAVES)
        texto = rel.montar_relatorio([a], {"STJ": 5}, date(2026, 10, 17), date(2026, 10, 25), {"STF": "timeout"})
        assert "para o STF: timeout" in texto and "Tema 1087 dos repetitivos do STJ" in texto
        assert rel.codigo_de_saida([a], {"STF": "timeout"}) == 2

    def test_corpo_da_issue_tem_teto(self):
        muitos = [{"rotulo": f"Súmula {i} do STF", "natureza": "outra", "fontes": {"cp": ["1"]}, "ids": [1],
                   "paradigmas": [], "texto": "x", "a_ler": True} for i in range(rel.A_MOSTRAR + 5)]
        texto = rel.montar_relatorio(muitos, {"STF": 734}, date(2026, 10, 17), date(2026, 10, 25), {})
        assert "_e mais 5, no `tribunais-2026-10-25.json` do artifact._" in texto
