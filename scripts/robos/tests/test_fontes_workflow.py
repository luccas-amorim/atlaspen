# -*- coding: utf-8 -*-
"""A montagem do corpo da issue, no passo "Abrir issue se alguma fonte falhou"
do `fontes.yml`, rodada de verdade no bash, com `-eo pipefail` como no runner,
e sem chamar o `gh`.

A issue #96 (31/10/2026) mostrou o `tail -n 40` da saída de `baixar.py`: 40
linhas de "sentinela ausente", sem o "0/77" que dizia que tinham falhado todas,
e com a instrução de conferir sentinela e URL — quando o que havia era o
firewall da Presidência bloqueando o runner.
"""
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "fontes.yml"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="sem bash")


def _montagem() -> str:
    """O `run` do passo, cortado antes das chamadas ao gh. Lido pelo texto: a
    CI não tem PyYAML, e um teste não justifica a dependência."""
    texto = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    passo = texto[texto.index("- name: Abrir issue se alguma fonte falhou"):]
    bloco = passo[passo.index("run: |\n") + len("run: |\n"):]
    linhas = []
    for linha in bloco.split("\n"):
        if linha.strip() and not linha.startswith(" " * 10):
            break
        linhas.append(linha)
    script = textwrap.dedent("\n".join(linhas))
    return script[:script.index("ABERTA=")]


def _corpo(tmp_path: Path, saida: str) -> str:
    (tmp_path / "saida.txt").write_text(saida, encoding="utf-8")
    p = subprocess.run(["bash", "-eo", "pipefail", "-c", _montagem()], cwd=tmp_path,
                       capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "TZ": "UTC"})
    assert p.returncode == 0, p.stderr
    return (tmp_path / "corpo.md").read_text(encoding="utf-8")


def _linhas(n: int, motivo: str) -> list[str]:
    return [f"  f{i}: {motivo}" for i in range(n)]


def test_bloqueio_vem_no_topo_e_a_lista_vem_inteira(tmp_path):
    saida = "\n".join([
        *(f"[{i + 1:2d}/77] ✗ f{i}  bloqueado pelo Planalto (código 1337)" for i in range(3)),
        "",
        "3 bloqueios seguidos: as 74 fontes restantes não foram tentadas.",
        "",
        "0/77 fontes íntegras.",
        'BLOQUEIO: o Planalto devolveu a página "Acesso Negado" em 3 requisição(ões). '
        "Não é sentinela nem URL: é o IP de quem baixou.",
        "Falhas:",
        *_linhas(77, "não tentada: o Planalto bloqueou as anteriores"),
    ]) + "\n"
    corpo = _corpo(tmp_path, saida)
    assert "**0/77 fontes íntegras.**" in corpo
    assert '> o Planalto devolveu a página "Acesso Negado"' in corpo
    assert corpo.index("Acesso Negado") < corpo.index("Falhas:")
    assert "o que mudou é a `sentinela`" not in corpo
    assert "  f0: " in corpo and "  f76: " in corpo   # nada cortado


def test_sentinela_ausente_mantem_a_orientacao_de_sempre(tmp_path):
    saida = "\n".join([
        "[ 1/2] ✗ cp  sentinela ausente: '15.517' (windows-1252)",
        "[ 2/2] ✓ cpm   12345B  windows-1252",
        "",
        "1/2 fontes íntegras.",
        "Falhas:",
        "  cp: sentinela ausente: '15.517'",
    ]) + "\n"
    corpo = _corpo(tmp_path, saida)
    assert "**1/2 fontes íntegras.**" in corpo
    assert "o que mudou é a `sentinela`" in corpo
    assert "[!WARNING]" not in corpo
    assert "  cp: sentinela ausente: '15.517'" in corpo
    assert "[ 2/2]" not in corpo                          # só a lista de falhas


def test_script_que_caiu_mostra_o_rabo_da_saida(tmp_path):
    """Sem placar nem lista, o que importa é o traceback."""
    saida = "Traceback (most recent call last):\nKeyError: 'fontes'\n"
    corpo = _corpo(tmp_path, saida)
    assert "KeyError: 'fontes'" in corpo
