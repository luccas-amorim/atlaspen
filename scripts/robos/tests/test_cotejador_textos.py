# -*- coding: utf-8 -*-
"""O Cotejador, frente 2: a moldura do Planalto contra a da Câmara, sem rede."""
from cotejador import textos

PLANALTO = """
<p>Art. 121. Matar alguem:</p>
<p>Pena - reclusão, de seis a vinte anos.</p>
<p>Art. 122. Induzir ou instigar alguém a suicidar-se:</p>
<p>Pena - reclusão, de 6 (seis) meses a 2 (dois) anos.</p>
<p>Art. 123. Matar, sob a influência do estado puerperal, o próprio filho:</p>
<p>Pena - detenção, de dois a seis anos.</p>
"""
# A Câmara com o art. 122 noutra moldura e sem o art. 123.
CAMARA = """
<p>Art. 121. Matar alguém:</p>
<p>Pena - reclusão, de seis a vinte anos.</p>
<p>Art. 122. Induzir ou instigar alguém a suicidar-se:</p>
<p>Pena - reclusão, de 1 (um) a 3 (três) anos.</p>
"""


def test_molduras_dos_dispositivos_com_pena():
    m = textos.molduras(PLANALTO)
    assert set(m) == {"Art. 121|caput", "Art. 122|caput", "Art. 123|caput"}
    assert m["Art. 121|caput"]["min"] == 72 and m["Art. 121|caput"]["max"] == 240


def test_compara_e_conta_o_que_ficou_fora():
    c = textos.comparar(textos.molduras(PLANALTO), textos.molduras(CAMARA))
    assert c["conferem"] == 1
    assert [d["dispositivo"] for d in c["divergentes"]] == ["Art. 122, caput"]
    assert c["so_planalto"] == 1 and c["so_camara"] == 0


def test_relatorio_e_codigo(tmp_path):
    (tmp_path / "cp").mkdir()
    (tmp_path / "cp" / "2026-10-25.html").write_text(PLANALTO, encoding="utf-8")
    v = textos.rodar([{"id": "cp", "urn": "urn:x"}], tmp_path, ler_camara=lambda urn: CAMARA)
    assert textos.codigo_de_saida(v) == 3
    texto = textos.montar_relatorio(v, __import__("datetime").date(2026, 10, 25))
    assert "Planalto **reclusão, 6 a 24 meses**; Câmara **reclusão, 12 a 36 meses**" in texto
    assert "**1** só no Planalto" in texto


def test_diploma_sem_pena_nao_e_cotejado(tmp_path):
    (tmp_path / "lep").mkdir()
    (tmp_path / "lep" / "2026-10-25.html").write_text("<p>Art. 1º A execução penal…</p>", encoding="utf-8")
    assert textos.rodar([{"id": "lep", "urn": "urn:x"}], tmp_path, ler_camara=lambda u: "") == []


def test_camara_sem_compilacao_nao_e_silencio(tmp_path):
    (tmp_path / "cp").mkdir()
    (tmp_path / "cp" / "2026-10-25.html").write_text(PLANALTO, encoding="utf-8")
    v = textos.rodar([{"id": "cp", "urn": "urn:x"}], tmp_path, ler_camara=lambda urn: None)
    assert "motivo" in v[0] and textos.codigo_de_saida(v) == 2


# A Câmara atrasada no art. 122, julgada: sai da conta, fica no relatório.
JULGADA = {"fonte": "cp", "dispositivo": "Art. 122, caput", "planalto": "reclusão, 6 a 24 meses",
           "camara": "reclusão, 12 a 36 meses", "motivo": "A Câmara não anota a lei nova.", "data": "2026-10-26"}


def test_divergencia_julgada_sai_da_conta_e_fica_no_relatorio(tmp_path):
    (tmp_path / "cp").mkdir()
    (tmp_path / "cp" / "2026-10-25.html").write_text(PLANALTO, encoding="utf-8")
    v = textos.rodar([{"id": "cp", "urn": "urn:x"}], tmp_path, ler_camara=lambda urn: CAMARA,
                     excecoes=[JULGADA])
    assert v[0]["comparacao"]["divergentes"] == []
    assert [j["dispositivo"] for j in v[0]["comparacao"]["julgadas"]] == ["Art. 122, caput"]
    sem_efeito = textos.excecoes_sem_efeito(v, [JULGADA])
    assert sem_efeito == [] and textos.codigo_de_saida(v, sem_efeito) == 0
    texto = textos.montar_relatorio(v, __import__("datetime").date(2026, 10, 26), sem_efeito)
    assert "### Já julgadas — 1" in texto and "A Câmara não anota a lei nova." in texto


def test_excecao_que_nao_casa_mais_e_sem_efeito(tmp_path):
    # A Câmara atualizou: as molduras conferem, e a exceção já não descreve nada.
    (tmp_path / "cp").mkdir()
    (tmp_path / "cp" / "2026-10-25.html").write_text(PLANALTO, encoding="utf-8")
    v = textos.rodar([{"id": "cp", "urn": "urn:x"}], tmp_path, ler_camara=lambda urn: PLANALTO,
                     excecoes=[JULGADA])
    sem_efeito = textos.excecoes_sem_efeito(v, [JULGADA])
    assert sem_efeito == [JULGADA] and textos.codigo_de_saida(v, sem_efeito) == 3
    assert "retirar de `excecoes-textos.json`" in textos.montar_relatorio(
        v, __import__("datetime").date(2026, 10, 26), sem_efeito)


def test_excecao_casa_pelas_duas_molduras(tmp_path):
    # Mesma divergência, outra moldura na Câmara: é caso novo, e volta a ser pergunta.
    (tmp_path / "cp").mkdir()
    (tmp_path / "cp" / "2026-10-25.html").write_text(PLANALTO, encoding="utf-8")
    outra = {**JULGADA, "camara": "reclusão, 12 a 48 meses"}
    v = textos.rodar([{"id": "cp", "urn": "urn:x"}], tmp_path, ler_camara=lambda urn: CAMARA,
                     excecoes=[outra])
    assert len(v[0]["comparacao"]["divergentes"]) == 1 and textos.codigo_de_saida(v) == 3


def test_excecoes_do_repositorio_sao_bem_formadas():
    for e in textos.carregar_excecoes():
        assert {"fonte", "dispositivo", "planalto", "camara", "motivo", "data"} <= set(e)
