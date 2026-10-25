# -*- coding: utf-8 -*-
"""Testes do cliente da API de Dados Abertos do Senado (`fontes/senado.py`).

Sem rede: as fixtures `senado-*.json` são recortes de respostas reais de
25/10/2026, com a estrutura intacta e só os itens que os testes usam.
"""
import json
from datetime import date

import pytest

from conftest import FIXTURES
from fontes import senado


def _json(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


class TestUnidade:
    @pytest.mark.parametrize("senado_escreve, canonica", [
        ("Art. 66, caput, Inciso 5, Alínea j", "art. 66, v, j"),
        ("Art. 112, § 1", "art. 112, §1º"),
        ("Art. 112, caput, Inciso 6-A", "art. 112, vi-a"),
        ("Art. 41, Parágrafo Único", "art. 41, parágrafo único"),
        ("Art. 146-E, caput", "art. 146-e, caput"),
        ("Art. 9-A", "art. 9-a"),
        ("Art. 121, § 2, Inciso 8", "art. 121, §2º, viii"),
        ("Art. 52, § 10", "art. 52, §10"),
        ("Art. 171, § 2-A", "art. 171, §2º-a"),
        ("Art. 112, caput, Inciso 4 ", "art. 112, iv"),
        ("Art. 154-A, Pena", "art. 154-a"),
        ("Art. 146-A, caput, Pena/Penalidade", "art. 146-a, caput"),
        ("Art. 140, § 3, Pena", "art. 140, §3º"),
        ("Art. 157, § 2, apenas o Caput", "art. 157, §2º"),
    ])
    def test_traduz_para_a_chave_do_historico(self, senado_escreve, canonica):
        assert senado.unidade(senado_escreve) == canonica

    @pytest.mark.parametrize("ilegivel", ["", "Anexo I", "Art. 5, Item 3", "Art. 117, caput, Item 5",
                                          "Parte Geral"])
    def test_o_que_nao_se_le_nao_vira_chave(self, ilegivel):
        assert senado.unidade(ilegivel) is None


class TestFichaDaLep:
    @pytest.fixture
    def lep(self):
        return senado.ler_norma(_json("senado-lep.json"))

    def test_identificacao_e_urn(self, lep):
        assert lep.nome == "Lei nº 7.210 de 11/07/1984"
        assert lep.urn == "urn:lex:br:federal:lei:1984-07-11;7210"
        assert lep.assinatura == date(1984, 7, 11)
        assert lep.ementa == "Institui a Lei de Execução Penal."

    def test_ultima_alteracao_e_a_sentinela_de_hoje(self, lep):
        ult = lep.ultima_alteracao()
        assert ult.numero == "15.410" and ult.assinatura == date(2026, 5, 20)
        assert {i.unidade for i in ult.itens} >= {"art. 52, §8º", "art. 86, §4º"}

    def test_decreto_correlato_nao_e_alteracao(self, lep):
        decreto = next(p for p in lep.posteriores if "Decreto nº 245" in p.nome)
        assert not decreto.permanente
        assert decreto not in lep.alteracoes()

    def test_item_vetado_nao_conta_como_mudanca(self, lep):
        lei = next(p for p in lep.posteriores if p.numero == "15.402" and p.permanente)
        vetados = [i for i in lei.itens if i.vetado]
        assert vetados and all(i.unidade.startswith("art. 112, ") for i in vetados)
        assert all(not i.vetado for i in lei.itens_vigentes())


class TestFichaDoCp:
    def test_sem_vides_os_disps_dao_a_mesma_resposta(self):
        """Às 02:48 de 25/10/2026 a ficha do CP veio sem `vides`."""
        cp = senado.ler_norma(_json("senado-cp-so-disps.json"))
        ult = cp.ultima_alteracao()
        assert ult.nome == "Lei nº 15.517 de 22/09/2026"
        assert ult.assinatura == date(2026, 9, 22)
        assert ult.permanente and ult.especie == "Lei"

    def test_dispositivo_sem_refs_nao_quebra(self):
        cp = senado.ler_norma(_json("senado-cp-so-disps.json"))
        assert all(p.nome for p in cp.posteriores)

    def test_a_classificacao_do_senado_erra_e_o_teste_registra(self):
        """A Lei 11.106/2005 REVOGOU o art. 240, e o Senado diz "Alteração".

        É por isso que nada daqui escreve no catálogo: este teste quebra no dia
        em que o Senado corrigir, e esse dia merece ser notado."""
        cp = senado.ler_norma(_json("senado-cp-so-vides.json"))
        lei = next(p for p in cp.posteriores if p.numero == "11.106")
        art240 = next(i for i in lei.itens if i.unidade == "art. 240")
        assert art240.comentario == "Alteração"

    def test_acordao_e_mensagem_de_veto_nao_sao_a_lei_da_sentinela(self):
        assert not senado.Posterior("Acórdão da Ação Direta de Inconstitucionalidade nº 7.192 de 17/05/2024",
                                    "7.192", date(2024, 5, 17), senado.ALTERACAO_PERMANENTE, ()).legislativa
        assert not senado.Posterior("Mensagem de Veto Parcial nº 216 de 24/03/2026", "216",
                                    date(2026, 3, 24), senado.ALTERACAO_PERMANENTE, ()).legislativa
        assert senado.Posterior("Lei Complementar nº 224 de 26/12/2025", "224", None,
                                senado.ALTERACAO_PERMANENTE, ()).legislativa


def test_lista_do_ano_em_ordem_de_numero():
    leis = senado.ler_lista(_json("senado-lista-2026.json"))
    assert [l.numero for l in leis] == sorted(l.numero for l in leis)
    assert leis[-1].numero == 15526 and leis[-1].assinatura == date(2026, 9, 29)
    assert leis[-1].ementa.startswith("Altera a Lei nº 8.171")


def test_norma_que_nao_existe():
    assert senado.ler_norma({"DetalheDocumento": {"documentos": {}}}) is None


def test_urls():
    assert senado.url_norma("LEI", 7210, 1984).endswith("/legislacao/LEI/7210/1984")
    assert senado.url_urn("urn:lex:br:federal:lei:1984-07-11;7210").endswith(
        "urn=urn:lex:br:federal:lei:1984-07-11;7210")
