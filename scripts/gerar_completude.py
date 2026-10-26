# -*- coding: utf-8 -*-
"""Gera docs/completude.md.

Ambas são DERIVADAS de ``data/diplomas.json`` (denominador da Fase 1) e de
``data/crimes.json`` (o catálogo). ``completude.md`` traz o índice de diplomas
vigentes com o total de tipos coletados e a situação de cada um;
``acervo-historico.md`` lista os diplomas revogados/não recepcionados e a meta
do acervo (v1.3.0). Não edite os ``.md`` à mão — regenere com:

    python scripts/gerar_completude.py

Rode após qualquer mudança em ``data/crimes.json`` ou ``data/diplomas.json``.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "robos"))
from nucleo.tempo import hoje  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

# Diplomas cuja coleta AINDA tem preceitos faltando (a conferência dispositivo
# a dispositivo, via scripts/diff_tipos.py, encontrou lacunas genuínas). Fora
# desta lista, um diploma com coleta é dado como "concluído" — no sentido de
# que a revisão não localizou preceito faltante, sempre passível de erro.
# O CPM saiu daqui em 20/09/2026: marcado em 21/07, antes da revisão que fechou a
# base, ele tinha 351 preceitos no texto e ZERO sem registro casado no comparador
# de tipos (scripts/diff_tipos.py cpm), e o Vigia não acusava nenhum artigo
# ausente. Uma marca que ninguém revisita diz ao leitor uma lacuna que não existe.
INCOMPLETOS: set[str] = set()

# Os dispositivos do acervo histórico vivem em data/acervo.json — a mesma fonte
# que o site lê em /acervo. Eram duas constantes daqui (os casos identificados
# na conferência e os tipos retirados do catálogo por revogação); passaram a
# dado para que o acervo não seja uma transcrição à mão da tabela deste
# gerador.
#
# Só entra no acervo o que a LEI tirou de vigência. Registro que saiu porque
# estava errado (duplicata, infração administrativa, texto de outro diploma) não
# é acervo histórico: isso é descrito na nota da versão em que saiu. Misturar as
# duas coisas transformaria o acervo — que é material de pesquisa sobre o que já
# foi crime no Brasil — num histórico dos nossos enganos.
CATEGORIAS_ACERVO = {"revogado": "revogado", "nao_recepcionado": "não recepcionado", "vetado": "vetado",
                     "vigencia_encerrada": "vigência encerrada"}


def validar_acervo() -> None:
    """A única trava de `data/acervo.json`: campo obrigatório, categoria e id.

    Nasceu servindo à tabela de `docs/acervo-historico.md`, que saiu na v2.2.0
    quando o acervo ganhou página própria. A tabela foi embora; a validação
    fica, porque continua sendo a única — o site lê o arquivo, não o confere.
    """
    dados = json.loads((RAIZ / "data" / "acervo.json").read_text(encoding="utf-8"))
    registros = dados["registros"]
    ids: set[str] = set()
    for r in registros:
        faltando = [c for c in ("id", "dispositivo", "nome", "categoria", "o_que_houve", "normas") if not r.get(c)]
        if faltando:
            raise SystemExit(f"data/acervo.json: registro {r.get('id')!r} sem {', '.join(faltando)}")
        if r["categoria"] not in CATEGORIAS_ACERVO:
            raise SystemExit(f"data/acervo.json: categoria desconhecida em {r['id']!r}: {r['categoria']!r}")
        if r["id"] in ids:
            raise SystemExit(f"data/acervo.json: id repetido: {r['id']!r}")
        ids.add(r["id"])


def main() -> int:
    validar_acervo()
    inventario = json.loads((RAIZ / "data" / "diplomas.json").read_text(encoding="utf-8"))
    catalogo = json.loads((RAIZ / "data" / "crimes.json").read_text(encoding="utf-8"))

    rotulo_para_slug: dict[str, str] = {}
    for d in inventario["diplomas"]:
        for rotulo in d.get("rotulos_catalogo", []):
            rotulo_para_slug[rotulo] = d["id"]

    tipos_por_slug: dict[str, list[dict]] = {}
    orfaos: dict[str, int] = {}
    for registro in catalogo:
        slug = rotulo_para_slug.get(registro["lei"])
        if slug is None:
            orfaos[registro["lei"]] = orfaos.get(registro["lei"], 0) + 1
        else:
            tipos_por_slug.setdefault(slug, []).append(registro)
    for rotulo, n in sorted(orfaos.items()):
        print(f"AVISO: rótulo sem diploma no inventário: {rotulo!r} ({n})", file=sys.stderr)

    vigentes = [d for d in inventario["diplomas"] if d["situacao"] == "vigente"]
    historicos = [d for d in inventario["diplomas"] if d["situacao"] != "vigente"]
    total_preceitos = inventario["_meta"]["total_preceitos_esperados"]
    # O índice só lista diplomas que TÊM tipo penal a coletar. Diploma vigente
    # sem preceito algum (ex.: Lei 9.807/99, cujo único crime foi vetado na
    # sanção) não é lacuna — não entra, para não aparecer como "não iniciado".
    indice = [d for d in vigentes
              if d["preceitos_esperados"] > 0 or tipos_por_slug.get(d["id"])]
    com_coleta = [d for d in indice if tipos_por_slug.get(d["id"])]

    def situacao(d: dict) -> str:
        if not tipos_por_slug.get(d["id"]):
            return "⛔ não iniciado"
        if d["id"] in INCOMPLETOS:
            return "🔶 em coleta"
        return "concluído ❓"

    # Quando TODOS estão concluídos, a coluna Situação é uma coluna inteira da
    # mesma palavra e "com coleta iniciada" repete a linha de cima. Aí o que
    # informa é uma frase de resumo, e a linha redundante sai.
    todos_concluidos = all(situacao(d) == "concluído ❓" for d in indice)

    # A página diz quanto foi conferido; tem de dizer também QUANDO, e de que
    # commit — o mesmo carimbo que a aba Leia-me da planilha já traz. Planilha
    # e página são fotografias, e fotografia sem data é citação do que já mudou.
    gerado_em = hoje().isoformat()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=RAIZ,
                                capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        commit = None

    L: list[str] = []
    p = L.append
    p("---")
    p("id: completude")
    p("title: Completude do catálogo")
    p("sidebar_position: 2")
    p(f"gerado_em: '{gerado_em}'")
    # Entre aspas: um hash só de dígitos viraria número no YAML.
    p(f"commit: {repr(commit) if commit else 'null'}")
    p("---")
    p("")
    p("{/* GERADO AUTOMATICAMENTE por scripts/gerar_completude.py — não edite à mão. */}")
    p("")
    p("# Completude do catálogo")
    p("")
    p(":::note[Página gerada]")
    p("Este acompanhamento é derivado de `data/diplomas.json` (o denominador da")
    p("conferência do catálogo) e de")
    p(f"`data/crimes.json` (o catálogo), gerado em {gerado_em}"
      + (f" a partir do commit `{commit}`" if commit else "") + ". Para atualizá-lo:")
    p("`python scripts/gerar_completude.py`.")
    p(":::")
    p("")
    p("| Indicador | Valor |")
    p("|---|---|")
    p(f"| Tipos penais catalogados | **{len(catalogo)}** |")
    p(f"| Diplomas com tipo penal vigente | {len(indice)} |")
    if not todos_concluidos:
        p(f"| — com coleta iniciada | {len(com_coleta)} |")
    p(f"| Diplomas revogados/não recepcionados | [{len(historicos)}](/acervo) |")
    p("")

    # ------------------------------------------------------------------ índice
    p("## Índice por diploma")
    p("")
    p(":::note[O que significa a situação]")
    p("**concluído ❓** — a conferência dispositivo a dispositivo não localizou "
      "nenhum preceito faltante após as revisões. Não é uma garantia: o "
      "denominador real (quantos tipos a lei comporta) não é conhecido com "
      "certeza, então este estado é **passível de erro** e pode voltar a "
      "\"em coleta\" se uma revisão futura encontrar algo. **em coleta** — há "
      "preceitos sabidamente faltando. **não iniciado** — nenhum tipo reunido "
      "ainda. A pergunta — quantos tipos penais existem — é a que abre a "
      "[História do projeto](/projeto).")
    p(":::")
    p("")
    if todos_concluidos:
        p(f"Todos os {len(indice)} diplomas com tipo penal vigente estão concluídos: a "
          "conferência dispositivo a dispositivo não localizou preceito faltante.")
        p("")
    p("| Diploma | Tipos coletados | Situação |")
    p("|---|---:|---|")
    ordem = sorted(indice, key=lambda d: (-len(tipos_por_slug.get(d["id"], [])),
                                          -d["preceitos_esperados"]))
    for d in ordem:
        n = len(tipos_por_slug.get(d["id"], []))
        p(f"| {d['nome']} | {n} | {situacao(d)} |")
    # `1 tipos` não existe: a pluralização mora em quem RENDERIZA a tabela
    # (completude.astro); aqui a coluna é só o número, e o cabeçalho é plural
    # porque a maioria das linhas o é.
    p("")
    p("A lista completa dos tipos já reunidos, com o texto de cada um, está na "
      "[busca por tipo penal](/tipos).")
    p("")

    destino = RAIZ / "docs" / "completude.md"
    with open(destino, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
        fh.write("\n")
    print(f"escrito {destino} ({len(L)} linhas)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
