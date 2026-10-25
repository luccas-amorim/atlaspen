# -*- coding: utf-8 -*-
"""Testes do watcher do DOU (F7) — sem rede.

A fixture `dou-2026-05-21.json` é um recorte REAL da listagem da Seção 1 do dia
em que saiu a Lei 15.410/2026 (a que acrescentou o inciso de violência doméstica
ao crime de tortura). Três itens, cada um travando uma decisão do filtro:

- a própria 15.410, que cita diploma monitorado;
- a Lei 15.409, cuja ementa não tem nada penal — o filtro não pode inventar;
- um despacho da ANEEL que diz "Revogar": vocabulário casado, espécie recusada.
  É o caso que garante que o watcher não afogue a issue em administrativo.
"""
import json
from pathlib import Path

from sentinela.dou_watcher import (classificar, comina_pena, marcas_penais,
                         montar_relatorio, padrao_dos_diplomas, triar)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
FONTES = Path(__file__).resolve().parents[3] / "data" / "fontes.json"


def carregar_itens():
    return json.loads((FIXTURES / "dou-2026-05-21.json").read_text(encoding="utf-8"))


def montar_filtro():
    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    return padrao_dos_diplomas(fontes)


class TestPadraoDosDiplomas:
    """O padrão de citação nasce de `fontes.json` — crescer o registro é
    crescer o watcher, sem tocar no código."""

    def test_reconhece_diplomas_por_numero_com_e_sem_ponto(self):
        padrao, numeros = montar_filtro()
        assert padrao.search("altera a Lei nº 9.605, de 1998")
        assert padrao.search("altera a Lei 9605")
        assert padrao.search("o Decreto-Lei nº 2.848 (Código Penal)")

    def test_numero_solto_nao_casa(self):
        """Sem a espécie na frente, "9.605" é número de processo, de valor ou
        de portaria — casar isso encheria a issue de ruído."""
        padrao, _ = montar_filtro()
        assert not padrao.search("Processo nº 9.605/2026")
        assert not padrao.search("R$ 2.848,00")

    def test_mapeia_de_volta_para_o_id_da_fonte(self):
        _, numeros = montar_filtro()
        assert numeros["2848"] == "cp"
        assert numeros["11340"] == "maria-penha-11340"
        assert numeros["9455"] == "tortura-9455"


class TestCominaPena:
    """O discriminador. Não filtra mais nada antes dele — ele decide sozinho."""

    def test_formula_canonica(self):
        assert comina_pena("Pena - reclusão, de 2 a 5 anos")
        assert comina_pena("detenção, de 3 (três) meses a 1 (um) ano")

    def test_pena_por_remissao(self):
        """Nove registros do catálogo têm essa forma, e nenhum traz "Pena -"."""
        assert comina_pena("Quem faz uso de documento falso incorre na pena "
                           "cominada à falsificação")
        assert comina_pena("Incorre nas mesmas penas quem…")
        assert comina_pena("aplica-se metade da pena cominada no art. 1º")
        assert comina_pena("punido no dobro da pena cominada para o tempo de paz")

    def test_pena_fora_da_formula(self):
        """Art. 28 da Lei 11.343/06: há pena, há tipo, e não há "Pena -"."""
        assert comina_pena("será submetido às seguintes penas: I - advertência "
                           "sobre os efeitos das drogas")

    def test_lei_que_so_fala_de_pena_nao_passa(self):
        assert not comina_pena("Institui o Dia Nacional do Cooperativismo")
        assert not comina_pena("Dispõe sobre o cumprimento de pena em "
                               "estabelecimento prisional federal")

    def test_marcas_dizem_por_que_o_ato_foi_aberto(self):
        assert "preceito secundário" in marcas_penais("Pena - reclusão, de 2 a 5 anos")
        assert "pena por remissão" in marcas_penais("Incorre nas mesmas penas")
        assert marcas_penais("Institui o Dia Nacional do Cooperativismo") == []


class TestTriagem:
    """Filtro largo, mas só sobre ato normativo."""

    def _triar(self, integral=""):
        padrao, numeros = montar_filtro()
        return triar(carregar_itens(), padrao, numeros, buscar_texto=lambda _: integral)

    def test_acha_a_lei_penal_da_semana(self):
        achadas = self._triar()
        titulos = [c["titulo"] for c in achadas]
        assert any("15.410" in t for t in titulos)
        lei = next(c for c in achadas if "15.410" in c["titulo"])
        assert "tortura-9455" in lei["diplomas_citados"]

    def test_ignora_despacho_mesmo_falando_em_revogar(self):
        """Espécie que não pode criar crime não entra: é o que mantém a lista
        com cinco itens por semana em vez de trezentos."""
        achadas = self._triar()
        assert not any("DESPACHO" in c["titulo"].upper() for c in achadas)

    def test_nao_inventa_candidata(self):
        """A Lei 15.409 (cadastro de condenados) não comina pena nem cita
        diploma monitorado — sem o texto integral, é DESCARTADA.

        Desde 11/08/2026 ela não some da lista: `triar` devolve todo ato
        normativo, e o corte é do classificador. O descartado sai nomeado, em
        uma linha, para que a decisão do filtro seja auditável — sumir era o que
        tornava impossível saber se o corte estava certo.
        """
        achadas = self._triar()
        dela = [c for c in achadas if "15.409" in c["titulo"]]
        assert dela, "o ato normativo tem de aparecer, ainda que descartado"
        assert all(c["nivel"] == "descartado" for c in dela)

    def test_texto_integral_amplia_o_alcance(self):
        """O que a ementa esconde, o texto integral revela — por isso o watcher
        baixa a íntegra dos poucos atos normativos da semana."""
        achadas = self._triar(integral="Pena - reclusão, de 1 (um) a 4 (quatro) anos.")
        assert any("15.409" in c["titulo"] for c in achadas)


class TestNiveis:
    """O corte que fez a lista encolher, medido contra 14 dias reais de Seção 1.

    O filtro largo devolvia SEIS candidatas em 3.569 atos, e nenhuma trazia
    preceito secundário: uma lei sobre saúde mental na criança (por alterar o
    ECA), uma sobre fundo garantidor (pela palavra "revoga"), uma sobre
    honorários de advogado (por citar o Estatuto da OAB). Ler seis textos por
    semana sem achar nada é o jeito mais rápido de parar de ler."""

    def test_preceito_secundario_sem_diploma_monitorado_e_o_ponto_cego(self):
        nivel, _ = classificar("Art. 2º Constitui crime … Pena - reclusão, de 20 a 40 anos.",
                               "Tipifica os crimes de domínio social estruturado", [])
        assert nivel == "novo"

    def test_preceito_secundario_em_diploma_monitorado_e_antecedencia(self):
        nivel, _ = classificar("… passa a vigorar acrescida do seguinte art. 40-A. "
                               "Pena - reclusão, de 5 a 15 anos.", "Altera a Lei 11.343",
                               ["drogas-11343"])
        assert nivel == "monitorado"

    def test_alterar_diploma_monitorado_sem_pena_e_descartado(self):
        """Caso real: a Lei 15.413/2026 altera o ECA para dispor sobre saúde
        mental. Nada de penal — e o conferidor vê a página do ECA toda semana."""
        nivel, porque = classificar(
            "Altera a Lei nº 8.069, de 1990, para dispor sobre o direito da criança "
            "e do adolescente à saúde mental. … passa a vigorar acrescida",
            "dispõe sobre saúde mental", ["eca"])
        assert nivel == "descartado"
        assert "sem cominar pena" in porque

    def test_palavra_solta_sem_diploma_e_descartado(self):
        """"revoga" e "crime" aparecem em lei de fundo garantidor e de fundo
        penitenciário. Sozinhas não dizem nada."""
        for texto in ("Revoga a Lei nº 14.042, de 2020, para autorizar a União",
                      "destinação de recursos do Fundo para Aparelhamento … combate ao crime"):
            assert classificar(texto, "", [])[0] == "descartado"

    def test_revogacao_de_dispositivo_em_diploma_monitorado_sobe_de_nivel(self):
        """Revogar um tipo penal não deixa "Pena -" no texto do ato. Sem esta
        regra, a supressão de um crime passaria pelo corte."""
        nivel, _ = classificar("Revogam-se os arts. 12 e 13 da Lei nº 7.716, de 1989.",
                               "", ["racismo-7716"])
        assert nivel == "monitorado"

    def test_ementa_salva_o_nivel_1_quando_a_integra_nao_abre(self):
        """Se o texto integral não pôde ser lido, a ementa que anuncia o crime
        basta — falso negativo aqui custa meses de catálogo desatualizado."""
        nivel, _ = classificar("", "Tipifica o crime de perseguição digital", [])
        assert nivel == "novo"


class TestRelatorio:
    def test_secao_vazia_diz_que_nao_ha_nada(self):
        from datetime import date
        texto = montar_relatorio([], date(2026, 5, 15), date(2026, 5, 22))
        assert "Nenhum ato normativo" in texto

    def test_lista_com_link_e_termos(self):
        from datetime import date
        padrao, numeros = montar_filtro()
        achadas = triar(carregar_itens(), padrao, numeros, buscar_texto=lambda _: "")
        texto = montar_relatorio(achadas, date(2026, 5, 15), date(2026, 5, 22))
        assert "15.410" in texto
        assert "in.gov.br/web/dou" in texto
        assert "tortura-9455" in texto

    def test_descartado_e_nomeado_e_nao_escondido(self):
        """O corte não pode virar cegueira: o princípio do módulo é que falso
        negativo não se tolera. Quem foi descartado aparece em uma linha, com o
        motivo — três segundos de leitura, e o corte fica auditável."""
        from datetime import date
        padrao, numeros = montar_filtro()
        achadas = triar(carregar_itens(), padrao, numeros, buscar_texto=lambda _: "")
        texto = montar_relatorio(achadas, date(2026, 5, 15), date(2026, 5, 22))
        assert "Descartados" in texto
        assert "Sentinelas a conferir" in texto


class TestReservaLegal:
    """Só lei ordinária e lei complementar criam tipo penal (CF, art. 5º, XXXIX).

    O corte por espécie não é economia de requisição — é direito. Vigiar medida
    provisória era vigiar o que a Constituição proíbe que exista (art. 62, §1º,
    I, "b"), e as três MPs da primeira rodada real entraram só para serem
    descartadas uma a uma.
    """

    def _passa(self, especie):
        from sentinela.dou_watcher import ESPECIES
        return bool(ESPECIES.match(especie))

    def test_as_duas_que_criam_crime(self):
        assert self._passa("Lei")
        assert self._passa("Lei Complementar")

    def test_medida_provisoria_nao_entra(self):
        assert not self._passa("Medida Provisória")

    def test_as_demais_especies_tambem_nao(self):
        # Lei delegada: a delegação não alcança direitos individuais (art. 68,
        # §1º, II). Decreto-lei: espécie extinta em 1988. Emenda: manda
        # criminalizar, não criminaliza.
        assert not self._passa("Lei Delegada")
        assert not self._passa("Decreto-Lei")
        assert not self._passa("Emenda Constitucional")

    def test_portaria_e_decreto_seguem_de_fora(self):
        assert not self._passa("Portaria")
        assert not self._passa("Decreto")


class TestUrnDaFonteProposta:
    """A entrada proposta para `fontes.json` precisa de `urn` desde 25/10/2026,
    ou o build do PR reprova (`validar_fontes`)."""

    CANDIDATA = {"titulo": "LEI Nº 15.410, DE 20 DE MAIO DE 2026", "data": "2026-05-21",
                 "url": "https://www.in.gov.br/web/dou/-/lei-15410", "diplomas_citados": []}
    INTEGRAL = "Art. 1º Matar alguém. Pena - reclusão, de 6 (seis) a 20 (vinte) anos."

    def test_data_da_assinatura_sai_do_titulo(self):
        from datetime import date
        from sentinela.dou_watcher import data_do_titulo
        assert data_do_titulo("LEI Nº 15.410, DE 20 DE MAIO DE 2026") == date(2026, 5, 20)
        assert data_do_titulo("LEI COMPLEMENTAR Nº 224, DE 1º DE MARÇO DE 2025") == date(2025, 3, 1)
        assert data_do_titulo("DESPACHO DE ONTEM") is None

    def test_proposta_traz_urn_que_o_construtor_aceita(self):
        from sentinela.dou_watcher import propor_fonte
        from catalogo.validacoes import _URN
        proposta = propor_fonte(self.CANDIDATA, self.INTEGRAL, set())
        assert proposta["urn"] == "urn:lex:br:federal:lei:2026-05-20;15410"
        assert _URN.match(proposta["urn"])

    def test_lei_complementar(self):
        from sentinela.dou_watcher import propor_fonte
        c = {**self.CANDIDATA, "titulo": "LEI COMPLEMENTAR Nº 230, DE 2 DE JUNHO DE 2026"}
        assert propor_fonte(c, self.INTEGRAL, set())["urn"] == \
            "urn:lex:br:federal:lei.complementar:2026-06-02;230"


class TestDiaQueNaoAbre:
    """Em 25/10/2026 uma listagem lenta do in.gov.br derrubou o Sentinela
    inteiro: a semana ficou sem resposta por causa de um dia."""

    def _listar(self, quedas):
        from fontes.rede import FalhaDeRede

        def listar(dia, secao):
            if (dia.day, secao) in quedas:
                raise FalhaDeRede("https://www.in.gov.br/leiturajornal", 2, TimeoutError("read timed out"))
            return []
        return listar

    def test_dia_que_nao_abre_vira_aviso_e_a_varredura_segue(self):
        from datetime import date
        from sentinela.dou_watcher import rodar
        vistos = []

        def listar(dia, secao):
            vistos.append((dia.day, secao))
            return self._listar({(24, "do1")})(dia, secao)
        candidatas, nao_lidos, sem_texto = rodar(date(2026, 10, 25), 3, listar_dia=listar, pausa=0)
        assert candidatas == [] and sem_texto == []
        assert len(nao_lidos) == 1 and nao_lidos[0].startswith("24/10/2026, seção `do1`")
        # Os outros dias e seções foram lidos, inclusive os depois da queda.
        assert len(vistos) == 6

    def test_ato_sem_texto_fica_contado_e_usa_a_ementa(self):
        from datetime import date
        from fontes.rede import FalhaDeRede
        from sentinela.dou_watcher import rodar

        def cai(slug):
            raise FalhaDeRede(slug, 2, TimeoutError())
        itens = carregar_itens()
        candidatas, nao_lidos, sem_texto = rodar(
            date(2026, 5, 21), 1, listar_dia=lambda d, s: itens if s == "do1" else [],
            buscar_texto=cai, pausa=0)
        assert not nao_lidos and sem_texto
        assert all(not c["integral"] for c in candidatas)

    def test_codigo_e_relatorio(self):
        from datetime import date
        from sentinela.dou_watcher import codigo_de_saida
        assert codigo_de_saida([], []) == 0
        assert codigo_de_saida([], ["24/10/2026, seção `do1`: timeout"]) == 2
        assert codigo_de_saida([{"nivel": "novo"}], ["x"]) == 3
        texto = montar_relatorio([], date(2026, 10, 18), date(2026, 10, 25),
                                 ["24/10/2026, seção `do1`: timeout"])
        assert "Varredura incompleta" in texto and "24/10/2026" in texto
        assert "nos dias lidos" in texto and "nesta janela" not in texto
