# -*- coding: utf-8 -*-
"""O Cotejador, frentes 4 e 5: vetos do ano e histórico legislativo, sem rede."""
import json
from datetime import date

from conftest import FIXTURES
from cotejador import historico, vetos
from fontes import senado

FONTES = [{"id": "cp", "urn": "urn:lex:br:federal:decreto.lei:1940-12-07;2848"},
          {"id": "lep", "urn": "urn:lex:br:federal:lei:1984-07-11;7210"},
          {"id": "lc64", "urn": "urn:lex:br:federal:lei.complementar:1990-05-18;64"},
          {"id": "cf", "urn": "urn:lex:br:federal:constituicao:1988-10-05;1988"}]


class TestVetos:
    def test_le_a_lista_do_senado(self):
        vs = senado.ler_vetos(json.loads((FIXTURES / "senado-vetos-2026.json").read_text(encoding="utf-8")))
        v52 = next(v for v in vs if v.numero == "52/2026")
        assert v52.em_tramitacao and not v52.total
        assert "Decreto-Lei nº 2.848" in v52.ementa

    def test_padroes_casam_a_citacao_do_diploma(self):
        p = vetos.padroes(FONTES)
        assert p["cp"].search("Altera o Decreto-Lei nº 2.848, de 7 de dezembro de 1940")
        assert p["lep"].search("e a Lei nº 7.210, de 11 de julho de 1984")
        assert p["lc64"].search("altera a Lei Complementar nº 64, de 18 de maio de 1990")
        # "Lei nº 2.848" não é o Decreto-Lei nº 2.848, e 7.2101 não é 7.210.
        assert not p["lep"].search("Lei nº 7.2101")

    def test_so_os_vetos_que_tocam_diploma_vigiado(self):
        vs = senado.ler_vetos(json.loads((FIXTURES / "senado-vetos-2026.json").read_text(encoding="utf-8")))
        achados = vetos.vetos_que_tocam(vs, vetos.padroes(FONTES))
        assert achados and all(a["fontes"] for a in achados)
        texto = vetos.montar_relatorio(2026, achados, None, date(2026, 10, 25))
        assert "VET 52/2026" in texto and "em tramitação" in texto

    def test_lista_ilegivel_e_dita(self):
        assert "não pôde ser lida" in vetos.montar_relatorio(2026, [], "timeout", date(2026, 10, 25))


class TestHistorico:
    def _lei(self, nome, dia, *unidades):
        itens = tuple(senado.Item(u, u, "Alteração") for u in unidades)
        return senado.Posterior(nome, None, dia, senado.ALTERACAO_PERMANENTE, itens)

    def _ficha(self, *posteriores):
        return senado.Norma("1", "Lei nº 7.210", None, None, "", posteriores)

    def test_chave_da_norma(self):
        assert historico.chave_da_norma("Lei nº 15.402") == ("lei", "15402")
        assert historico.chave_da_norma("Lei nº 15.402 de 08/05/2026") == ("lei", "15402")
        assert historico.chave_da_norma("Lei Complementar nº 224") == ("lei complementar", "224")
        assert historico.chave_da_norma("original") is None

    def test_os_dois_sentidos(self):
        eventos = [
            {"dispositivo": "lep|art. 112, i", "evento": "alteracao", "norma": "Lei nº 15.402"},
            {"dispositivo": "lep|art. 112, ii", "evento": "criacao", "norma": "Lei nº 13.964"},
            {"dispositivo": "lep|art. 52, caput", "evento": "criacao", "norma": "original"},
        ]
        ficha = self._ficha(self._lei("Lei nº 15.402 de 08/05/2026", date(2026, 5, 8), "art. 112"),
                            self._lei("Lei nº 15.410 de 20/05/2026", date(2026, 5, 20), "art. 52, §8º"))
        c = historico.cruzar("lep", eventos, ficha)
        # 13.964 não está no Senado: o Senado não registra.
        assert [x["norma"] for x in c["senado_nao_registra"]] == ["Lei nº 13.964"]
        # 15.410 tocou o art. 52, que o histórico acompanha, sem evento lá.
        assert [(x["dispositivo"], x["norma"]) for x in c["historico_nao_registra"]] == \
            [("lep|art. 52, §8º", "Lei nº 15.410 de 20/05/2026")]

    def test_superada_nao_vira_lacuna_do_historico(self):
        eventos = [{"dispositivo": "lep|art. 52, caput", "evento": "alteracao", "norma": "Lei nº 15.410"}]
        ficha = self._ficha(self._lei("Lei nº 10.792 de 01/12/2003", date(2003, 12, 1), "art. 52"),
                            self._lei("Lei nº 15.410 de 20/05/2026", date(2026, 5, 20), "art. 52"))
        assert historico.cruzar("lep", eventos, ficha)["historico_nao_registra"] == []
