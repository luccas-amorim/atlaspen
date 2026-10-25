# -*- coding: utf-8 -*-
"""Testes da saúde da documentação.

O que importa aqui é a REGRA de vencimento — prazo e dependência —, não o `git`.
As datas de commit são substituídas por um dublê, para o teste não depender do
histórico do repositório em que roda.
"""
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts"))
from arquivista import verificar_documentacao as vd  # noqa: E402

HOJE = date(2026, 8, 2)


def registro(**doc):
    base = {"arquivo": "CONTRIBUTING.md", "sobre": "convenções",
            "conferido_em": "2026-06-01", "depende_de": []}
    return {"cadencia_padrao_dias": 90, "documentos": [{**base, **doc}]}


def com_datas(monkeypatch, datas: dict):
    monkeypatch.setattr(vd, "commit_mais_recente",
                        lambda caminho: datas.get(caminho))


def test_documento_recente_e_sem_dependencia_mudada_esta_em_dia(monkeypatch):
    com_datas(monkeypatch, {"CONTRIBUTING.md": date(2026, 7, 30)})
    v = vd.avaliar(registro(depende_de=["scripts/transform_data.py"]), HOJE)[0]
    assert not v["vencido_por_prazo"] and not v["dependencias_mudaram"]


def test_dependencia_que_mudou_depois_vence_o_documento(monkeypatch):
    """O caso que motivou o verificador: a convenção C7 do CONTRIBUTING mandava
    escrever a pena no `obs`, e o `transform_data` já tinha invertido a regra —
    dentro do prazo, e errado."""
    com_datas(monkeypatch, {
        "CONTRIBUTING.md": date(2026, 7, 20),
        "scripts/transform_data.py": date(2026, 7, 28),
    })
    v = vd.avaliar(registro(depende_de=["scripts/transform_data.py"]), HOJE)[0]
    assert not v["vencido_por_prazo"]
    assert [d["arquivo"] for d in v["dependencias_mudaram"]] == ["scripts/transform_data.py"]


def test_editar_o_documento_conta_como_conferi_lo(monkeypatch):
    """Quem mexeu no texto o leu: a data efetiva é a do commit, e a dependência
    mudada ANTES dele deixa de pesar."""
    com_datas(monkeypatch, {
        "CONTRIBUTING.md": date(2026, 8, 1),
        "scripts/transform_data.py": date(2026, 7, 28),
    })
    v = vd.avaliar(registro(depende_de=["scripts/transform_data.py"]), HOJE)[0]
    assert v["conferido_em"] == "2026-08-01" and not v["dependencias_mudaram"]


def test_prazo_vencido_mesmo_sem_dependencia(monkeypatch):
    com_datas(monkeypatch, {"CONTRIBUTING.md": date(2026, 1, 10)})
    v = vd.avaliar(registro(conferido_em="2026-01-10"), HOJE)[0]
    assert v["vencido_por_prazo"] and v["dias"] > 90


def test_arquivo_que_sumiu_e_registro_orfao(monkeypatch):
    com_datas(monkeypatch, {})
    v = vd.avaliar(registro(arquivo="docs/nao-existe.md"), HOJE)[0]
    assert not v["existe"]
    assert "não existe" in vd.montar_relatorio([v])


def test_relatorio_diz_o_que_vencer_significa(monkeypatch):
    com_datas(monkeypatch, {"CONTRIBUTING.md": date(2026, 1, 10)})
    texto = vd.montar_relatorio(vd.avaliar(registro(conferido_em="2026-01-10"), HOJE))
    assert "não quer dizer que esteja errado" in texto


def test_registro_real_do_projeto_e_coerente():
    """Todo documento registrado existe, e todo .md explicativo está registrado."""
    import json
    registro_real = json.loads((RAIZ / "data" / "documentacao.json").read_text(encoding="utf-8"))
    declarados = {d["arquivo"] for d in registro_real["documentos"]}
    for arquivo in declarados:
        assert (RAIZ / arquivo).exists(), f"{arquivo} está no registro e não existe"
    # Tudo o que está em docs/ vai ao ar — a raiz é o grupo "Documentação" da
    # barra lateral, docs/textos/ é o grupo "Textos". O gerado não entra, porque
    # quem o mantém é o gerador, e não a prosa.
    gerados = {"docs/completude.md"}
    publicados = {f"docs/{p.name}" for p in (RAIZ / "docs").glob("*.md")}
    publicados |= {f"docs/textos/{p.name}" for p in (RAIZ / "docs" / "textos").glob("*.md")}
    assert not (publicados - gerados - declarados), "documento publicado fora do registro"


def _repo_git(tmp_path, monkeypatch):
    """Um repositório de verdade: aqui o que se testa é a leitura do `git`.

    As datas são fixadas pelo ambiente, e a de COMMITTER junto com a de autor —
    é a de committer que o verificador lê (`%cI`). Sem fixar as duas, os dois
    commits do teste nasceriam no mesmo segundo e o teste passaria à toa.
    """
    import subprocess

    def git(*args, em: str | None = None):
        env = None
        if em:
            import os
            env = {**os.environ, "GIT_AUTHOR_DATE": em, "GIT_COMMITTER_DATE": em}
        return subprocess.run(["git", *args], cwd=tmp_path, env=env,
                              capture_output=True, text=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")
    monkeypatch.setattr(vd, "RAIZ", tmp_path)
    return git


def test_mover_o_arquivo_nao_conta_como_releitura(tmp_path, monkeypatch):
    """`git mv` toca o caminho sem que ninguém leia uma linha.

    Foi o que aconteceu em 24/09/2026, quando `textos/` foi para dentro de
    `docs/`: o movimento sozinho limpou a marca que o Arquivista mantinha sobre
    a história do projeto, que continuava esperando reescrita.
    """
    git = _repo_git(tmp_path, monkeypatch)
    (tmp_path / "texto.md").write_text("a prosa\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "escrito", em="2026-01-10T12:00:00")

    (tmp_path / "docs").mkdir()
    git("mv", "texto.md", "docs/texto.md")
    git("commit", "-q", "-m", "so muda de lugar", em="2026-09-24T12:00:00")

    assert vd.commit_mais_recente("docs/texto.md") == date(2026, 1, 10)


def test_mover_com_edicao_conta_como_releitura(tmp_path, monkeypatch):
    """Quem reescreve ao mudar de lugar leu o que reescreveu."""
    git = _repo_git(tmp_path, monkeypatch)
    (tmp_path / "texto.md").write_text("a prosa\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "escrito", em="2026-01-10T12:00:00")

    (tmp_path / "docs").mkdir()
    git("mv", "texto.md", "docs/texto.md")
    (tmp_path / "docs" / "texto.md").write_text(
        "a prosa, outra\ne mais uma linha\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "muda de lugar e reescreve", em="2026-09-24T12:00:00")

    assert vd.commit_mais_recente("docs/texto.md") == date(2026, 9, 24)


def test_saida_em_pasta_que_ainda_nao_existe(tmp_path, monkeypatch):
    """No checkout limpo da CI, `crawler/relatorios/` não existe.

    Até 25/10/2026 o Arquivista quebrava aí toda semana, e a triagem lia a
    quebra como "documentação em dia".
    """
    import io
    monkeypatch.setattr(vd, "avaliar", lambda registro: [])
    # `main` embrulha o `sys.stdout.buffer` num wrapper novo; sem a referência,
    # o falso é coletado e fecha o buffer que o novo usa.
    falso = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", falso)
    destino = tmp_path / "crawler" / "relatorios" / "documentacao.md"
    monkeypatch.setattr(sys, "argv", ["verificar_documentacao.py", "--saida", str(destino)])

    assert vd.main() == 0
    assert destino.exists()
