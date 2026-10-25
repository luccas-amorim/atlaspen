# -*- coding: utf-8 -*-
"""Testes do orquestrador do PR semanal (F6b).

Sem rede e sem tocar no repositório: o que se testa aqui é a montagem — versão,
corpo do PR e notas de atualização —, porque é onde um erro passa despercebido
até virar nota publicada. A escolha do diploma e a aplicação no catálogo são
exercitadas contra os snapshots reais nas rodadas do workflow.

A regra das notas (decisão de 14/09/2026): só vai para o feed a alteração de
LEI, lida da anotação do compilado — redação dada, ou dispositivo incluído, por
lei deste ano ou do anterior. Correção de dado fica fora.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # scripts/
from proponente import propor  # noqa: E402

LEI_NOVA = {"acao": "redacao", "norma": "Lei nº 15.397", "ano": 2026,
            "texto": "(Redação dada pela Lei nº 15.397, de 2026)",
            "url": "https://exemplo/l15397.htm#art1"}


@pytest.fixture
def escolha():
    """Uma rodada com uma correção e uma linha nova, as duas vindas de lei recente."""
    antes = {"id": 42, "artigo": "Art. 155, §4º", "crime": "Furto qualificado",
             "pena_min": 24, "pena_max": 96, "tipo_pena": "Reclusão",
             "obs": "2 a 8 anos reclusão"}
    depois = dict(antes, pena_min=24, pena_max=120, tipo_pena="Reclusão",
                  obs="2 a 10 anos reclusão")
    return {
        "fonte": {"id": "cp", "rotulos": ["CP"], "url": "https://exemplo/cp.htm"},
        "correcoes": [{"id": 42, "antes": antes, "depois": depois,
                       "evidencia": "Pena - reclusão, de dois a dez anos",
                       "anotacao": dict(LEI_NOVA)}],
        "novas": [{"linha": {"id": 1700, "artigo": "Art. 155, §5º",
                             "crime": "Furto de veículo", "pena_min": 36,
                             "pena_max": 96, "tipo_pena": "Reclusão",
                             "elemento": "Doloso"},
                   "achado": {"tipo": "AUSENTE", "detalhe": "dispositivo com pena própria",
                              "anotacao": dict(LEI_NOVA, acao="incluido",
                                               texto="(Incluído pela Lei nº 15.397, de 2026)")},
                   "herdado": ["acao"], "caput_id": 7}],
        "humanos": [{"chave": "Art. 180|caput", "tipo": "REVOGADO",
                     "detalhe": "a lei marca como revogado"}],
        "total": 2,
    }


class TestVersao:
    def test_correcao_de_dado_sobe_o_patch(self):
        assert propor.proxima_versao("1.3.0") == "1.3.1"
        assert propor.proxima_versao("1.3.9") == "1.3.10"

    def test_em_0x_a_versao_anda_em_0_0_x(self, monkeypatch):
        """Até o lançamento o projeto anda em 0.0.x (decisão de 14/09/2026)."""
        monkeypatch.setattr(propor, "versao_atual", lambda: "0.0.0")
        assert propor.versao_da_rodada() == "0.0.1"

    def test_bump_que_nao_pega_derruba_o_processo(self, tmp_path):
        """O bump por substituição de texto já falhou em silêncio neste
        repositório — três entradas anunciaram versões que nunca saíram. Aqui,
        não casar é erro fatal, nunca "seguir com o arquivo intacto"."""
        alvo = tmp_path / "package.json"
        alvo.write_bytes(b'{\r\n  "version": "9.9.9"\r\n}\r\n')
        with pytest.raises(SystemExit):
            propor._substituir_versao(alvo, r'"version":\s*"{v}"', "1.3.0", "1.3.1")

    def test_bump_preserva_o_crlf_do_arquivo(self, tmp_path):
        """Reescrever em LF trocaria a quebra de linha do arquivo inteiro e o
        diff do PR mostraria cinquenta linhas no lugar de uma."""
        alvo = tmp_path / "package.json"
        alvo.write_bytes(b'{\r\n  "name": "atlaspen",\r\n  "version": "1.3.0"\r\n}\r\n')
        propor._substituir_versao(alvo, r'"version":\s*"{v}"', "1.3.0", "1.3.1")
        bruto = alvo.read_bytes()
        assert b'"version": "1.3.1"' in bruto
        assert bruto.count(b"\r\n") == 4 and b"\n\n" not in bruto.replace(b"\r\n", b"")

    def test_o_lockfile_sobe_nas_duas_raizes(self, tmp_path):
        alvo = tmp_path / "package-lock.json"
        alvo.write_bytes(b'{\n  "version": "0.0.1",\n  "packages": {\n    "": {\n'
                         b'      "version": "0.0.1"\n    },\n    "x": {"version": "0.0.1"}\n  }\n}\n')
        propor._substituir_versao(alvo, r'"version":\s*"{v}"', "0.0.1", "0.0.2", vezes=2)
        bruto = alvo.read_bytes()
        assert bruto.count(b'"0.0.2"') == 2 and b'"x": {"version": "0.0.1"}' in bruto


class TestCorpoDoPR:
    def test_cada_mudanca_leva_a_evidencia_da_lei(self, escolha):
        corpo = propor.corpo_pr(escolha, "1.3.1")
        assert "https://exemplo/cp.htm" in corpo          # o texto conferido
        assert "Pena - reclusão, de dois a dez anos" in corpo
        assert "24–96 meses" in corpo and "24–120 meses" in corpo
        assert "/tipos/42" in corpo                       # onde conferir publicado

    def test_linha_nova_declara_o_que_foi_herdado(self, escolha):
        """Do texto saem seis campos; o resto herda do caput. A revisão precisa
        saber onde olhar primeiro."""
        corpo = propor.corpo_pr(escolha, "1.3.1")
        assert "Herdado do caput" in corpo and "acao" in corpo

    def test_o_que_nao_e_mecanico_aparece_como_pendente(self, escolha):
        corpo = propor.corpo_pr(escolha, "1.3.1")
        assert "Fora do automático" in corpo and "REVOGADO" in corpo

    def test_o_corpo_diz_o_que_vai_e_o_que_nao_vai_para_o_feed(self, escolha):
        escolha["correcoes"][0]["anotacao"] = dict(LEI_NOVA, ano=2009)
        legais, fora = propor.mudancas_da_lei(escolha, 2026)
        corpo = propor.corpo_pr(escolha, "1.3.1", legais, fora)
        assert "novatio legis incriminadora" in corpo
        assert "fora do feed, correção de dado" in corpo


class TestQueVaiParaAsNotas:
    def test_alteracao_de_lei_recente_vira_nota_com_a_natureza(self, escolha):
        legais, fora = propor.mudancas_da_lei(escolha, 2026)
        assert [(m["id"], m["natureza"]) for m in legais] == [(42, "pejus"), (1700, "incriminadora")]
        assert fora == []

    def test_correcao_de_dado_fica_fora_do_feed(self, escolha):
        """Moldura divergente sob redação antiga é erro do catálogo, não lei nova."""
        escolha["correcoes"][0]["anotacao"] = dict(LEI_NOVA, ano=2009)
        legais, fora = propor.mudancas_da_lei(escolha, 2026)
        assert [m["id"] for m in legais] == [1700]
        assert fora[0]["id"] == 42 and "correção de dado" in fora[0]["motivo"]

    def test_sem_anotacao_nao_ha_como_afirmar_lei_nova(self, escolha):
        escolha["correcoes"][0]["anotacao"] = None
        escolha["novas"][0]["achado"]["anotacao"] = None
        legais, fora = propor.mudancas_da_lei(escolha, 2026)
        assert legais == [] and len(fora) == 2

    def test_pena_que_desce_e_in_mellius(self, escolha):
        c = escolha["correcoes"][0]
        c["depois"] = dict(c["antes"], pena_max=72)
        legais, _ = propor.mudancas_da_lei(escolha, 2026)
        assert legais[0]["natureza"] == "mellius"

    def test_sentido_misto_vai_para_a_revisao(self, escolha):
        c = escolha["correcoes"][0]
        c["depois"] = dict(c["antes"], pena_min=36, pena_max=72)
        legais, fora = propor.mudancas_da_lei(escolha, 2026)
        assert [m["id"] for m in legais] == [1700]
        assert "natureza fica para a revisão" in fora[0]["motivo"]

    def test_linha_que_so_faltava_no_catalogo_nao_e_incriminadora(self, escolha):
        """Dispositivo antigo que o catálogo não tinha é completude, não lei nova."""
        escolha["novas"][0]["achado"]["anotacao"] = dict(LEI_NOVA, acao="incluido", ano=1998)
        legais, fora = propor.mudancas_da_lei(escolha, 2026)
        assert [m["id"] for m in legais] == [42]
        assert fora[0]["id"] == 1700


class TestEntradaDeChangelog:
    def test_uma_entrada_por_lei_e_por_natureza(self, escolha, monkeypatch, tmp_path):
        monkeypatch.setattr(propor, "ENTRADAS", tmp_path)
        legais, _ = propor.mudancas_da_lei(escolha, 2026)
        saida = propor.entradas_changelog(escolha, legais, "0.0.2", "2026-09-14")
        nomes = sorted(d.name for d, _ in saida)
        assert nomes == ["2026-09-14-lei-15397-incriminadora.ts", "2026-09-14-lei-15397-pejus.ts"]
        por_nome = {d.name: ts for d, ts in saida}
        pejus = por_nome["2026-09-14-lei-15397-pejus.ts"]
        # O contrato mudou em 24/09/2026: a entrada declara `alcance`, e não
        # mais a natureza em latim. A direção continua no TÍTULO, em português —
        # é lá que o leitor a lê —, e continua agrupando as correções: uma
        # entrada por lei e por sentido.
        assert "alcance: ['tipo']" in pejus and "version: 'v0.0.2'" in pejus
        assert "penas agravadas" in pejus or "pena agravada" in pejus
        assert "de 2 a 8 anos de reclusão para 2 a 10 anos de reclusão" in pejus
        # O link externo sai literal; o interno, por `urlPublica`.
        assert "https://exemplo/l15397.htm#art1" in pejus
        assert 'urlPublica("/tipos/42")' in pejus
        incrim = por_nome["2026-09-14-lei-15397-incriminadora.ts"]
        assert "alcance: ['tipo']" in incrim
        assert "incluído" in incrim or "incluídos" in incrim
        # body é texto puro: sem markdown, sem backtick (contrato do ChangelogEntry)
        corpo = pejus.split("body: [")[1].split("],")[0]
        assert "`" not in corpo and "**" not in corpo

    def test_id_nao_colide_no_mesmo_dia(self, escolha, monkeypatch, tmp_path):
        monkeypatch.setattr(propor, "ENTRADAS", tmp_path)
        (tmp_path / "2026").mkdir()
        (tmp_path / "2026" / "2026-09-14-lei-15397-pejus.ts").write_text("já existe")
        escolha["novas"] = []
        legais, _ = propor.mudancas_da_lei(escolha, 2026)
        [(destino, ts)] = propor.entradas_changelog(escolha, legais, "0.0.2", "2026-09-14")
        assert destino.name == "2026-09-14-lei-15397-pejus-2.ts"
        assert "id: '2026-09-14-lei-15397-pejus-2'" in ts


def _sem_catalogo(monkeypatch, tmp_path):
    monkeypatch.setattr(propor, "ENTRADAS", tmp_path / "entries")
    monkeypatch.setattr(propor, "corrigir", type("X", (), {"aplicar": staticmethod(lambda p: None)}))
    monkeypatch.setattr(propor, "criar", type("X", (), {"aplicar": staticmethod(lambda p: None)}))


def test_meta_do_pr_tem_ramo_titulo_e_as_notas(escolha, monkeypatch, tmp_path):
    """O workflow lê este JSON para nomear o ramo e o PR — se mudar de formato,
    o passo de abertura falha calado."""
    _sem_catalogo(monkeypatch, tmp_path)
    subiu = []
    monkeypatch.setattr(propor, "subir_versao", lambda v: subiu.append(v))
    meta = propor.aplicar(escolha, "0.0.2", "2026-09-14", tmp_path / "saida")
    assert meta["ramo"] == "conferidor/cp-2026-09-14"
    assert meta["fonte"] == "cp" and meta["versao"] == "0.0.2" and subiu == ["0.0.2"]
    assert len(meta["entradas"]) == 2 and meta["entrada"] == meta["entradas"][0]
    assert (tmp_path / "saida" / "corpo.md").exists()
    gravado = json.loads((tmp_path / "saida" / "meta.json").read_text(encoding="utf-8"))
    assert gravado["correcoes"] == 1 and gravado["novas"] == 1


def test_sem_lei_recente_nao_ha_nota_nem_versao(escolha, monkeypatch, tmp_path):
    """Rodada só de correção de dado: aplica, mas não escreve nota nem sobe versão
    (a versão sem entrada seria reprovada pelo validar-changelog). As chaves do
    meta continuam existindo, vazias, porque o workflow as lê."""
    _sem_catalogo(monkeypatch, tmp_path)
    escolha["correcoes"][0]["anotacao"] = None
    escolha["novas"][0]["achado"]["anotacao"] = None
    subiu = []
    monkeypatch.setattr(propor, "subir_versao", lambda v: subiu.append(v))
    meta = propor.aplicar(escolha, "0.0.2", "2026-09-14", tmp_path / "saida")
    assert meta["versao"] == "" and meta["entrada"] == "" and meta["entradas"] == []
    assert not subiu and not (tmp_path / "entries").exists()
    corpo = (tmp_path / "saida" / "corpo.md").read_text(encoding="utf-8")
    assert "fecha a versão" not in corpo and "nenhuma mudança vem de lei recente" in corpo


# ── Sentinelas e modificadores de escopo declarado (28/09/2026) ─────────────
from types import SimpleNamespace  # noqa: E402


def _disp(texto="", marcador="caput", artigo="155", sufixo=None, anotacao=None,
          epigrafe=None, citacao=False, incisos=None):
    return SimpleNamespace(texto=texto, marcador=marcador, artigo=artigo, sufixo=sufixo,
                           anotacao=anotacao, epigrafe=epigrafe, citacao=citacao,
                           incisos=incisos or [])


def _anot(norma="Lei nº 15.517", ano=2026, texto="(Incluído pela Lei nº 15.517, de 2026)"):
    return SimpleNamespace(norma=norma, ano=ano, texto=texto)


class TestSentinelas:
    FONTE = {"id": "cp", "rotulos": ["CP"], "sentinela": "15.384"}

    def _propostas(self, disp, fonte=None):
        return propor.sentinelas_propostas([fonte or self.FONTE], dispositivos=lambda fid: disp)

    def test_lei_mais_nova_anotada_vira_sentinela(self):
        disp = {"Art. 155|§ 10º": _disp(anotacao=_anot()),
                "Art. 121|caput": _disp(anotacao=_anot("Lei nº 15.397", 2026,
                                                       "(Redação dada pela Lei nº 15.397, de 2026)"))}
        p = self._propostas(disp)
        assert [(x["de"], x["para"]) for x in p] == [("15.384", "15.517")]
        assert "15.517" in p[0]["evidencia"]

    def test_lei_mais_velha_nao_mexe(self):
        disp = {"Art. 1|caput": _disp(anotacao=_anot("Lei nº 13.964", 2019,
                                                     "(Incluído pela Lei nº 13.964, de 2019)"))}
        assert self._propostas(disp) == []

    def test_sentinela_de_conteudo_fica_como_esta(self):
        fonte = {"id": "orgcrim-15358", "rotulos": ["Lei 15.358/26"],
                 "sentinela": "domínio social estruturado"}
        disp = {"Art. 2|caput": _disp(anotacao=_anot())}
        assert self._propostas(disp, fonte) == []

    def test_vide_e_remissao_nao_prova_frescor(self):
        disp = {"Art. 158|§ 2º": _disp(anotacao=_anot("Lei nº 15.900", 2026,
                                                      "Vide Lei nº 15.900, de 2026"))}
        assert self._propostas(disp) == []

    def test_texto_citado_de_outra_lei_nao_conta(self):
        disp = {"Art. 172|caput": _disp(anotacao=_anot(), citacao=True)}
        assert self._propostas(disp) == []

    def test_lei_complementar_nao_troca_numero_de_lei_ordinaria(self):
        disp = {"Art. 1|caput": _disp(anotacao=_anot("Lei Complementar nº 224", 2026,
                                                     "(Incluído pela Lei Complementar nº 224, de 2026)"))}
        assert self._propostas(disp) == []

    def test_anotacao_de_inciso_tambem_conta(self):
        disp = {"Art. 157|§ 2º": _disp(incisos=[{"marcador": "XI", "anotacao": _anot()}])}
        assert [x["para"] for x in self._propostas(disp)] == ["15.517"]

    def test_aplicar_troca_so_a_entrada_certa(self, tmp_path):
        f = tmp_path / "fontes.json"
        f.write_text('''{
  "fontes": [
    {"id": "cp", "rotulos": ["CP"], "url": "u", "sentinela": "15.384"},
    {"id": "cpm", "rotulos": ["CPM"], "url": "u", "sentinela": "15.384"}
  ]
}
''', encoding="utf-8")
        propor.aplicar_sentinelas([{"fonte": "cpm", "de": "15.384", "para": "15.517"}], f)
        texto = f.read_text(encoding="utf-8")
        assert '"id": "cp", "rotulos": ["CP"], "url": "u", "sentinela": "15.384"' in texto
        assert '"id": "cpm", "rotulos": ["CPM"], "url": "u", "sentinela": "15.517"' in texto

    def test_aplicar_que_nao_acha_a_entrada_derruba_o_processo(self, tmp_path):
        f = tmp_path / "fontes.json"
        f.write_text('{"fontes": [{"id": "cp", "sentinela": "1.000"}]}', encoding="utf-8")
        with pytest.raises(SystemExit):
            propor.aplicar_sentinelas([{"fonte": "cp", "de": "15.384", "para": "15.517"}], f)


class TestFracoes:
    @pytest.mark.parametrize("texto, esperado", [
        ("a pena é aumentada de 1/3 (um terço), se o crime é praticado:", (1 / 3, 1 / 3)),
        ("a pena é aumentada de 2/3 (dois terços) se do crime resulta:", (2 / 3, 2 / 3)),
        ("A pena aumenta-se de 1/3 (um terço) até metade:", (1 / 3, 0.5)),
        ("A pena aumenta-se de um terço até metade", (1 / 3, 0.5)),
        ("As penas aumentam-se de um sexto a um terço", (1 / 6, 1 / 3)),
        ("a pena poderá ser reduzida de um a dois terços", (1 / 3, 2 / 3)),
        ("diminuir a pena de 1/3 (um terço) a 2/3 (dois terços)", (1 / 3, 2 / 3)),
        ("A pena aumenta-se de 1/3 (um terço) ao dobro", (1 / 3, 1.0)),
        ("a pena poderá ser reduzida até a metade", (0.0, 0.5)),
        ("aplica-se em dobro a pena prevista no caput", (1.0, 1.0)),
        ("As penas aumentam-se de metade, se há dano para outrem", (0.5, 0.5)),
        ("Pena - reclusão, de um a três anos, e multa.", None),
    ])
    def test_le_a_fracao_como_a_lei_escreve(self, texto, esperado):
        got = propor.fracoes_do_texto(texto)
        if esperado is None:
            assert got is None
        else:
            assert got is not None and all(abs(a - b) < 1e-9 for a, b in zip(got, esperado))


class TestModificadoresPropostos:
    FONTE = {"id": "cp", "rotulos": ["CP"], "url": "u"}
    CATALOGO = [{"lei": "CP", "artigo": "Art. 155, caput"},
                {"lei": "CP", "artigo": "Art. 155, §10"},
                {"lei": "CP", "artigo": "Art. 155, §11 c/c §10"},
                {"lei": "CP", "artigo": "Art. 344"},
                {"lei": "CP", "artigo": "Art. 133, caput"},
                {"lei": "CP", "artigo": "Art. 133, §1º"}]

    def _propor(self, disp, chave):
        achado = {"fonte": "cp", "dispositivo": chave, "tipo": "MODIFICADOR-AUSENTE",
                  "detalhe": ""}
        return propor.modificadores_propostos(self.FONTE, self.CATALOGO, [achado],
                                              "2026-09-28", dispositivos=lambda fid: disp)

    def test_na_hipotese_do_paragrafo_declara_o_alcance(self):
        disp = {"Art. 155|caput": _disp(epigrafe="Furto"),
                "Art. 155|§ 11º": _disp("Na hipótese do § 10 deste artigo, a pena é aumentada "
                                        "de 1/3 (um terço), se o crime é praticado:",
                                        marcador="§ 11º", anotacao=_anot())}
        p = self._propor(disp, "Art. 155|§ 11º")
        assert len(p) == 1
        m = p[0]["modificador"]
        assert m["escopo"] == {"tipo": "tipos_por_artigo", "lei": "CP", "artigos": ["Art. 155, §10"]}
        assert m["natureza"] == "aumento" and abs(m["fracao_min"] - 1 / 3) < 1e-9
        assert m["dispositivo"] == "CP, art. 155, §11" and m["nome"].startswith("Furto — §11 (+1/3)")
        # a linha "§11 c/c §10" existe: o front já não oferece o aumento de novo
        assert p[0]["embutida"] and "ignora_embutida" not in m
        assert "Lei nº 15.517" in m["obs"]

    def test_sem_alcance_declarado_fica_como_pergunta(self):
        disp = {"Art. 171|§ 3º": _disp("A pena aumenta-se de um terço, se o crime é cometido em "
                                       "detrimento de entidade de direito público",
                                       marcador="§ 3º", artigo="171")}
        assert self._propor(disp, "Art. 171|§ 3º") == []

    def test_neste_artigo_com_linha_unica_e_leitura_direta(self):
        disp = {"Art. 344|caput": _disp(epigrafe="Coação no curso do processo", artigo="344"),
                "Art. 344|parágrafo único": _disp("A pena aumenta-se de 1/3 (um terço) até a metade "
                                                  "se o processo envolver crime contra a dignidade "
                                                  "sexual, cominado neste artigo.",
                                                  marcador="parágrafo único", artigo="344")}
        p = self._propor(disp, "Art. 344|parágrafo único")
        assert len(p) == 1
        m = p[0]["modificador"]
        assert m["escopo"]["artigos"] == ["Art. 344"]
        assert m["fracao_min"] < m["fracao_max"] == 0.5
        # sem linha derivada, o aumento ficaria invisível no CP
        assert m["ignora_embutida"] is True
        assert m["id"] == "aumento-cp-art344-paragrafounico"

    def test_neste_artigo_com_varias_molduras_e_juizo(self):
        disp = {"Art. 133|§ 3º": _disp("As penas cominadas neste artigo aumentam-se de um terço:",
                                       marcador="§ 3º", artigo="133")}
        assert self._propor(disp, "Art. 133|§ 3º") == []

    def test_alvo_que_nao_existe_no_catalogo_nao_vira_modificador(self):
        disp = {"Art. 999|§ 2º": _disp("Na hipótese do § 1º deste artigo, a pena é aumentada de "
                                       "metade.", marcador="§ 2º", artigo="999")}
        assert self._propor(disp, "Art. 999|§ 2º") == []


def test_corpo_do_pr_mostra_modificadores_e_sentinelas(escolha):
    escolha["modificadores"] = [{
        "modificador": {"id": "aumento-cp-art155-p11", "nome": "Furto — §11 (+1/3)",
                        "dispositivo": "CP, art. 155, §11", "natureza": "aumento",
                        "fracao_min": 1 / 3, "fracao_max": 1 / 3,
                        "escopo": {"tipo": "tipos_por_artigo", "lei": "CP", "artigos": ["Art. 155, §10"]}},
        "achado": {}, "lido": "Na hipótese do § 10", "embutida": True,
        "texto": "Na hipótese do § 10 deste artigo, a pena é aumentada de 1/3"}]
    escolha["sentinelas"] = [{"fonte": "cp", "rotulo": "CP", "de": "15.384", "para": "15.517",
                              "evidencia": "(Incluído pela Lei nº 15.517, de 2026)", "ano": 2026}]
    corpo = propor.corpo_pr(escolha, None)
    assert "## Modificadores de escopo declarado" in corpo and "`Art. 155, §10`" in corpo
    assert "## Sentinelas" in corpo and "15.384 → **15.517**" in corpo
    assert "**1** modificador(es) de escopo declarado" in corpo



def test_rodada_de_auditoria_usa_o_auditor_importado(monkeypatch, tmp_path):
    """Até 25/10/2026 a rodada fazia `import auditar`, que não resolve desde que
    cada robô ganhou pasta própria: morria com 1, o código de "nada mecânico"."""
    monkeypatch.setattr(propor.auditoria, "rodar", lambda: [])
    args = SimpleNamespace(aplicar=False, saida=str(tmp_path))
    assert propor._rodada_de_auditoria(args) == 1
