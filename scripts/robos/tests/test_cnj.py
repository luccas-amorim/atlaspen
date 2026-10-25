# -*- coding: utf-8 -*-
"""O cliente do Banco Nacional de Precedentes do CNJ (`fontes/cnj.py`), sem rede.

As fixtures `cnj-*.json` são respostas reais de 25/10/2026: o Tema 113 (LCP,
art. 25, não recepcionado), a ADPF 496 (desacato, recepcionado) e a janela de
precedentes atualizados desde 17/10/2026, recortada.
"""
import json
from datetime import date

from conftest import FIXTURES
from fontes import cnj


def _json(nome):
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def test_tema_de_repercussao_geral():
    p = cnj.ler_resultados(_json("cnj-tema-113.json"))[0]
    assert p.id == "stf-rg-113" and p.tipo == "RG" and p.numero == "113"
    assert p.rotulo == "Tema 113 de repercussão geral"
    assert "não foi recepcionado pela Constituição de 1988" in p.texto
    assert p.paradigmas == ("583523",)
    assert p.ato_impugnado == ""            # tema não traz o ato codificado


def test_controle_concentrado():
    p = cnj.ler_resultados(_json("cnj-adpf-496.json"))[0]
    assert p.rotulo == "ADPF 496" and p.decisao == "EMBARGOS_DE_DECLARACAO"
    assert "LEG-FED DEL-002848 ANO-1940 ART-00331" in p.ato_impugnado
    assert p.atualizado_em == date(2022, 10, 24)
    assert "desacato" in p.texto


def test_janela():
    ps = cnj.ler_resultados(_json("cnj-janela.json"))
    assert len(ps) == 5 and {p.tipo for p in ps} == {"RG", "ADI"}
    assert all(p.atualizado_em and p.atualizado_em >= date(2026, 10, 17) for p in ps)


def test_filtro_usa_data_brasileira(monkeypatch):
    """Em ISO o CNJ ignora o filtro e devolve o banco inteiro (6.702 em 25/10/2026)."""
    enviados = []

    def falso(f):
        enviados.append(f)
        return {"total": 1, "resultados": _json("cnj-tema-113.json")["resultados"]}
    monkeypatch.setattr(cnj, "_consultar", falso)
    ps = cnj.atualizados_desde(date(2026, 10, 17))
    assert enviados[0]["atualizacaoDesde"] == "17/10/2026"
    assert enviados[0]["orgaos"] == ["STF"] and "RG" in enviados[0]["tipos"]
    assert [p.id for p in ps] == ["stf-rg-113"]


def test_pagina_enquanto_houver(monkeypatch):
    um = _json("cnj-tema-113.json")["resultados"][0]
    paginas = {1: [um] * 50, 2: [um] * 50, 3: [um] * 7}

    def falso(f):
        return {"total": 107, "resultados": paginas[f["pagina"]]}
    monkeypatch.setattr(cnj, "_consultar", falso)
    assert len(cnj.atualizados_desde(date(2026, 10, 17))) == 107


def test_resposta_sem_resultados_e_erro(monkeypatch):
    import pytest
    monkeypatch.setattr(cnj.REDE, "obter", lambda *a, **k: b'{"erro": "x"}')
    with pytest.raises(ValueError):
        cnj.por_numero("RG", "113")
