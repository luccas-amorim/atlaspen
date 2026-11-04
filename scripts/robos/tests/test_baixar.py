# -*- coding: utf-8 -*-
"""O download só ocupa o caminho canônico depois de passar pela sentinela.

Até 25/09/2026 `baixar_fonte` gravava a página direto em `<data>.html` e anotava
`sentinela_ok` só no `meta.json`, que nenhum consumidor lê: o Vigia, os auditores
e o histórico varrem os `.html` por `glob`. Um snapshot truncado ou servido de
cache velho tomava o lugar do bom, e a rodada seguinte comparava o catálogo com
ele — em silêncio, que é o modo de falhar que mais dói aqui.
"""
import json
import sys
from datetime import date

from nucleo import baixar

FONTE = {"id": "cp", "url": "https://exemplo.test/cp", "sentinela": "Lei nº 15.517, de 2026",
         "rotulos": ["CP"]}


def _com_pagina(monkeypatch, html: str):
    monkeypatch.setattr(baixar, "buscar", lambda url: html.encode("utf-8"))
    monkeypatch.setattr(baixar, "hoje", lambda: date(2026, 9, 25))


def test_sentinela_presente_promove_ao_caminho_canonico(tmp_path, monkeypatch):
    _com_pagina(monkeypatch, "<html>Art. 1º … (Redação dada pela Lei nº 15.517, de 2026)</html>")
    meta = baixar.baixar_fonte(FONTE, tmp_path)
    assert meta["sentinela_ok"] is True
    assert (tmp_path / "cp" / "2026-09-25.html").exists()
    assert not (tmp_path / "cp" / "2026-09-25.html.part").exists()
    assert meta["arquivo"] == "2026-09-25.html"


def test_sentinela_ausente_nao_ocupa_o_caminho_canonico(tmp_path, monkeypatch):
    """A página velha fica em `.part`, fora do `glob("*.html")` dos consumidores."""
    _com_pagina(monkeypatch, "<html>Art. 1º … (Redação dada pela Lei nº 13.964, de 2019)</html>")
    meta = baixar.baixar_fonte(FONTE, tmp_path)
    assert meta["sentinela_ok"] is False
    assert not (tmp_path / "cp" / "2026-09-25.html").exists()
    assert (tmp_path / "cp" / "2026-09-25.html.part").exists()
    assert meta["arquivo"] == "2026-09-25.html.part"
    assert sorted(p.name for p in (tmp_path / "cp").glob("*.html")) == []


def test_snapshot_bom_anterior_sobrevive_ao_download_ruim(tmp_path, monkeypatch):
    """O que os consumidores veem depois de um download reprovado é o último
    snapshot que PASSOU — e o Vigia avisa a idade dele no relatório."""
    (tmp_path / "cp").mkdir()
    (tmp_path / "cp" / "2026-09-18.html").write_text("bom", encoding="utf-8")
    _com_pagina(monkeypatch, "<html>página truncada</html>")
    baixar.baixar_fonte(FONTE, tmp_path)
    assert [p.name for p in sorted((tmp_path / "cp").glob("*.html"))] == ["2026-09-18.html"]


def test_sem_sentinela_declarada_promove(tmp_path, monkeypatch):
    """Fonte sem sentinela não tem o que conferir: passa, como antes."""
    _com_pagina(monkeypatch, "<html>qualquer coisa</html>")
    meta = baixar.baixar_fonte({**FONTE, "sentinela": ""}, tmp_path)
    assert meta["sentinela_ok"] is True
    assert meta["bloqueio"] is None
    assert (tmp_path / "cp" / "2026-09-25.html").exists()


# A página que o firewall da Presidência serviu, com HTTP 200 e em windows-1252,
# no lugar de cada compilado da rodada de 02/11/2026 (issue #96).
BLOQUEIO = """<html><head><title>Acesso Negado!</title></head><body><table border="0" \
cellpadding="0" cellspacing="0" width="70%">\r
  <tr>\r
    <td width="14%"><p align="center"><img src="http://www.planalto.gov.br/Brastra.gif"\r
    alt="Brastra.gif (4376 bytes)" width="74" height="82"></td>\r
  </tr>\r
</table> <br><br>Esta requisição foi bloqueada. <br><br>\r
Em caso de dúvida, por favor envie o código 13376840597241759405 no assunto da mensagem \
para o endereço eletrônico <a href="mailto:bloqueio.de.aplicacoes@presidencia.gov.br">\
bloqueio.de.aplicacoes@presidencia.gov.br</a>.<br><br>\r
\r
Diretoria de Tecnologia da Presidência da República.<br><br>\r
<a href='javascript:history.back();'>[Go Back]</a></body></html>"""


def _bloqueado(monkeypatch):
    monkeypatch.setattr(baixar, "buscar", lambda url: BLOQUEIO.encode("windows-1252"))
    monkeypatch.setattr(baixar, "hoje", lambda: date(2026, 11, 2))


def test_pagina_de_bloqueio_sai_com_o_codigo(tmp_path, monkeypatch):
    _bloqueado(monkeypatch)
    meta = baixar.baixar_fonte(FONTE, tmp_path)
    assert meta["bloqueio"] == "13376840597241759405"
    assert meta["sentinela_ok"] is False
    assert list((tmp_path / "cp").glob("*.html")) == []


def test_pagina_de_bloqueio_nao_passa_nem_sem_sentinela(tmp_path, monkeypatch):
    """Sem sentinela a fonte passava com qualquer página — a de bloqueio inclusive."""
    _bloqueado(monkeypatch)
    meta = baixar.baixar_fonte({**FONTE, "sentinela": ""}, tmp_path)
    assert meta["sentinela_ok"] is False
    assert list((tmp_path / "cp").glob("*.html")) == []


def test_lei_que_cita_o_bloqueio_de_aplicacoes_nao_e_bloqueio():
    """A marca é o endereço do firewall, não a palavra 'bloqueio', que é de lei."""
    assert baixar.bloqueio("Art. 1º O bloqueio de bens … código 123") is None


def _rodar_main(tmp_path, monkeypatch, capfd, n_fontes: int) -> tuple[int, str, int]:
    fontes = [{**FONTE, "id": f"f{i}", "url": f"https://exemplo.test/{i}"}
              for i in range(n_fontes)]
    arquivo = tmp_path / "fontes.json"
    arquivo.write_text(json.dumps({"fontes": fontes}), encoding="utf-8")
    pedidos = []
    monkeypatch.setattr(baixar, "FONTES", arquivo)
    monkeypatch.setattr(baixar, "CORTESIA_S", 0)
    monkeypatch.setattr(baixar, "buscar",
                        lambda url: pedidos.append(url) or BLOQUEIO.encode("windows-1252"))
    monkeypatch.setattr(baixar, "hoje", lambda: date(2026, 11, 2))
    monkeypatch.setattr(sys, "argv", ["baixar.py", "--todas", "--saida", str(tmp_path / "s")])
    # O `main` troca o `sys.stdout`; o monkeypatch o devolve ao fim do teste.
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    codigo = baixar.main()
    sys.stdout.flush()
    return codigo, capfd.readouterr().out, len(pedidos)


def test_bloqueios_seguidos_encerram_a_rodada(tmp_path, monkeypatch, capfd):
    """Insistir contra o firewall só alonga o bloqueio: param as requisições, e
    a saída diz que é bloqueio, com o código, antes da lista de falhas."""
    codigo, saida, pedidos = _rodar_main(tmp_path, monkeypatch, capfd, 10)
    assert codigo == 2
    assert pedidos == baixar.BLOQUEIOS_SEGUIDOS
    assert "0/10 fontes íntegras." in saida
    assert "BLOQUEIO:" in saida and "13376840597241759405" in saida
    assert saida.index("BLOQUEIO:") < saida.index("Falhas:")
    assert "f9: não tentada: o Planalto bloqueou as anteriores" in saida
    assert "sentinela ausente" not in saida
