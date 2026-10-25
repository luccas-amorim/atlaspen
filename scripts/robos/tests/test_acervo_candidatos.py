# -*- coding: utf-8 -*-
"""Os candidatos ao acervo histórico (`acervo/candidatos.py`), sem rede.

O caso do CP é o que mudou o critério: o compilado não guarda o riscado do
artigo revogado ("Art. 240 - (Revogado pela Lei nº 11.106, de 2005)"), e a
prova de pena tem de vir do original. O da LCP é o contrário: o texto e a pena
ficam no lugar, riscados.
"""
from acervo import candidatos as c
from fontes import senado

CP_240 = """
<p><b>Adultério</b></p>
<p>Art. 240 - <a href="../_Ato2004-2006/2005/Lei/L11106.htm#art5">(Revogado pela Lei nº 11.106, de 2005)</a></p>
<p>Art. 241 - Promover no registro civil a inscrição de nascimento inexistente:</p>
<p>Pena - reclusão, de dois a seis anos.</p>
"""
CP_51 = """
<p>Art. 51 - Transitada em julgado a sentença condenatória, a multa será considerada dívida de valor.</p>
<p>§ 1º - <a href="../LEIS/L9268.htm#art1">(Revogado pela Lei nº 9.268, de 1º.4.1996)</a></p>
"""
ORIGINAL_CP = ("Art. 240. Cometer adultério: Pena - detenção, de quinze dias a seis meses. "
               "Art. 241. Promover no registro civil a inscrição de nascimento inexistente: "
               "Pena - reclusão, de dois a seis anos.")
FONTE_CP = {"id": "cp", "urn": "urn:lex:br:federal:decreto.lei:1940-12-07;2848"}
FONTE_LCP = {"id": "lcp", "urn": "urn:lex:br:federal:decreto.lei:1941-10-03;3688"}


class TestNivel:
    def test_cp_sem_riscado_vai_pelo_original(self):
        achados = c.levantar_fonte(FONTE_CP, CP_240, "cp", [[121, 361]], set(),
                                   c.segmentos_do_original(ORIGINAL_CP))
        art240 = next(a for a in achados if a["id"] == "cp-240")
        assert art240["nome"] == "Adultério"
        assert art240["norma"] == "Lei nº 11.106" and art240["ano"] == 2005
        assert art240["nivel"] == "pena_no_original"
        assert art240["trecho_original"].startswith("Art. 240. Cometer adultério")

    def test_sem_original_pede_juizo(self):
        achados = c.levantar_fonte(FONTE_CP, CP_240, "cp", [[121, 361]], set(), None)
        assert next(a for a in achados if a["id"] == "cp-240")["nivel"] == "pede_juizo"

    def test_lcp_mantem_a_pena_riscada_no_compilado(self, carregar):
        achados = c.levantar_fonte(FONTE_LCP, carregar("lcp-art65-revogado"), "lcp", [[18, 70]],
                                   set(), None)
        art65 = next(a for a in achados if a["id"] == "lcp-65")
        assert art65["nivel"] == "pena_no_compilado"

    def test_paragrafo_nao_herda_a_pena_do_caput_no_original(self):
        """O original é segmentado por artigo: a pena do caput não prova o parágrafo."""
        html = """<p>Art. 240 - Cometer adultério:</p><p>Pena - detenção, de quinze dias a seis meses.</p>
        <p>§ 1º - <a href="x">(Revogado pela Lei nº 11.106, de 2005)</a></p>"""
        achados = c.levantar_fonte(FONTE_CP, html, "cp", [[121, 361]], set(),
                                   c.segmentos_do_original(ORIGINAL_CP))
        assert next(a for a in achados if a["id"] == "cp-240-p1")["nivel"] == "pede_juizo"

    def test_titulo_de_secao_nao_e_nome_de_crime(self):
        assert c._nome("DISPOSIÇÕES GERAIS") is None
        assert c._nome("Adultério") == "Adultério"

    def test_parte_geral_fica_fora_do_intervalo(self):
        achados = c.levantar_fonte(FONTE_CP, CP_51, "cp", [[121, 361]], set(), None)
        assert [(a["id"], a["nivel"]) for a in achados] == [("cp-51-p1", "fora_do_intervalo")]


class TestIds:
    def test_formas(self):
        assert c.id_no_acervo("cp", "Art. 240", "caput") == "cp-240"
        assert c.id_no_acervo("cp", "Art. 150", "§ 2º") == "cp-150-p2"
        assert c.id_no_acervo("cp", "Art. 121", "§ 2º-A") == "cp-121-p2a"
        assert c.id_no_acervo("lei4595", "Art. 44", "§ 7º") == "lei4595-44-p7"
        assert c.id_no_acervo("cp", "Art. 218-B", "caput") == "cp-218b"

    def test_ja_registrados(self):
        acervo = {"registros": [
            {"id": "cp-219-222", "artigos": ["cp-219", "cp-220", "cp-221", "cp-222"]},
            {"id": "cp-150-p2", "artigos": ["cp-150"]}]}
        r = c.ja_registrados(acervo)
        assert {"cp-219", "cp-222", "cp-150-p2"} <= r
        # O registro do §2º não cobre o artigo inteiro.
        assert "cp-150" not in r

    def test_o_que_o_acervo_ja_tem_sai_marcado(self):
        achados = c.levantar_fonte(FONTE_CP, CP_240, "cp", [[121, 361]], {"cp-240"}, None)
        assert next(a for a in achados if a["id"] == "cp-240")["ja_no_acervo"]


class TestOriginal:
    def test_segmenta_por_artigo(self):
        seg = c.segmentos_do_original(ORIGINAL_CP)
        assert set(seg) == {"240", "241"}
        assert "Pena - detenção" in seg["240"] and "reclusão" not in seg["240"]


class TestMapa:
    def test_fonte_casa_com_o_inventario_pela_urn(self):
        meta = {"cp": {"norma": "Decreto-Lei nº 2.848, de 7 de dezembro de 1940", "faixas": [[121, 361]]},
                "lei7170": {"norma": "Lei nº 7.170, de 14 de dezembro de 1983", "situacao": "revogado"}}
        mapa = c.diplomas_do_inventario(meta)
        assert c.diploma_da_fonte(FONTE_CP, mapa) == ("cp", [[121, 361]])
        # Revogado no inventário não tem faixa nem é fonte.
        assert ("lei", 7170) not in mapa

    def test_sem_urn_nao_casa(self):
        assert c.diploma_da_fonte({"id": "x"}, {}) is None


class TestDiplomasRevogadosNoTodo:
    def _ficha(self, *anteriores):
        return senado.Norma("1", "Lei nº 13.869 de 05/09/2019", None, None, "", (), anteriores)

    def test_o_que_diplomas_json_ja_tem_nao_volta(self):
        a = senado.Anterior("1", "Lei nº 4.898 de 09/12/1965", senado.REVOGACAO_NO_TODO, ())
        diplomas = {"diplomas": [{"norma": "Lei nº 4.898, de 9 de dezembro de 1965"}]}
        assert c.revogados_no_todo({"abuso": self._ficha(a)}, c.diplomas_ja_registrados(diplomas)) == []

    def test_o_que_falta_vira_candidato(self):
        a = senado.Anterior("77", "Lei nº 1.234 de 01/01/1960", senado.REVOGACAO_NO_TODO, ())
        alt = senado.Anterior("78", "Lei nº 9.296 de 24/07/1996", senado.ALTERACAO_PERMANENTE, ())
        saida = c.revogados_no_todo({"abuso": self._ficha(a, alt)}, set())
        assert [d["nome"] for d in saida] == ["Lei nº 1.234 de 01/01/1960"]
        assert saida[0]["codigo"] == "77" and saida[0]["revogada_por"].startswith("Lei nº 13.869")


class TestPropostas:
    def test_so_os_niveis_com_pena_e_no_formato_do_acervo(self):
        cand = [
            {"id": "cp-240", "dispositivo": "Art. 240", "nome": "Adultério", "diploma": "cp",
             "norma": "Lei nº 11.106", "ano": 2005, "nivel": "pena_no_original", "ja_no_acervo": False},
            {"id": "cp-51-p1", "dispositivo": "Art. 51, § 1º", "nome": None, "diploma": "cp",
             "norma": "Lei nº 9.268", "ano": 1996, "nivel": "fora_do_intervalo", "ja_no_acervo": False},
        ]
        p = c.propostas(cand)
        assert [x["id"] for x in p] == ["cp-240"]
        assert p[0]["normas"] == [{"norma": "Lei 11.106/2005", "ano": 2005}]
        assert p[0]["texto_original"] is None and p[0]["data_revogacao"] is None
        assert p[0]["categoria"] == "revogado"
