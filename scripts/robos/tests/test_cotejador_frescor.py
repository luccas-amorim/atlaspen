# -*- coding: utf-8 -*-
"""O Cotejador de frescor: o compilado anota a lei que o Senado registra?

Sem rede: a ficha do Senado vem de `senado-lep.json` (recorte real de
25/10/2026, última alteração da LEP = Lei 15.410), e o "compilado" é um HTML
mínimo que cita, ou não, cada lei.
"""
import json
from datetime import date

import pytest

from conftest import FIXTURES
from cotejador import frescor
from fontes import senado
from fontes.rede import FalhaDeRede

DIA = date(2026, 10, 25)
# As leis da ficha da LEP dentro da janela de 400 dias antes de DIA.
RECENTES = ("Lei nº 15.295", "Lei nº 15.358", "Lei nº 15.402", "Lei nº 15.407", "Lei nº 15.410")
LEP = {"id": "lep", "urn": "urn:lex:br:federal:lei:1984-07-11;7210", "sentinela": "15.410"}


@pytest.fixture
def ficha():
    return senado.ler_norma(json.loads((FIXTURES / "senado-lep.json").read_text(encoding="utf-8")))


def compilado(*leis: str) -> str:
    """Um compilado de brinquedo, com a anotação como o Planalto a escreve."""
    corpo = "".join(f"<p>Art. 1º … <a href='x'>(Redação dada pela {l}, de 2026)</a></p>" for l in leis)
    return frescor.texto_plano(f"<html><style>p{{}}</style>{corpo}</html>")


class TestAnotada:
    @pytest.mark.parametrize("pagina", ["Lei nº 15.410", "LEI Nº 15.410", "Lei n° 15410",
                                        "Lei nº&nbsp;15.410", "Lei no 15.410", "Lei n º 15.410"])
    def test_grafias_do_planalto(self, pagina):
        p = senado.Posterior("Lei nº 15.410 de 20/05/2026", "15.410", date(2026, 5, 20),
                             senado.ALTERACAO_PERMANENTE, ())
        assert frescor.anotada(frescor.texto_plano(pagina), p)

    def test_numero_vizinho_nao_casa(self):
        p = senado.Posterior("Lei nº 15.410 de 20/05/2026", "15.410", None, "", ())
        assert not frescor.anotada("Lei nº 15.4101", p)
        assert not frescor.anotada("Lei nº 15.41", p)

    def test_especie_conta(self):
        lc = senado.Posterior("Lei Complementar nº 224 de 26/12/2025", "224", None, "", ())
        assert frescor.anotada("(Incluído pela Lei Complementar nº 224, de 2025)", lc)
        assert not frescor.anotada("(Incluído pela Lei nº 224, de 1990)", lc)


class TestCotejar:
    def test_tudo_anotado_confere(self, ficha):
        texto = compilado(*RECENTES)
        v = frescor.cotejar(LEP, ficha, texto, {}, DIA)
        assert v["situacao"] == "confere" and v["ultima"] == "Lei nº 15.410 de 20/05/2026"

    def test_lei_que_o_compilado_nao_cita_vira_pergunta(self, ficha):
        texto = compilado(*RECENTES[:-1])
        chaves = {"lep|art. 52, §8º": [900], "lep|art. 112, i": [901]}
        v = frescor.cotejar(LEP, ficha, texto, chaves, DIA)
        assert v["situacao"] == "planalto_nao_anota"
        assert [f["norma"] for f in v["faltando"]] == ["Lei nº 15.410 de 20/05/2026"]
        # A 15.410 tocou o art. 52, §8º: o registro 900 sobe de prioridade.
        assert v["faltando"][0]["ids"] == [900]

    def test_lei_antiga_fora_da_janela_nao_reabre(self, ficha):
        """A 14.994/2024 está na ficha, mas fora da janela de 400 dias."""
        texto = compilado(*RECENTES)
        v = frescor.cotejar(LEP, ficha, texto, {}, DIA)
        assert not v["faltando"]

    def test_ficha_ausente_nao_e_silencio(self):
        v = frescor.cotejar(LEP, None, "", {}, DIA)
        assert v["situacao"] == "nao_lido"


class TestRodar:
    def _snapshots(self, tmp_path, texto="<p>" + " ".join(RECENTES) + "</p>"):
        (tmp_path / "lep").mkdir()
        (tmp_path / "lep" / "2026-10-25.html").write_text(texto, encoding="utf-8")
        return tmp_path

    def test_sem_snapshot_e_nao_lido(self, tmp_path, ficha):
        v = frescor.rodar([LEP], tmp_path, DIA, ler=lambda urn: ficha, chaves={})
        assert v[0]["situacao"] == "nao_lido" and "snapshot" in v[0]["motivo"]

    def test_senado_fora_do_ar_e_nao_lido(self, tmp_path):
        def cai(urn):
            raise FalhaDeRede(urn, 3, TimeoutError())
        v = frescor.rodar([LEP], self._snapshots(tmp_path), DIA, ler=cai, chaves={})
        assert v[0]["situacao"] == "nao_lido" and "não respondeu" in v[0]["motivo"]

    def test_le_o_snapshot_mais_recente(self, tmp_path, ficha):
        pasta = self._snapshots(tmp_path)
        (pasta / "lep" / "2026-01-01.html").write_text("<p>velho</p>", encoding="utf-8")
        v = frescor.rodar([LEP], pasta, DIA, ler=lambda urn: ficha, chaves={})
        assert v[0]["situacao"] == "confere"


class TestSaida:
    def test_codigos(self):
        assert frescor.codigo_de_saida([{"situacao": "confere"}]) == 0
        assert frescor.codigo_de_saida([{"situacao": "confere"}, {"situacao": "sem_registro"}]) == 0
        assert frescor.codigo_de_saida([{"situacao": "confere"}, {"situacao": "planalto_nao_anota"}]) == 3
        assert frescor.codigo_de_saida([{"situacao": "confere"}, {"situacao": "nao_lido"}]) == 3
        assert frescor.codigo_de_saida([{"situacao": "nao_lido"}]) == 2

    def test_relatorio_poe_o_que_toca_o_catalogo_primeiro(self):
        v = [{"id": "cdc", "situacao": "planalto_nao_anota",
              "faltando": [{"norma": "Lei nº 15.224 de 30/09/2025", "dispositivos": [], "ids": []}]},
             {"id": "lep", "situacao": "planalto_nao_anota",
              "faltando": [{"norma": "Lei nº 15.410 de 20/05/2026", "dispositivos": ["Art. 52, § 8"],
                            "ids": [900]}]}]
        texto = frescor.montar_relatorio(v, DIA)
        assert texto.index("`lep`") < texto.index("`cdc`")
        assert "toca 1 registro(s) do catálogo" in texto
        assert "O Senado aponta, não decide" in texto


class TestSuperada:
    """O caso medido em 25/10/2026: a Lei 15.229/2025 incluiu o art. 171, §5º,
    III, do CP; a Lei 15.397/2026 reescreveu o art. 171. O compilado cita a
    segunda, e a primeira sumiu da página — sem que nada falte."""

    def _lei(self, nome, numero, dia, *unidades):
        itens = tuple(senado.Item(u, u, "Alteração") for u in unidades)
        return senado.Posterior(nome, numero, dia, senado.ALTERACAO_PERMANENTE, itens)

    def test_lei_posterior_no_dispositivo_acima_supera(self):
        a = self._lei("Lei nº 15.229 de 02/10/2025", "15.229", date(2025, 10, 2), "art. 171, §5º, iii")
        b = self._lei("Lei nº 15.397 de 30/04/2026", "15.397", date(2026, 4, 30), "art. 171")
        assert frescor.superada_por(a, [a, b]) == "Lei nº 15.397 de 30/04/2026"

    def test_lei_posterior_noutro_dispositivo_nao_supera(self):
        a = self._lei("Lei nº 15.229 de 02/10/2025", "15.229", date(2025, 10, 2), "art. 171, §5º, iii")
        b = self._lei("Lei nº 15.517 de 22/09/2026", "15.517", date(2026, 9, 22), "art. 155, §10")
        assert frescor.superada_por(a, [a, b]) is None

    def test_superacao_parcial_nao_basta(self):
        a = self._lei("Lei nº 1", "1", date(2025, 1, 1), "art. 10", "art. 20")
        b = self._lei("Lei nº 2", "2", date(2026, 1, 1), "art. 10")
        assert frescor.superada_por(a, [a, b]) is None

    def test_lei_anterior_nao_supera(self):
        a = self._lei("Lei nº 2", "2", date(2026, 1, 1), "art. 10")
        b = self._lei("Lei nº 1", "1", date(2025, 1, 1), "art. 10")
        assert frescor.superada_por(a, [a, b]) is None

    def test_superada_nao_abre_issue_e_aparece_no_relatorio(self):
        a = self._lei("Lei nº 15.229 de 02/10/2025", "15.229", date(2025, 10, 2), "art. 171, §5º, iii")
        b = self._lei("Lei nº 15.397 de 30/04/2026", "15.397", date(2026, 4, 30), "art. 171")
        ficha = senado.Norma("1", "Decreto-Lei nº 2.848", "urn", None, "", (a, b))
        v = frescor.cotejar({"id": "cp"}, ficha, "(Redação dada pela Lei nº 15.397, de 2026)", {}, DIA)
        assert v["situacao"] == "confere" and v["superadas"][0]["por"].startswith("Lei nº 15.397")
        assert "superada por Lei nº 15.397" in frescor.montar_relatorio([v], DIA)
