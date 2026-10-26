# -*- coding: utf-8 -*-
"""A varredura do Curador no ctresb/leis, com estado.

Cada pasta de ano tem um `sha` de árvore no git: igual ao do estado, nada
mudou, e o ano não é baixado de novo. Na varredura única são uns 30 mil
arquivos; no mês seguinte, só os anos que o ctresb reescreveu.

O estado (`data/curadoria.json`) guarda, por espécie e ano, o `sha` da árvore e as
contagens, e, por lei apontada, o que a triagem viu. O que não aponta fica só na
contagem: 30 mil linhas no repositório não diriam nada que a contagem não diga.
"""
from __future__ import annotations

import concurrent.futures as cf
from dataclasses import asdict

from curador import triagem
from fontes import ctresb
from fontes.rede import FalhaDeRede

PARALELO = 8
ANOS_ATE_DESISTIR = 3


def anos_a_ler(pasta: dict[str, str], estado_especie: dict, ano_inicial: int = triagem.ANO_INICIAL
               ) -> dict[str, str]:
    """{ano: sha} das pastas novas ou mudadas desde o estado."""
    return {ano: sha for ano, sha in sorted(pasta.items())
            if ano.isdigit() and int(ano) >= ano_inicial
            and (estado_especie.get(ano) or {}).get("arvore") != sha}


def ler_ano(especie: str, ano: str, arvore: str, commit: str, ler=ctresb.texto, listar=ctresb.arquivos
            ) -> tuple[dict, list[triagem.Triada], list[str]]:
    """As contagens do ano, as leis com pena própria e os arquivos não lidos."""
    caminho = f"{triagem.PASTAS[especie]}/{ano}"
    lista = listar(caminho, arvore)
    triadas, falhas = [], []

    def um(a):
        try:
            return triagem.triar(a.caminho, ler(a.caminho, commit))
        except (FalhaDeRede, ValueError) as e:
            falhas.append(f"{a.caminho}: {e}")
            return None
    with cf.ThreadPoolExecutor(PARALELO) as ex:
        triadas = [t for t in ex.map(um, lista) if t]
    contagem = {"arvore": arvore, "arquivos": len(lista),
                "pena_propria": sum(t.pena_propria for t in triadas),
                "pena_citada": sum(t.pena_citada for t in triadas)}
    if falhas:
        contagem["nao_lidos"] = len(falhas)
        contagem["arvore"] = None          # volta a ser lido no próximo mês
    return contagem, [t for t in triadas if t.pena_propria], falhas


def varrer(estado: dict, conhecidos: dict[str, str], commit: str, especies=tuple(triagem.PASTAS),
           progresso=print) -> tuple[dict, list[str]]:
    """Atualiza `estado` em lugar e devolve (as leis novas apontadas, os avisos)."""
    estado["commit_ctresb"] = commit
    novos, avisos = {}, []
    for especie in especies:
        try:
            pasta = ctresb.subpastas(triagem.PASTAS[especie], commit)
        except (FalhaDeRede, ValueError) as e:
            avisos.append(f"`{triagem.PASTAS[especie]}` não pôde ser listada: {e}")
            continue
        por_ano = estado.setdefault("anos", {}).setdefault(especie, {})
        seguidas = 0
        for ano, arvore in anos_a_ler(pasta, por_ano).items():
            try:
                contagem, apontadas, falhas = ler_ano(especie, ano, arvore, commit)
            except (FalhaDeRede, ValueError) as e:
                avisos.append(f"`{especie}` {ano}: {e}")
                seguidas += 1
                # Na primeira rodada de 26/10/2026, sem token, o teto de 60
                # pedidos por hora da API acabou em 1951, e os 30 anos seguintes
                # deram o mesmo 403 um a um. O ano não lido fica para a próxima
                # rodada, que o encontra com a árvore de antes.
                if seguidas >= ANOS_ATE_DESISTIR:
                    avisos.append(f"`{especie}`: {ANOS_ATE_DESISTIR} anos seguidos sem leitura — o resto fica "
                                  "para a próxima rodada")
                    break
                continue
            seguidas = 0
            por_ano[ano] = contagem
            avisos += falhas[:5]
            for t in apontadas:
                registro = estado.setdefault("apontadas", {}).get(t.chave)
                if t.chave in conhecidos:
                    continue
                if registro is None:
                    novos[t.chave] = t
                estado["apontadas"][t.chave] = {**(registro or {}), **asdict(t)}
            progresso(f"{especie} {ano}: {contagem['arquivos']} arquivos, {contagem['pena_propria']} com pena "
                      f"própria, {len(apontadas)} apontadas")
    return novos, avisos
