# -*- coding: utf-8 -*-
"""O ctresb/leis só observado (`fontes/ctresb.py`, `cotejador/ctresb.py`), sem rede."""
from datetime import date

from cotejador import ctresb as rel
from fontes import ctresb
from fontes.rede import FalhaDeRede


def test_caminho_da_urn():
    assert ctresb.caminho_da_urn("urn:lex:br:federal:lei:1984-07-11;7210") == \
        "federal/leis-ordinarias/1984/lei-7210-1984-07-11.md"
    assert ctresb.caminho_da_urn("urn:lex:br:federal:decreto.lei:1940-12-07;2848") == \
        "federal/decretos-lei/1940/del-2848-1940-12-07.md"
    assert ctresb.caminho_da_urn("urn:lex:br:federal:lei.complementar:1990-05-18;64") == \
        "federal/leis-complementares/1990/lcp-64-1990-05-18.md"
    assert ctresb.caminho_da_urn("urn:lex:br:federal:constituicao:1988-10-05;1988") == "constituicao.md"
    assert ctresb.caminho_da_urn("lixo") is None


def test_ler_commits_da_api():
    dados = [{"sha": "deea03bfc8fe954f274dd93b92c8266cf45946f9", "html_url": "https://x",
              "commit": {"message": "scripts: rede com limite\n\ncorpo", "author": {"date": "2026-10-20T12:00:00Z"}}}]
    c = ctresb.ler_commits(dados)[0]
    assert c.sha == "deea03bfc8fe" and c.data == "2026-10-20" and c.mensagem == "scripts: rede com limite"


def test_rodar_separa_codigo_e_diplomas_e_nao_quebra():
    c = ctresb.Commit("abc", "2026-10-20", "lep: recompila", "https://x")

    def ler(caminho, desde):
        if caminho == "scripts":
            raise FalhaDeRede(caminho, 2, TimeoutError())
        return [c] if "7210" in caminho else []
    fontes = [{"id": "lep", "urn": "urn:lex:br:federal:lei:1984-07-11;7210"},
              {"id": "cp", "urn": "urn:lex:br:federal:decreto.lei:1940-12-07;2848"}]
    r = rel.rodar(fontes, "2026-10-17", ler=ler)
    assert [d["id"] for d in r["diplomas"]] == ["lep"]
    assert r["nao_lidos"] and "scripts" in r["nao_lidos"][0]
    texto = rel.montar_relatorio(r, date(2026, 10, 25))
    assert "Só observação" in texto and "`lep`" in texto and "Não deu para ler" in texto


def test_rodar_le_a_jurisprudencia():
    s = ctresb.Commit("def", "2026-10-20", "Atualiza versões oficiais STF", "https://y")

    def ler(caminho, desde):
        if caminho == "jurisprudencia/stj":
            raise FalhaDeRede(caminho, 2, TimeoutError())
        return [s] if caminho == "jurisprudencia/stf" else []
    r = rel.rodar([], "2026-10-17", ler=ler)
    assert list(r["jurisprudencia"]) == ["jurisprudencia/stf"]
    assert any("jurisprudencia/stj" in x for x in r["nao_lidos"])
    texto = rel.montar_relatorio(r, date(2026, 10, 25))
    assert "**1** na jurisprudência" in texto and "pista para o Relator" in texto
    assert "`jurisprudencia/stf/` — Atualiza versões oficiais STF" in texto
