# -*- coding: utf-8 -*-
"""O repositório ctresb/leis, lido pela API do GitHub — só para observar.

https://github.com/ctresb/leis converte para Markdown a legislação brasileira a
partir do normas.leg.br, do Senado e do Planalto. Criado em 15/10/2026, operado
por agentes de IA (o `WORKLOG.md` dele diz isso), MIT no código. O plano de
fontes abertas decidiu, em 25/10/2026, só observá-lo: o que muda nos `scripts/`
dele é o que pode valer a pena aprender, e o que muda no arquivo de um diploma
que vigiamos é um terceiro olhar sobre o mesmo texto. Nunca é fonte de dado e
nunca é dependência: se a leitura falha, o relatório diz que não leu, e só.

Sem clone: são 4 GB. A API do GitHub responde por caminho; sem token, o teto é
de 60 requisições por hora, e uma rodada usa ~70 — na CI, o `GITHUB_TOKEN` do
job sobe o teto para mil.
"""
from __future__ import annotations

import json
import os
import urllib.parse
from dataclasses import dataclass

from fontes.rede import Rede

REPO = "ctresb/leis"
API = f"https://api.github.com/repos/{REPO}"


def _cabecalhos() -> dict[str, str]:
    c = {"User-Agent": "AtlasPen (+https://github.com/luccas-amorim/atlaspen)",
         "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        c["Authorization"] = f"Bearer {token}"
    return c


REDE = Rede(_cabecalhos(), tentativas=2, timeout=60, intervalo=0.2)

_PASTA = {
    "lei": ("leis-ordinarias", "lei"),
    "decreto.lei": ("decretos-lei", "del"),
    "lei.complementar": ("leis-complementares", "lcp"),
}


def caminho_da_urn(urn: str) -> str | None:
    """A URN do diploma no caminho do arquivo dele no ctresb/leis.

        urn:lex:br:federal:lei:1984-07-11;7210           -> federal/leis-ordinarias/1984/lei-7210-1984-07-11.md
        urn:lex:br:federal:decreto.lei:1940-12-07;2848   -> federal/decretos-lei/1940/del-2848-1940-12-07.md
        urn:lex:br:federal:constituicao:1988-10-05;1988  -> constituicao.md
    """
    partes = (urn or "").split(":")
    if len(partes) != 6 or ";" not in partes[5]:
        return None
    especie = partes[4]
    data, numero = partes[5].split(";", 1)
    if especie == "constituicao":
        return "constituicao.md"
    if especie not in _PASTA:
        return None
    pasta, prefixo = _PASTA[especie]
    return f"federal/{pasta}/{data[:4]}/{prefixo}-{numero}-{data}.md"


@dataclass(frozen=True)
class Commit:
    sha: str
    data: str            # ISO, do autor
    mensagem: str        # a primeira linha
    url: str


def ler_commits(dados: list) -> list[Commit]:
    saida = []
    for c in dados or []:
        info = c.get("commit") or {}
        saida.append(Commit(c.get("sha", "")[:12], ((info.get("author") or {}).get("date") or "")[:10],
                            (info.get("message") or "").splitlines()[0][:140] if info.get("message") else "",
                            c.get("html_url", "")))
    return saida


def commits(caminho: str, desde: str, ate_quantos: int = 30) -> list[Commit]:
    """Os commits que tocaram `caminho` desde a data ISO `desde`."""
    q = urllib.parse.urlencode({"path": caminho, "since": f"{desde}T00:00:00Z", "per_page": ate_quantos})
    bruto = REDE.obter(f"{API}/commits?{q}", ausentes=(404, 409))
    return ler_commits(json.loads(bruto)) if bruto else []


# ── A leitura em escala (o Curador) ─────────────────────────────────────────
# O texto vem do raw.githubusercontent.com, que não conta no teto da API, e em
# paralelo: com o intervalo do REDE, 30 mil arquivos levariam mais de hora e
# meia. Medido em 26/10/2026: 80 arquivos em 2,5 s, com 8 de uma vez.
RAW = "https://raw.githubusercontent.com"
REDE_RAW = Rede(_cabecalhos(), tentativas=3, timeout=60)


@dataclass(frozen=True)
class Arquivo:
    caminho: str         # federal/leis-ordinarias/1965/lei-4737-1965-07-15.md
    sha: str             # o blob no git


def commit_atual() -> str:
    """O commit da main agora — a varredura lê tudo dele, e não da main que anda."""
    bruto = REDE.obter(f"{API}/commits/main", ausentes=())
    return json.loads(bruto)["sha"]


def subpastas(caminho: str, commit: str) -> dict[str, str]:
    """{nome: sha da árvore} das pastas dentro de `caminho` — os anos."""
    q = urllib.parse.urlencode({"ref": commit})
    bruto = REDE.obter(f"{API}/contents/{caminho}?{q}", ausentes=(404,))
    if not bruto:
        return {}
    return {x["name"]: x["sha"] for x in json.loads(bruto) if x.get("type") == "dir"}


def arquivos(caminho: str, arvore: str) -> list[Arquivo]:
    """Os arquivos de uma pasta pela API de árvores do git, que não corta em mil
    itens como a de conteúdo — um ano de decretos-lei de 1942 passa disso."""
    bruto = REDE.obter(f"{API}/git/trees/{arvore}", ausentes=())
    dados = json.loads(bruto)
    if dados.get("truncated"):
        raise ValueError(f"a árvore de {caminho} veio truncada")
    return [Arquivo(f"{caminho}/{x['path']}", x["sha"]) for x in dados.get("tree") or []
            if x.get("type") == "blob" and x["path"].endswith(".md")]


def texto(caminho: str, commit: str) -> str:
    bruto = REDE_RAW.obter(f"{RAW}/{REPO}/{commit}/{urllib.parse.quote(caminho)}", ausentes=())
    return bruto.decode("utf-8", errors="replace")
