# -*- coding: utf-8 -*-
"""A montagem do corpo da issue, no passo "Abrir issue com os achados" do
`conferidor.yml`, rodada de verdade no bash, com `-e` como no runner, contra
relatórios de véspera e sem chamar o `gh`.

A rodada manual de 25/10/2026 começou às 23h41 de Brasília e a triagem rodou
depois da meia-noite: procurou relatórios de 26/10, os robôs tinham datado os
seus de 25, e a issue #51 saiu sem tribunais, cotejos e DOU.
"""
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "conferidor.yml"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="sem bash")


def _montagem() -> str:
    """O `run` do passo, cortado antes das chamadas ao gh. Lido pelo texto: a
    CI não tem PyYAML, e um teste não justifica a dependência."""
    texto = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    passo = texto[texto.index("- name: Abrir issue com os achados"):]
    bloco = passo[passo.index("run: |\n") + len("run: |\n"):]
    linhas = []
    for linha in bloco.split("\n"):
        if linha.strip() and not linha.startswith(" " * 10):
            break
        linhas.append(linha)
    script = textwrap.dedent("\n".join(linhas))
    script = script[:script.index('REPO="${{ github.repository }}"')]
    return script.replace("${{ github.run_number }}", "16") + '\necho "TITULO=$HOJE"\n'


def _rodar(tmp_path: Path, arquivos: dict[str, str]) -> tuple[str, str]:
    r = tmp_path / "crawler" / "relatorios"
    r.mkdir(parents=True)
    for nome, conteudo in arquivos.items():
        (r / nome).write_text(conteudo, encoding="utf-8")
    p = subprocess.run(["bash", "-e", "-c", _montagem()], cwd=tmp_path, capture_output=True,
                       text=True, encoding="utf-8", env={**os.environ, "TZ": "UTC"})
    assert p.returncode == 0, p.stderr
    corpo = (tmp_path / "corpo.md").read_text(encoding="utf-8")
    return corpo, re.search(r"TITULO=(\S+)", p.stdout).group(1)


def test_rodada_que_vira_a_meia_noite(tmp_path):
    corpo, titulo = _rodar(tmp_path, {
        "2026-10-25-resumo.md": "RESUMO-VIGIA\n", "2026-10-25.md": "COMPLETO-VIGIA\n",
        "dou-2026-10-25.md": "DOU\n", "auditoria-2026-10-25.md": "AUDITORIA\n",
        "documentacao.md": "DOCS\n", "cotejo-frescor-2026-10-25.md": "FRESCOR\n",
        "cotejo-textos-2026-10-25.md": "TEXTOS\n", "tribunais-2026-10-26.md": "TRIBUNAIS\n",
        "quebrados.md": "QUEBRADOS\n", "leis-do-ano-2026.md": "LEIS\n",
        "curadoria-2026-10-25.md": "CURADOR\n",
    })
    for marca in ("RESUMO-VIGIA", "DOU", "AUDITORIA", "DOCS", "FRESCOR", "TEXTOS", "TRIBUNAIS",
                  "QUEBRADOS", "LEIS", "CURADOR"):
        assert marca in corpo, marca
    assert "COMPLETO-VIGIA" not in corpo          # o completo só entra sem resumo
    assert titulo == "2026-10-25"                  # o dia em que a rodada começou
    assert corpo.index("QUEBRADOS") < corpo.index("RESUMO-VIGIA") < corpo.index("TRIBUNAIS")


def test_sem_resumo_entra_o_completo(tmp_path):
    corpo, _ = _rodar(tmp_path, {"2026-10-25.md": "COMPLETO-VIGIA\n"})
    assert "COMPLETO-VIGIA" in corpo


def test_sem_relatorio_datado_nao_quebra(tmp_path):
    corpo, titulo = _rodar(tmp_path, {"documentacao.md": "DOCS\n"})
    assert "DOCS" in corpo and re.fullmatch(r"\d{4}-\d{2}-\d{2}", titulo)
