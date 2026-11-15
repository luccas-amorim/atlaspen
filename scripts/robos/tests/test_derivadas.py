# -*- coding: utf-8 -*-
"""O verificador de pena derivada (28/09/2026): a conta que ficava sem conferência.

Cada caso aqui é uma linha real do catálogo, ou o erro real que a primeira
rodada achou: o incêndio majorado publicando a pena do caput (ids 722–724), a
corrupção passiva majorada sem o aumento (725), o homicídio militar privilegiado
sem a redução (693).
"""
from types import SimpleNamespace

import pytest

from nucleo import fracao
from vigia import derivadas


def _d(texto="", pena_texto=None, incisos=None):
    return SimpleNamespace(texto=texto, pena_texto=pena_texto, incisos=incisos or [])


def _linha(id, artigo, pmin, pmax, lei="CP", tipo="Reclusão"):
    return {"id": id, "lei": lei, "artigo": artigo, "pena_min": pmin, "pena_max": pmax,
            "tipo_pena": tipo, "crime": artigo}


class TestFracao:
    @pytest.mark.parametrize("texto, esperado", [
        ("o juiz pode reduzir a pena, de um sexto a um têrço", (1 / 6, 1 / 3)),
        ("aumenta-se a pena de sexta parte", (1 / 6, 1 / 6)),
        ("A pena aumenta-se de um têrço até metade:", (1 / 3, 0.5)),
        ("as penas são duplicadas", (1.0, 1.0)),
        ("As penas aumentam-se até a metade se a associação é armada", (0.0, 0.5)),
        ("Pena: Metade da cominada aos crimes ali previstos.", (0.5, 0.5)),
    ])
    def test_le_a_fracao(self, texto, esperado):
        got = fracao.fracoes_do_texto(texto)
        assert got and all(abs(a - b) < 1e-9 for a, b in zip(got, esperado))

    def test_ate_a_metade_e_teto_de_aumento_e_nao_descida(self):
        assert fracao.direcao("A pena é aumentada de 1/3 (um terço) até a metade") == "aumento"
        assert fracao.direcao("a pena é aumentada de 1/3 (um terço) à metade") == "aumento"

    def test_diminuir_as_consequencias_nao_e_minorante(self):
        assert fracao.direcao("a pena é aumentada de 1/3, se o agente não procura diminuir "
                              "as consequências do seu ato") == "aumento"

    def test_acrescida_de_uma_terca_parte_e_aumento(self):
        """DL 16/1966, art. 3º: "ficará sujeito à pena cominada no art. 1º,
        acrescida de uma terça parte". A anotação "acrescido pela Lei" não é
        verbo de aumento."""
        assert fracao.direcao("ficará sujeito à pena cominada no art. 1º, acrescida de uma "
                              "terça parte, com abertura obrigatória do competente inquérito") == "aumento"
        assert fracao.direcao("Parágrafo acrescido pela Lei nº 9.000, de 1995") is None

    def test_metade_da_cominada_e_descida(self):
        assert fracao.direcao("Pena: Metade da cominada aos crimes ali previstos.") == "diminuicao"
        assert fracao.direcao("Se o crime for culposo, a pena será reduzida à metade") == "diminuicao"

    def test_partes_de_um_dispositivo_com_duas_hipoteses(self):
        t = ("As penas cominadas nos dois artigos anteriores são aumentadas de um terço, se, "
             "em consequência do aborto, a gestante sofre lesão corporal de natureza grave; "
             "e são duplicadas, se, por qualquer dessas causas, lhe sobrevém a morte.")
        assert fracao.fracoes_do_texto(fracao.parte(t, 1)) == (1 / 3, 1 / 3)
        assert fracao.fracoes_do_texto(fracao.parte(t, 2)) == (1.0, 1.0)

    def test_aplicar_segue_a_leitura_mais_larga(self):
        assert fracao.aplicar(72, 120, "aumento", (1 / 3, 0.5)) == pytest.approx((96, 180))   # roubo majorado
        assert fracao.aplicar(12, 72, "diminuicao", (1 / 3, 2 / 3)) == pytest.approx((4, 48))  # furto privilegiado


class TestBase:
    def test_c_c_declara_a_base(self):
        assert derivadas.alvo_do_c_c("Art. 155, §11 c/c §10") == "Art. 155, §10"
        assert derivadas.alvo_do_c_c("Art. 405 c/c art. 242, §3º") == "Art. 242, §3º"
        assert derivadas.alvo_do_c_c("Art. 158, §2º c/c art. 157, §3º (morte)") == "Art. 157, §3º"
        assert derivadas.alvo_do_c_c("Art. 129, §12, II c/c caput") == "Art. 129, caput"
        assert derivadas.alvo_do_c_c("Art. 157, §2º, XI") is None

    def test_base_presumida_e_o_caput_e_depois_as_outras_molduras(self):
        regs = [_linha(1, "Art. 121, caput", 72, 240), _linha(2, "Art. 121, §3º", 12, 36),
                _linha(3, "Art. 121, §4º, 1ª parte", 16, 48), _linha(4, "Art. 121, §2º c/c §1º", 1, 1)]
        bases, origem = derivadas.candidatos_a_base(regs[2], regs)
        assert origem == "presumida"
        assert [b["id"] for b in bases] == [1, 2]      # nem ela mesma, nem outra derivada

    def test_sem_caput_no_catalogo_nao_se_adivinha(self):
        regs = [_linha(63, "Art. 141, III", 1, 32), _linha(64, "Art. 141, §2º", 18, 72)]
        assert derivadas.candidatos_a_base(regs[0], regs) == ([], "presumida")


class TestAvaliar:
    CP = [_linha(185, "Art. 250, caput", 36, 72), _linha(722, "Art. 250, §1º, I", 36, 72),
          _linha(186, "Art. 250, §2º", 6, 24, tipo="Detenção")]
    LEI = {"Art. 250|caput": _d("Causar incêndio", "Pena - reclusão, de três a seis anos, e multa."),
           "Art. 250|§ 1º": _d("As penas aumentam-se de um terço:",
                               incisos=[{"marcador": "I", "texto": "se o crime é cometido com intuito de obter vantagem"}]),
           "Art. 250|§ 2º": _d("Se culposo o incêndio, é pena de detenção, de seis meses a dois anos")}

    def test_o_incendio_majorado_publicava_a_pena_do_caput(self):
        v = derivadas.avaliar(self.CP[1], self.CP, self.LEI)
        assert v["status"] == "diverge"
        assert v["esperado"] == (48, 96) and v["base"] == "Art. 250, caput"
        assert "36–72" in v["motivo"]

    def test_a_conta_certa_confere(self):
        certa = dict(self.CP[1], pena_min=48, pena_max=96)
        v = derivadas.avaliar(certa, [self.CP[0], certa, self.CP[2]], self.LEI)
        assert v["status"] == "confere" and v["fracao"] == (1 / 3, 1 / 3)

    def test_arredondamento_de_mes_nao_e_erro(self):
        """2 meses aumentados de um terço são 2 meses e 20 dias; o catálogo escreve 2."""
        regs = [_linha(1, "Art. 129, caput", 3, 12), _linha(2, "Art. 129, §6º", 2, 12),
                _linha(3, "Art. 129, §7º", 2, 16)]
        lei = {"Art. 129|caput": _d("Ofender", "Pena - detenção, de três meses a um ano."),
               "Art. 129|§ 6º": _d("Se a lesão é culposa:", "Pena - detenção, de dois meses a um ano."),
               "Art. 129|§ 7º": _d("Aumenta-se a pena de 1/3 (um terço) se ocorrer qualquer das hipóteses")}
        v = derivadas.avaliar(regs[2], regs, lei)
        assert v["status"] == "confere" and v["base"] == "Art. 129, §6º"
        assert "base presumida" in v["motivo"]

    def test_c_c_com_base_declarada(self):
        regs = [_linha(1513, "Art. 155, §10", 48, 120), _linha(1514, "Art. 155, §11 c/c §10", 64, 160)]
        lei = {"Art. 155|§ 11º": _d("Na hipótese do § 10 deste artigo, a pena é aumentada de 1/3 (um terço)")}
        v = derivadas.avaliar(regs[1], regs, lei)
        assert v["status"] == "confere" and v["origem_da_base"] == "declarada"

    def test_c_c_sem_fracao_e_a_pena_da_base(self):
        regs = [_linha(1457, "Art. 242, §2º, I", 64, 270, lei="CPM (DL 1.001/69)"),
                _linha(1459, "Art. 243, §1º c/c art. 242, §2º, I", 64, 270, lei="CPM (DL 1.001/69)")]
        lei = {"Art. 243|§ 1º": _d("Se o agente vem a empregar violência, aplicam-se, "
                                   "correspondentemente, as disposições do art. 242, § 2º")}
        assert derivadas.avaliar(regs[1], regs, lei)["status"] == "confere"

    def test_base_que_nao_e_registro_vem_da_lei(self):
        regs = [_linha(907, "Art. 1º c/c Art. 2º", 24, 60, lei="Lei 7.643/87")]
        lei = {"Art. 1|caput": _d("Fica proibida a pesca de cetáceo")}
        v = derivadas.avaliar(regs[0], regs, lei, molduras_da_lei=lambda r: [(24, 60)] if "2" in r else [])
        assert v["status"] == "confere" and "moldura lida na lei" in v["base"]

    def test_parte_pega_a_oracao_certa(self):
        regs = [_linha(126, "Art. 126", 12, 48), _linha(1489, "Art. 127, 2ª parte c/c art. 126", 24, 96)]
        lei = {"Art. 127|caput": _d("As penas cominadas nos dois artigos anteriores são aumentadas de "
                                    "um terço, se a gestante sofre lesão corporal de natureza grave; "
                                    "e são duplicadas, se lhe sobrevém a morte.")}
        v = derivadas.avaliar(regs[1], regs, lei)
        assert v["status"] == "confere" and v["fracao"] == (1.0, 1.0)

    def test_dobro_trava_no_teto_do_cpm(self):
        """Decisão de 28/09/2026: o dobro de 15–30 anos é 30–60, e a reclusão para
        em 30 (art. 58) nos dois limites — moldura fixa, com a morte no grau
        máximo que o art. 405 comina. Publicar a moldura de paz é divergência."""
        regs = [_linha(1452, "Art. 242, §3º", 180, 360, lei="CPM (DL 1.001/69)"),
                _linha(1443, "Art. 405 c/c art. 242, §3º", 360, 360, lei="CPM (DL 1.001/69)", tipo="Morte")]
        lei = {"Art. 405|caput": _d("Praticar roubo em zona de operações", "Pena - reclusão pelo dôbro da pena")}
        assert derivadas.avaliar(regs[1], regs, lei)["status"] == "confere"
        errada = dict(regs[1], pena_min=180)
        v = derivadas.avaliar(errada, [regs[0], errada], lei)
        assert v["status"] == "diverge" and v["esperado"] == (360, 360)

    def test_caput_sem_moldura_propria_nao_serve_de_base(self):
        regs = [_linha(793, "Art. 5º", 72, 270, lei="Lei 13.260/16"),
                _linha(1461, "Art. 5º, §2º", 48, 180, lei="Lei 13.260/16")]
        lei = {"Art. 5|§ 2º": _d("a pena será a correspondente ao delito consumado, diminuída de metade a dois terços")}
        v = derivadas.avaliar(regs[1], regs, lei, molduras_da_lei=lambda r: [])
        assert v["status"] == "pede_juizo" and "outro artigo" in v["motivo"]

    def test_texto_sem_fracao_pede_juizo(self):
        regs = [_linha(1, "Art. 9, caput", 12, 36), _linha(2, "Art. 9, §1º", 12, 36)]
        lei = {"Art. 9|§ 1º": _d("Se o agente é primário, o juiz pode substituir a pena")}
        assert derivadas.avaliar(regs[1], regs, lei)["status"] == "pede_juizo"


class TestMesmaPena:
    """"Na mesma pena incorre" é seguido de um salto pelo resolvedor do conferidor."""

    def _lei(self):
        from nucleo.parsear import Dispositivo
        ds = [
            Dispositivo("187", None, "caput", texto="Ausentar-se o militar, sem licença",
                        pena_texto="Pena - detenção, de seis meses a dois anos."),
            Dispositivo("188", None, "caput", texto="Na mesma pena incorre o militar que:"),
            Dispositivo("240", None, "caput", texto="Subtrair coisa alheia móvel",
                        pena_texto="Pena - reclusão, até seis anos."),
            Dispositivo("240", None, "§ 6º", texto="Se o furto é praticado:",
                        pena_texto="Pena - reclusão, de três a dez anos."),
            Dispositivo("240", None, "§ 6º-A", texto="Na mesma pena do § 6º deste artigo incorre quem subtrai arma"),
        ]
        return {d.chave: d for d in ds}

    def test_mesma_pena_do_paragrafo_vai_ao_paragrafo(self):
        from vigia.conferir import _molduras_da_lei
        assert _molduras_da_lei(self._lei())("art. 240, §6º-A") == [(36, 120)]

    def test_mesma_pena_incorre_vai_ao_dispositivo_anterior_com_moldura(self):
        from vigia.conferir import _molduras_da_lei
        assert _molduras_da_lei(self._lei())("art. 188") == [(6, 24)]

    def test_um_salto_so(self):
        from vigia.conferir import _molduras_da_lei
        resolver = _molduras_da_lei(self._lei())
        assert resolver("art. 188", saltar=False) == []
