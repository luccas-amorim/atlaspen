# -*- coding: utf-8 -*-
"""O Curador (`curador/`), sem rede: a triagem no Markdown do ctresb/leis, a
confirmação no HTML do Planalto e a varredura com estado. Os trechos imitam os
arquivos reais lidos em 26/10/2026."""
from datetime import date

import pytest

from curador import confirmar, triagem, varrer
from fontes.rede import FalhaDeRede

FRONT = ('---\ntitulo: "Lei nº {n} de 01/01/{a}"\ntipo: "Lei Ordinária"\nnumero: "{n}"\n'
         'ementa: "{e}"\nrevogada: {r}\nurn: "urn:lex:br:federal:lei:{a}-01-01;{n}"\n---\n')


def md(n, a, corpo, e="Ementa.", r="false"):
    return FRONT.format(n=n, a=a, e=e, r=r) + corpo


class TestChaves:
    def test_chave_do_arquivo_e_da_urn(self):
        assert triagem.chave_do_arquivo("lei-4737-1965-07-15.md") == "lei-4737-1965"
        assert triagem.chave_do_arquivo("del-2848-1940-12-07.md") == "del-2848-1940"
        assert triagem.chave_do_arquivo("README.md") is None
        assert triagem.chave_da_urn("urn:lex:br:federal:decreto.lei:1940-12-07;2848") == "del-2848-1940"
        assert triagem.chave_da_urn("urn:lex:br:federal:constituicao:1988-10-05;1988") is None

    def test_chaves_da_norma(self):
        assert triagem.chaves_da_norma("Lei nº 1.521, de 26 de dezembro de 1951") == {"lei-1521-1951"}
        assert triagem.chaves_da_norma("Decreto-Lei nº 201/1967") == {"del-201-1967"}
        assert triagem.chaves_da_norma("Lei Complementar nº 64/1990") == {"lcp-64-1990"}
        # Os excluídos vêm em texto livre.
        assert triagem.chaves_da_norma("Lei nº 8.072/1990, Lei nº 9.099/1995, LEP (7.210/1984), CPP") == \
            {"lei-8072-1990", "lei-9099-1995", "lei-7210-1984"}

    def test_conhecidos(self):
        k = triagem.conhecidos(
            [{"id": "cp", "urn": "urn:lex:br:federal:decreto.lei:1940-12-07;2848"}],
            {"diplomas": [{"id": "lei1164", "norma": "Lei nº 1.164, de 24 de julho de 1950"}],
             "excluidos": [{"norma": "Lei nº 1.079/1950 (crimes de responsabilidade)"}]},
            {"registros": [{"id": "x", "normas": [{"norma": "Lei nº 6.815/1980"}]}]})
        assert set(k) == {"del-2848-1940", "lei-1164-1950", "lei-1079-1950", "lei-6815-1980"}


class TestTriagem:
    def test_pena_propria(self):
        t = triagem.triar("federal/leis-ordinarias/1951/lei-1521-1951-12-26.md",
                          md(1521, 1951, "**Art. 2º** São crimes...\n\nPena – detenção, de seis meses a dois anos."))
        assert t.chave == "lei-1521-1951" and t.pena_propria and not t.pena_citada and t.revogada is False

    def test_pena_so_citada_nao_aponta(self):
        # Lei 13.964/2019: a pena está no texto que ela dá ao CP, entre aspas.
        corpo = ("**Art. 2º** O Decreto-Lei nº 2.848 passa a vigorar com as seguintes alterações:\n\n"
                 "“**Art. 121.** ...\n\nPena – reclusão, de doze a trinta anos.” (NR)\n")
        t = triagem.triar("federal/leis-ordinarias/2019/lei-13964-2019-12-24.md", md(13964, 2019, corpo))
        assert not t.pena_propria and t.pena_citada

    def test_forma_antiga_so_antes_de_1941(self):
        corpo = "Art. 2º Incorrerá na pena de prisão cellular por um a seis mezes quem..."
        antiga = triagem.triar("federal/leis-ordinarias/1921/lei-4242-1921-01-05.md", md(4242, 1921, corpo))
        assert antiga.pena_propria
        moderna = triagem.triar("federal/leis-ordinarias/1990/lei-8000-1990-01-01.md",
                                md(8000, 1990, "O infrator incorrerá na pena de multa de cem reais."))
        assert not moderna.pena_propria       # "pena de multa" moderna é sanção administrativa

    def test_sem_pena(self):
        t = triagem.triar("federal/leis-ordinarias/1965/lei-4596-1965-02-22.md",
                          md(4596, 1965, "Isenta do impôsto de importação."))
        assert not t.pena_propria and not t.pena_citada


def _pagina(cabecalho, corpo):
    return (f"<html><head><style>p{{}}</style></head><body><p>Presidência da República</p>"
            f"<p>{cabecalho}</p>{corpo}</body></html>").encode("utf-8")


class TestConfirmacao:
    def test_enderecos_por_epoca(self):
        assert confirmar.enderecos("lei", 1521, 1951)[0] == "leis/l1521.htm"
        assert confirmar.enderecos("lei", 38, 1935)[0] == "leis/1930-1949/L0038.htm"
        assert "leis/2003/L10.826.htm" in confirmar.enderecos("lei", 10826, 2003)
        assert "decreto-lei/Del0201.htm" in confirmar.enderecos("del", 201, 1967)
        assert confirmar.enderecos("lei", 15400, 2026)[0] == "_ato2023-2026/2026/lei/l15400.htm"
        assert "leis/lim/LIM3353.htm" in confirmar.enderecos("lei", 3353, 1888)
        assert "leis/1970-1979/L6620.htm" in confirmar.enderecos("lei", 6620, 1978)
        assert "_ato2004-2006/2004/lei/l10.886.htm" in confirmar.enderecos("lei", 10886, 2004)

    def test_cabecalho_confere_ano_e_numero(self):
        t = "Casa Civil LEI Nº 1.521, DE 26 DE DEZEMBRO DE 1951. Altera dispositivos"
        assert confirmar.cabecalho_confere(t, "lei", 1521, 1951)
        assert not confirmar.cabecalho_confere(t, "lei", 1521, 1950)
        assert not confirmar.cabecalho_confere(t, "lei", 152, 1951)
        assert confirmar.cabecalho_confere("DECRETO-LEI Nº 201, DE 27 DE FEVEREIRO DE 1967.", "del", 201, 1967)
        assert not confirmar.cabecalho_confere("LEI COMPLEMENTAR Nº 64, DE 18 DE MAIO DE 1990", "lei", 64, 1990)

    def test_a_lei_homonima_de_outro_ano_nao_serve(self):
        # A Lei 4.242 existe em 1921 e em 1963; `leis/l4242.htm` é a de 1963.
        paginas = {confirmar.PLANALTO + "leis/l4242.htm":
                   _pagina("LEI Nº 4.242, DE 17 DE JULHO DE 1963.", "<p>Pena – detenção, de um a dois anos.</p>")}
        r = confirmar.confirmar("lei-4242-1921", obter=paginas.get, pausa=0, dia=date(2026, 10, 26))
        assert r["estado"] == "sem_pagina"
        r = confirmar.confirmar("lei-4242-1963", obter=paginas.get, pausa=0)
        assert r["estado"] == "pena_vigente" and r["url"].endswith("leis/l4242.htm")

    @pytest.mark.parametrize("corpo, esperado", [
        ("<p>Art. 1º Pena – reclusão, de dois a seis anos.</p>", "pena_vigente"),
        ("<p><strike>Art. 1º Pena – reclusão, de dois a seis anos.</strike></p><p>Art. 2º Revogado.</p>",
         "pena_riscada"),
        ("<p>(Revogada pela Lei nº 14.785, de 2023)</p><p>Pena – reclusão, de dois a quatro anos.</p>",
         "revogada"),
        ("<p>Art. 1º Fica isento o equipamento.</p>", "sem_pena"),
        ("<p>“Art. 121. Pena – reclusão, de seis a vinte anos.” (NR)</p>", "sem_pena"),
    ])
    def test_classificar(self, corpo, esperado):
        paginas = {confirmar.PLANALTO + "leis/l7802.htm": _pagina("LEI Nº 7.802, DE 11 DE JULHO DE 1989.", corpo)}
        assert confirmar.confirmar("lei-7802-1989", obter=paginas.get, pausa=0)["estado"] == esperado

    def test_planalto_fora_do_ar_nao_vira_sem_pagina(self):
        def caiu(url):
            raise FalhaDeRede(url, 2, TimeoutError())
        with pytest.raises(FalhaDeRede):
            confirmar.confirmar("lei-1521-1951", obter=caiu, pausa=0)


class TestVarredura:
    def test_so_le_o_ano_que_mudou(self):
        estado = {"1950": {"arvore": "aaa"}, "1951": {"arvore": "bbb"}}
        assert varrer.anos_a_ler({"1888": "x", "1950": "aaa", "1951": "novo", "1952": "c", "_lotes": "z"},
                                 estado) == {"1951": "novo", "1952": "c"}

    def test_ler_ano(self):
        from fontes.ctresb import Arquivo
        arquivos = [Arquivo("federal/leis-ordinarias/1951/lei-1521-1951-12-26.md", "s1"),
                    Arquivo("federal/leis-ordinarias/1951/lei-1522-1951-12-27.md", "s2"),
                    Arquivo("federal/leis-ordinarias/1951/lei-1523-1951-12-28.md", "s3")]
        textos = {arquivos[0].caminho: md(1521, 1951, "Pena – detenção, de seis meses a dois anos."),
                  arquivos[1].caminho: md(1522, 1951, "Isenta.")}

        def ler(caminho, commit):
            if caminho not in textos:
                raise FalhaDeRede(caminho, 2, TimeoutError())
            return textos[caminho]
        contagem, apontadas, falhas = varrer.ler_ano("lei", "1951", "arv", "c0", ler=ler,
                                                      listar=lambda c, a: arquivos)
        assert contagem["arquivos"] == 3 and contagem["pena_propria"] == 1
        assert contagem["nao_lidos"] == 1 and contagem["arvore"] is None    # volta no mês seguinte
        assert [t.chave for t in apontadas] == ["lei-1521-1951"] and len(falhas) == 1


class TestCurar:
    @staticmethod
    def _estado():
        return {"apontadas": {
            "lei-38-1935": {"caminho": "federal/leis-ordinarias/1935/lei-38-1935-04-04.md", "ementa": "Define crimes.",
                            "planalto": {"estado": "pena_vigente", "url": "u", "conferido_em": "2026-01-01"}},
            "lei-90-1936": {"caminho": "c", "ementa": "", "planalto": {"estado": "sem_pena",
                                                                       "conferido_em": "2026-10-01"}},
            "lei-91-1936": {"caminho": "c", "ementa": ""},
        }, "anos": {"lei": {"1935": {"arquivos": 141}, "1936": {"arquivos": 171}}},
            "senado": {"lei": {"1935": 141, "1936": 200}, "dec": {"1931": 1328}}}

    def test_a_confirmar_novas_e_vencidas(self):
        from curador import curar
        assert curar.a_confirmar(self._estado(), date(2026, 10, 26), 10) == ["lei-91-1936", "lei-38-1935"]
        assert curar.a_confirmar(self._estado(), date(2026, 10, 26), 1) == ["lei-91-1936"]

    def test_mudanca_de_estado_e_queda(self):
        from curador import curar
        estado = self._estado()

        def conf(c, dia):
            if c == "lei-91-1936":
                raise FalhaDeRede(c, 2, TimeoutError())
            return {"estado": "revogada", "url": "u", "indicio": "Revogada pela Lei nº 1.802, de 1953",
                    "conferido_em": dia.isoformat()}
        primeiras, mudaram, avisos = curar.rodar_confirmacoes(estado, ["lei-38-1935", "lei-91-1936"],
                                                             date(2026, 10, 26), conf)
        assert primeiras == [] and mudaram == ["lei-38-1935"] and "não respondeu" in avisos[0]
        assert "planalto" not in estado["apontadas"]["lei-91-1936"]        # queda não vira estado

    def test_lacunas_e_relatorio(self):
        from curador import curar
        estado = self._estado()
        assert curar.lacunas(estado) == [("lei", "1936", 171, 200), ("dec", "1931", 0, 1328)]
        texto = curar.montar_relatorio(estado, ["lei-38-1935"], [], [], date(2026, 10, 26))
        assert "**Lei nº 38/1935** — pena vigente" in texto and "anteriores a 1942" in texto
        assert "Decretos de 1931: 0 no ctresb, 1328 no Senado" in texto

    def test_codigos(self):
        from curador import curar
        estado = self._estado()
        assert curar.codigo_de_saida(["lei-38-1935"], [], estado, True) == 3
        assert curar.codigo_de_saida(["lei-90-1936"], [], estado, True) == 0     # sem pena não pede leitura
        assert curar.codigo_de_saida([], ["lei-90-1936"], estado, True) == 3
        assert curar.codigo_de_saida([], [], estado, False) == 2


def test_tres_anos_sem_leitura_encerram_a_especie(monkeypatch):
    from fontes import ctresb
    chamados = []
    monkeypatch.setattr(ctresb, "subpastas", lambda c, commit: {str(a): f"s{a}" for a in range(1950, 1960)})

    def caiu(especie, ano, arvore, commit):
        chamados.append(ano)
        raise FalhaDeRede("api", 2, OSError("HTTP Error 403: rate limit exceeded"))
    monkeypatch.setattr(varrer, "ler_ano", caiu)
    estado = {}
    novos, avisos = varrer.varrer(estado, {}, "c0", especies=("lei",), progresso=lambda m: None)
    assert chamados == ["1950", "1951", "1952"] and "anos seguidos sem leitura" in avisos[-1]
    assert estado["anos"]["lei"] == {}        # nada lido, nada gravado: a próxima rodada relê


def test_primeira_confirmacao_e_alteradora():
    from curador import curar
    estado = {"apontadas": {
        "lei-6416-1977": {"caminho": "c", "ementa": "Altera dispositivos do Código Penal (Decreto-lei nº 2.848, "
                                                    "de 7 de dezembro de 1940)."},
        "lei-7653-1988": {"caminho": "c", "ementa": "Altera a redação dos arts. 18 e 27 da Lei nº 5.197, de 03 de "
                                                    "janeiro de 1967."},
        "lei-9966-2000": {"caminho": "c", "ementa": "Dispõe sobre a poluição por óleo."}}}
    conf = lambda c, dia: {"estado": "pena_vigente", "url": "u", "indicio": None, "conferido_em": "2026-10-26"}
    primeiras, mudaram, _ = curar.rodar_confirmacoes(estado, sorted(estado["apontadas"]), date(2026, 10, 26), conf)
    assert primeiras == sorted(estado["apontadas"]) and mudaram == []
    curar.marcar_alteradoras(estado, {"del-2848-1940": "fontes.json (cp)"})
    assert estado["apontadas"]["lei-6416-1977"]["altera"] == ["del-2848-1940"]
    assert "altera" not in estado["apontadas"]["lei-7653-1988"]      # a Lei 5.197/67 o projeto não vigia
    texto = curar.montar_relatorio(estado, primeiras, [], [], date(2026, 10, 26))
    assert "Alteram diploma que o projeto já vigia" in texto and "Lei nº 6.416/1977" in texto
    assert "desde 1942 — candidatas" in texto and "**Lei nº 9.966/2000**" in texto
    # A alteradora não abre issue sozinha.
    assert curar.codigo_de_saida(["lei-6416-1977"], [], estado, True) == 0
    assert curar.codigo_de_saida(["lei-9966-2000"], [], estado, True) == 3


def test_so_multa_e_sem_prisao():
    pagina = _pagina("LEI Nº 11.771, DE 17 DE SETEMBRO DE 2008.",
                     "<p>Pena - multa e interdição do local e atividade.</p>")
    r = confirmar.confirmar("lei-11771-2008", obter={confirmar.PLANALTO + "_ato2007-2010/2008/lei/l11771.htm": pagina}.get,
                            pausa=0)
    assert r["estado"] == "sem_prisao"
