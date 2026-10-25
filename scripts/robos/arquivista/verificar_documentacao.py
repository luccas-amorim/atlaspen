# -*- coding: utf-8 -*-
"""Saúde da documentação: quem envelheceu, e por quê.

A conferência semanal vigia o dado. Este script vigia a **prosa**, com a mesma
lógica: um documento não é confiável só porque existe — é confiável enquanto o
que ele descreve não mudou.

Duas perguntas, por documento:

1. **Passou da cadência?** Noventa dias, por padrão. É o piso: documento que
   ninguém relê há um trimestre merece uma olhada, mesmo que nada tenha mudado.
2. **Mudou algo de que ele fala?** Cada documento declara suas dependências em
   `data/documentacao.json`. Se um arquivo dependente foi commitado DEPOIS da
   última conferência, o documento vence — mesmo dentro do prazo.

A segunda pergunta é a que importa. Na revisão de 01/08/2026, a convenção C7 do
`CONTRIBUTING.md` ainda mandava escrever a pena no campo `obs`; a regra tinha
sido invertida meses antes, no `transform_data.py`, e o prazo do documento nem
havia corrido. Prazo é relógio; dependência é sinal.

Editar o documento conta como conferi-lo: a data efetiva é a maior entre o
`conferido_em` do registro e o último commit do próprio arquivo. Assim só há
escrituração manual quando alguém relê e **não** encontra o que corrigir.

Uso:
    python scripts/robos/arquivista/verificar_documentacao.py            # relatório
    python scripts/robos/arquivista/verificar_documentacao.py --md       # em markdown, p/ a issue

Saídas: 0 = tudo em dia; 2 = erro; 3 = há documento vencido.
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
# `scripts/robos` para os pacotes dos robôs e do núcleo; `scripts` para o
# `pena_parser`, que é compartilhado com o construtor do catálogo e por isso
# não mora aqui.
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
REGISTRO = RAIZ / "data" / "documentacao.json"


# Separador de commits no `git log`, para não confundir com o texto de nenhuma
# linha de status. É o `%x01` do formato, escrito aqui uma vez só.
_SEP = chr(1)


def commit_mais_recente(caminho: str) -> date | None:
    """Data do último commit que MUDOU o caminho (arquivo ou diretório).

    **Mudar de lugar não é mudar.** O `git mv` toca o caminho sem que ninguém
    releia uma linha, e a regra "editar é conferir" tomava isso por leitura. Na
    reorganização de 24/09/2026, que levou `textos/` para dentro de `docs/`, o
    movimento sozinho limpou a marca que o Arquivista mantinha sobre a história
    do projeto: o documento continuava esperando reescrita, e o relatório passou
    a dizer que estava em dia. Falha silenciosa, que é a que mais dói.

    Renomeação COM edição (`R097` e afins) continua contando — ali houve
    leitura. Só o `R100`, o mesmo conteúdo noutro lugar, é ignorado.

    Em diretório a ressalva não se aplica: `--follow` exige um arquivo, e mover
    algo para dentro de um diretório é, de fato, mudá-lo.
    """
    e_arquivo = (RAIZ / caminho).is_file()
    cmd = ["git", "log", f"--format=%x01%cI"]
    cmd += ["--follow", "--name-status"] if e_arquivo else ["-1"]
    try:
        saida = subprocess.run(cmd + ["--", caminho],
                               cwd=RAIZ, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None

    if not e_arquivo:
        bruto = saida.stdout.replace(_SEP, "").strip()
        return datetime.fromisoformat(bruto).date() if bruto else None

    for bloco in saida.stdout.split(_SEP)[1:]:
        linhas = [l for l in bloco.splitlines() if l.strip()]
        if not linhas:
            continue
        estados = [l.split("\t")[0] for l in linhas[1:]]
        if estados and all(e == "R100" for e in estados):
            continue
        return datetime.fromisoformat(linhas[0].strip()).date()
    return None


def avaliar(registro: dict, hoje: date | None = None) -> list[dict]:
    """Um veredito por documento, com o motivo do vencimento."""
    hoje = hoje or date.today()
    cadencia = registro.get("cadencia_padrao_dias", 90)
    veredito = []
    for doc in registro["documentos"]:
        arquivo = doc["arquivo"]
        declarado = date.fromisoformat(doc["conferido_em"])
        proprio = commit_mais_recente(arquivo)
        # Editar é conferir: quem mexeu no texto o leu.
        efetivo = max(declarado, proprio) if proprio else declarado

        atrasadas = []
        for dep in doc.get("depende_de", []):
            quando = commit_mais_recente(dep)
            if quando and quando > efetivo:
                atrasadas.append((dep, quando))

        dias = (hoje - efetivo).days
        limite = doc.get("cadencia_dias", cadencia)
        veredito.append({
            "arquivo": arquivo,
            "sobre": doc.get("sobre", ""),
            "conferido_em": efetivo.isoformat(),
            "dias": dias,
            "vencido_por_prazo": dias > limite,
            "dependencias_mudaram": [
                {"arquivo": d, "em": q.isoformat()} for d, q in sorted(atrasadas)],
            "existe": (RAIZ / arquivo).exists(),
        })
    return veredito


def desatualizados(veredito: list[dict]) -> list[dict]:
    return [v for v in veredito
            if v["vencido_por_prazo"] or v["dependencias_mudaram"] or not v["existe"]]


def montar_relatorio(veredito: list[dict]) -> str:
    vencidos = desatualizados(veredito)
    L = ["## Saúde da documentação", ""]
    if not vencidos:
        L += [f"Os {len(veredito)} documentos registrados estão em dia — nenhum passou "
              "da cadência e nenhuma dependência mudou desde a última conferência.", ""]
        return "\n".join(L) + "\n"

    L += [f"**{len(vencidos)}** de {len(veredito)} documento(s) a reler.", "",
          "> Vencer não quer dizer que esteja errado: quer dizer que ninguém confirmou "
          "que continua certo. Ao reler e nada mudar, atualize `conferido_em` em "
          "`data/documentacao.json`; ao corrigir, o próprio commit responde.", ""]
    for v in vencidos:
        L.append(f"### `{v['arquivo']}`")
        L.append("")
        if not v["existe"]:
            L += ["- ⚠️ **arquivo não existe** — registro órfão em `data/documentacao.json`", ""]
            continue
        L.append(f"- {v['sobre']}")
        L.append(f"- conferido pela última vez em {v['conferido_em']} ({v['dias']} dias)")
        if v["vencido_por_prazo"]:
            L.append("- **passou da cadência**")
        for dep in v["dependencias_mudaram"]:
            L.append(f"- **mudou depois disso:** `{dep['arquivo']}` (em {dep['em']})")
        L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Verifica a saúde da documentação.")
    p.add_argument("--md", action="store_true", help="imprime o relatório em markdown")
    p.add_argument("--saida", help="grava o markdown neste arquivo")
    args = p.parse_args()

    registro = json.loads(REGISTRO.read_text(encoding="utf-8"))
    veredito = avaliar(registro)
    relatorio = montar_relatorio(veredito)

    if args.saida:
        # No checkout limpo da CI, `crawler/relatorios/` não existe: até
        # 25/10/2026 o Arquivista quebrava aqui toda semana, e a quebra passava
        # por "documentação em dia".
        saida = Path(args.saida)
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(relatorio, encoding="utf-8")
    if args.md or args.saida:
        print(relatorio)
    else:
        for v in veredito:
            marca = "!" if (v["vencido_por_prazo"] or v["dependencias_mudaram"]) else "."
            print(f"{marca} {v['arquivo']:45s} {v['conferido_em']}  "
                  f"{v['dias']:4d}d  deps atrasadas: {len(v['dependencias_mudaram'])}")
    return 3 if desatualizados(veredito) else 0


if __name__ == "__main__":
    raise SystemExit(main())
