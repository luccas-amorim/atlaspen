# -*- coding: utf-8 -*-
"""Monta a proposta da rodada: escolhe o diploma, aplica e escreve o PR (F6b).

`corrigir.py` e `criar.py` sabem propor mudanças de UM diploma; este módulo é o
que falta entre eles e o workflow semanal — decide qual diploma vai na rodada,
aplica as duas coisas na mesma árvore e deixa pronto o corpo do PR com a
evidência de cada mudança. Depois da v1.0.0, também escreve a entrada de
changelog e sobe a versão.

Quatro decisões, todas para que o PR seja revisável por gente:

- **Um diploma por PR.** Revisar pena exige abrir o texto compilado; misturar
  vinte diplomas num PR só produz aprovação no atacado. O escolhido é o de mais
  propostas, e o próximo vai na semana seguinte.
- **Por padrão, só CORRIGE linha existente.** Criar linha é decidir se o
  dispositivo é crime autônomo, causa de aumento ou nada — e a primeira leva
  automática de linhas novas (F6) trouxe 29 registros que não eram tipos penais
  vigentes: contravenções revogadas, infrações administrativas do ECA e, sobre-
  tudo, redações do Código Penal transcritas dentro das leis que o alteraram.
  As guardas contra esses casos existem agora (`parsear._marcar_citacoes`,
  espécie de pena, revogação anotada), mas quem cria linha continua sendo gente:
  `--com-novas` liga a proposta de linha nova, e o workflow só a usa quando
  alguém pedir explicitamente.
- **Nota só para alteração de lei** (decisão de 14/09/2026). O feed publica o
  que uma lei nova cria ou modifica, e não o erro antigo do catálogo que a
  conferência achou. O que separa os dois é a anotação do compilado: redação
  dada, ou dispositivo incluído, por lei deste ano ou do anterior. Com nota, o
  PR fecha uma versão (em `0.0.x` até o lançamento) e sobe `package.json` e o
  lockfile; sem nota, não sobe nada. Entrada sem bump seria pior: anunciaria
  no feed uma versão já publicada.
- **Nada de silencioso.** O bump é conferido depois de escrito (substituição de
  texto já falhou em silêncio aqui) e cada mudança leva no corpo o trecho da lei
  que a motivou.

Uso:
    python scripts/robos/propor/propor.py                 # o que sairia (não escreve)
    python scripts/robos/propor/propor.py --aplicar --saida crawler/proposta

Saídas: 0 = proposta pronta; 1 = nada mecânico nesta rodada; 2 = erro.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import traceback
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
# `scripts/robos` para os pacotes dos robôs e do núcleo; `scripts` para o
# `pena_parser`, que é compartilhado com o construtor do catálogo e por isso
# não mora aqui.
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from proponente import corrigir  # noqa: E402
from proponente import criar  # noqa: E402
from nucleo.dispositivo import SNAPSHOTS  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402
from endereco_publico import SITE  # noqa: E402
from transform_data import _faixa_de_meses, proximo_id  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
MODIFICADORES = RAIZ / "data" / "modificadores.json"
CATALOGO_FONTE = RAIZ / "data" / "crimes.json"
PACKAGE = RAIZ / "package.json"
LOCK = RAIZ / "package-lock.json"
CITATION = RAIZ / "CITATION.cff"
ENTRADAS = RAIZ / "src" / "data" / "changelog" / "entries"


# ── Versão ──────────────────────────────────────────────────────────────────
def versao_atual() -> str:
    return json.loads(PACKAGE.read_text(encoding="utf-8"))["version"]


def proxima_versao(atual: str) -> str:
    """Correção de dado é patch (docs/dados-abertos.md, Estabilidade e versionamento)."""
    maior, menor, patch = (int(x) for x in atual.split("."))
    return f"{maior}.{menor}.{patch + 1}"


def versao_da_rodada() -> str:
    """A versão que o PR fecha SE a rodada tiver nota (ver `aplicar`).

    Até o lançamento o projeto anda em 0.0.x (decisão de 14/09/2026): o patch
    sobe, e o `release.yml` continua sem publicar nada enquanto a versão for 0.x.
    """
    return proxima_versao(versao_atual())


def _substituir_versao(caminho: Path, padrao: str, atual: str, nova: str,
                       vezes: int = 1) -> None:
    """Troca a versão e CONFERE o resultado.

    O bump por substituição de texto já falhou em silêncio neste repositório
    (três entradas anunciaram versões que nunca saíram). Aqui, se a troca não
    pegar, o processo morre — nunca segue com o arquivo intacto.

    Trabalha sobre os bytes porque o repositório é CRLF: reescrever pelo modo
    texto trocaria a quebra de linha do arquivo inteiro e o diff do PR deixaria
    de mostrar uma linha para mostrar cinquenta.
    """
    texto = caminho.read_bytes().decode("utf-8")
    novo, trocas = re.subn(padrao.format(v=re.escape(atual)),
                           lambda m: m.group(0).replace(atual, nova), texto, count=vezes)
    if trocas != vezes or nova not in novo:
        raise SystemExit(f"bump falhou em {caminho.name}: {trocas} substituição(ões)")
    caminho.write_bytes(novo.encode("utf-8"))


def subir_versao(nova: str) -> None:
    atual = versao_atual()
    _substituir_versao(PACKAGE, r'"version":\s*"{v}"', atual, nova)
    # A raiz do lockfile repete a versão duas vezes: o pacote e packages[""].
    if LOCK.exists():
        _substituir_versao(LOCK, r'"version":\s*"{v}"', atual, nova, vezes=2)
    # Até a v1.0.0 o CITATION.cff cita pela data e não tem campo de versão.
    if re.search(r"^version:", CITATION.read_text(encoding="utf-8"), re.M):
        _substituir_versao(CITATION, r'version:\s*"{v}"', atual, nova)
    conferida = json.loads(PACKAGE.read_text(encoding="utf-8"))["version"]
    if conferida != nova:
        raise SystemExit(f"package.json ficou em {conferida}, não em {nova}")


# ── Escolha do diploma ──────────────────────────────────────────────────────
def carregar_fontes() -> list[dict]:
    return json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]


def propostas_da_fonte(fonte_id: str, proximo_id: int,
                       com_novas: bool) -> tuple[list[dict], list[dict], list[dict]]:
    """(correções, linhas novas, achados que ficam para gente)."""
    correcoes, humanos = corrigir.gerar(fonte_id)
    novas = criar.gerar(fonte_id, proximo_id)[0] if com_novas else []
    return correcoes, novas, humanos


def escolher(com_novas: bool, apenas: str | None = None) -> dict | None:
    """O diploma da rodada: o de mais propostas mecânicas.

    Empate desfeito pela ordem de `fontes.json`, que é estável — duas execuções
    na mesma árvore têm de produzir o mesmo PR.
    """
    catalogo = json.loads(CATALOGO_FONTE.read_text(encoding="utf-8"))
    # Conta os ids aposentados: um endereço público nunca é reaproveitado.
    proximo = proximo_id(catalogo)
    fontes = [f for f in carregar_fontes() if not apenas or f["id"] == apenas]
    com_snapshot = [f for f in fontes if (SNAPSHOTS / f["id"]).exists()]
    achados_mod = achados_de_modificadores() if com_snapshot else []
    dia = hoje().isoformat()

    melhor = None
    for f in com_snapshot:
        correcoes, novas, humanos = propostas_da_fonte(f["id"], proximo, com_novas)
        modificadores = modificadores_propostos(f, catalogo, achados_mod, dia)
        total = len(correcoes) + len(novas) + len(modificadores)
        if not total:
            continue
        if melhor is None or total > melhor["total"]:
            melhor = {"fonte": f, "correcoes": correcoes, "novas": novas,
                      "humanos": humanos, "modificadores": modificadores, "total": total}
    # Sentinela é prova de frescor, não dado do catálogo: vai em qualquer PR da
    # rodada, de todas as fontes de uma vez. Sozinha, também justifica um PR.
    sentinelas = sentinelas_propostas(com_snapshot)
    if melhor is None and sentinelas:
        f = next(x for x in com_snapshot if x["id"] == sentinelas[0]["fonte"])
        melhor = {"fonte": f, "correcoes": [], "novas": [], "humanos": [],
                  "modificadores": [], "total": 0}
    if melhor is not None:
        melhor["sentinelas"] = sentinelas
    return melhor


# ── Sentinelas e modificadores de escopo declarado ──────────────────────────
# Duas leituras diretas que ficavam para gente sem precisar (decisão de
# 28/09/2026, depois da rodada da Lei 15.517):
#
# - A SENTINELA de uma fonte é o número da lei mais recente que o compilado
#   anota ("Incluído pela Lei nº 15.517, de 2026"). Quando a página passa a
#   anotar lei mais nova que a sentinela, a prova de frescor envelheceu — e o
#   número novo está escrito na própria página. Só se troca sentinela que já É
#   número de lei ordinária (com ponto de milhar); sentinela de CONTEÚDO — o
#   nomen juris de um tipo, para diploma que ainda não tem emenda — fica.
#   "Vide Lei nº …" não conta: remissão não prova que a página foi atualizada.
# - Um MODIFICADOR só é proposto quando o próprio dispositivo diz sobre o que
#   incide: "na hipótese do § 10", "a pena prevista no § 2º-A", ou "as penas
#   cominadas neste artigo" num artigo que tem uma linha só no catálogo. Fração
#   e direção vêm do texto. O que não declara alcance continua pergunta na
#   issue — definir escopo é juízo, e o auditor que só lista continua certo.
from auditor import auditar as auditoria  # noqa: E402

_SENTINELA_NUMERICA = re.compile(r"^\d{1,3}\.\d{3}$")
_LEI_ORDINARIA = re.compile(r"^Lei\s+n[ºo°]\s*([\d.]+)$", re.I)
_PELA_LEI = re.compile(r"\bpel[ao]\s+Lei\b", re.I)


def _numero(texto: str) -> int:
    return int(re.sub(r"\D", "", texto))


def _anotacoes(d) -> list:
    """A anotação do dispositivo e as dos incisos (o compilado anota inciso a inciso)."""
    saida = [getattr(d, "anotacao", None)]
    for inc in getattr(d, "incisos", None) or []:
        saida.append(inc.get("anotacao") if isinstance(inc, dict) else getattr(inc, "anotacao", None))
    return [a for a in saida if a]


def _norma_de(a) -> tuple[str | None, str, int | None]:
    if isinstance(a, dict):
        return a.get("norma"), a.get("texto") or "", a.get("ano")
    return getattr(a, "norma", None), getattr(a, "texto", "") or "", getattr(a, "ano", None)


def sentinelas_propostas(fontes: list[dict], dispositivos=None) -> list[dict]:
    """Fontes cuja página já anota lei mais nova que a sentinela."""
    dispositivos = dispositivos or auditoria.dispositivos_de
    propostas = []
    for f in fontes:
        atual = f.get("sentinela") or ""
        if not _SENTINELA_NUMERICA.match(atual):
            continue
        melhor = None
        for d in dispositivos(f["id"]).values():
            if getattr(d, "citacao", False):
                continue                  # texto transcrito de OUTRA lei
            for a in _anotacoes(d):
                norma, texto, ano = _norma_de(a)
                if not norma or not _PELA_LEI.search(texto):
                    continue
                m = _LEI_ORDINARIA.match(norma.strip())
                if not m:
                    continue              # lei complementar, decreto-lei, MP
                n = _numero(m.group(1))
                if n < 1000:
                    continue
                if melhor is None or n > melhor[0]:
                    melhor = (n, texto.strip(), ano)
        if melhor and melhor[0] > _numero(atual):
            n, texto, ano = melhor
            propostas.append({"fonte": f["id"], "rotulo": _rotulo(f), "de": atual,
                              "para": f"{n // 1000}.{n % 1000:03d}", "evidencia": texto,
                              "ano": ano})
    return propostas


def aplicar_sentinelas(propostas: list[dict], caminho: Path = FONTES) -> None:
    """Troca só o valor, na entrada certa, sem reescrever o arquivo."""
    texto = caminho.read_bytes().decode("utf-8")
    for p in propostas:
        padrao = re.compile(
            r'("id":\s*"%s"(?:(?!"id":).)*?"sentinela":\s*")%s(")'
            % (re.escape(p["fonte"]), re.escape(p["de"])), re.S)
        texto, n = padrao.subn(lambda m: m.group(1) + p["para"] + m.group(2), texto, count=1)
        if n != 1:
            raise SystemExit(f"sentinela de {p['fonte']} ({p['de']!r}) não encontrada em {caminho.name}")
    caminho.write_bytes(texto.encode("utf-8"))


from nucleo.fracao import fracao_humana as _fracao_humana, fracoes_do_texto  # noqa: E402


_ESCOPO_PARAGRAFO = re.compile(
    r"(?:na\s+hip[óo]tese|no\s+caso|nos\s+casos|penas?\s+(?:previstas?|cominadas?))\s+"
    r"(?:do|no|dos|nos)\s+§\s*(\d+\s*[ºo°]?(?:-[A-Z])?)(?!\s*(?:e|,|ou)\s*§)", re.I)
_ESCOPO_ARTIGO = re.compile(r"\bneste\s+artigo\b", re.I)


def _marcador_canonico(marcador: str) -> str:
    """"§ 11º" → "§11"; "§ 2º" → "§2º"; "§ 2º-A" → "§2º-A"; "parágrafo único" fica."""
    if "único" in marcador or "unico" in marcador:
        return "parágrafo único"
    m = re.match(r"§\s*(\d+)\s*[ºo°]?(-[A-Z])?", marcador)
    if not m:
        return marcador
    num, sufixo = int(m.group(1)), m.group(2) or ""
    return f"§{num}{'º' if num < 10 else ''}{sufixo}"


def _slug(texto: str) -> str:
    t = texto.lower()
    t = (t.replace("§", "p").replace("ú", "u").replace("á", "a").replace("ã", "a")
          .replace("é", "e").replace("ç", "c").replace("º", "").replace("°", ""))
    return re.sub(r"[^a-z0-9]+", "", t)


def _sem_ordinal(texto: str) -> str:
    """"Art. 155, §12, VI c/c §10" e "Art. 155, § 12º" comparam sem espaço nem ordinal."""
    return re.sub(r"[\sº°]", "", texto).lower()


def achados_de_modificadores() -> list[dict]:
    """Os MODIFICADOR-AUSENTE da rodada, já sem os julgados em excecoes-auditoria.json."""
    fontes = carregar_fontes()
    indice = {r: f["id"] for f in fontes for r in f["rotulos"]}
    excecoes = auditoria.carregar_excecoes()
    return [a for a in auditoria.auditar_modificadores(indice)
            if not auditoria.dispensado(excecoes, a)]


def modificadores_propostos(fonte: dict, catalogo: list[dict], achados: list[dict],
                            dia: str, dispositivos=None) -> list[dict]:
    """Modificador para o achado cujo texto declara fração, direção e alcance."""
    dispositivos = dispositivos or auditoria.dispositivos_de
    rotulos, lei = set(fonte["rotulos"]), _rotulo(fonte)
    diploma = re.split(r"\s*\(", lei, maxsplit=1)[0].strip()
    registros = [c for c in catalogo if c["lei"] in rotulos]
    disp = None
    propostas = []
    for a in achados:
        if a.get("fonte") != fonte["id"] or a.get("tipo") != "MODIFICADOR-AUSENTE":
            continue
        if disp is None:
            disp = dispositivos(fonte["id"])
        d = disp.get(a["dispositivo"])
        if d is None:
            continue
        texto = re.sub(r"\s+", " ", d.texto or "").strip()
        fracao = fracoes_do_texto(texto)
        if not fracao:
            continue
        sobe = bool(re.search(r"aument|dobro|triplo", texto, re.I))
        desce = bool(re.search(r"reduz|diminu", texto, re.I))
        if sobe == desce:
            continue                      # nem uma coisa nem outra, ou as duas
        art = f"Art. {d.artigo}" + (f"-{d.sufixo}" if d.sufixo else "")
        m = _ESCOPO_PARAGRAFO.search(texto)
        if m:
            par = re.sub(r"\s+", "", m.group(1)).replace("o", "º").replace("°", "º")
            alvo, lido = f"{art}, {_marcador_canonico('§ ' + par)}", m.group(0)
        elif _ESCOPO_ARTIGO.search(texto):
            proprios = [c for c in registros
                        if re.match(re.escape(art) + r"(?=$|,| )", c["artigo"])]
            if len(proprios) != 1:
                continue                  # mais de uma moldura: qual delas? juízo
            alvo, lido = proprios[0]["artigo"], "neste artigo"
        else:
            continue
        if not any(c["artigo"].startswith(alvo) for c in registros):
            continue                      # o alvo não existe no catálogo
        natureza = "aumento" if sobe else "diminuicao"
        caput = disp.get(f"{art}|caput")
        epigrafe = (getattr(caput, "epigrafe", None) or art).strip()
        marcador = _marcador_canonico(d.marcador)
        chave_propria = _sem_ordinal(f"{art}, {marcador}")
        embutida = any(_sem_ordinal(c["artigo"]).startswith(chave_propria) for c in registros)
        fmin, fmax = fracao
        obs = (f"{texto.rstrip('.:;')}. Proposto pelo conferidor em {dia}: fração e alcance "
               f"lidos do próprio dispositivo (\"{lido}\"); o texto compilado é a evidência. "
               "Confira o alcance antes de aprovar.")
        if d.anotacao and getattr(d.anotacao, "texto", None):
            obs += f" {d.anotacao.texto.strip()}"
        mod = {
            "id": f"{natureza}-{fonte['id']}-{_slug(art)}-{_slug(marcador)}",
            "nome": f"{epigrafe} — {marcador} ({'+' if sobe else '−'}{_fracao_humana(fmin, fmax)})",
            "dispositivo": f"{diploma}, {art[0].lower() + art[1:]}, {marcador}",
            "natureza": natureza, "fase": 3, "sobre": "pena_provisoria",
            "fracao_min": fmin, "fracao_max": fmax, "piso_minimo": False,
            "escopo": {"tipo": "tipos_por_artigo", "lei": lei, "artigos": [alvo]},
            "obs": obs,
        }
        # No CP o front suprime o aumento cominado no mesmo artigo do tipo, porque
        # as majorantes do CP viraram linhas com moldura calculada. Onde NÃO há
        # linha derivada, o aumento ficaria invisível — daí a declaração.
        if fonte["id"] == "cp" and not embutida:
            mod["ignora_embutida"] = True
        propostas.append({"modificador": mod, "achado": a, "lido": lido,
                          "embutida": embutida, "texto": texto})
    return propostas


def aplicar_modificadores(propostas: list[dict], caminho: Path = MODIFICADORES) -> None:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    ids = {m["id"] for m in dados["modificadores"]}
    for p in propostas:
        if p["modificador"]["id"] not in ids:
            dados["modificadores"].append(p["modificador"])
            ids.add(p["modificador"]["id"])
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")


# ── Auditoria: propostas que dependem de juízo ──────────────────────────────
# Regra da casa: o que a máquina lê com segurança ela corrige; o que depende de
# juízo jurídico ela PROPÕE, em PR, com o fundamento ao lado. Corrigir um PR é
# mais barato do que montar um do zero — e o diff mostra exatamente o que muda.
CAMPO_DO_ACHADO = {"hediondez": "hediondo", "acao_penal": "acao"}


def propostas_de_auditoria(achados: list[dict]) -> list[dict]:
    """Achados da auditoria que viram mudança concreta de campo."""
    catalogo = {c["id"]: c for c in json.loads(CATALOGO_FONTE.read_text(encoding="utf-8"))}
    propostas = []
    for a in achados:
        campo = CAMPO_DO_ACHADO.get(a.get("campo"))
        if not campo or "id" not in a or not a.get("para"):
            continue
        linha = catalogo.get(a["id"])
        if linha is None or linha.get(campo) == a["para"]:
            continue
        propostas.append({
            "id": a["id"], "campo": campo,
            "de": linha.get(campo), "para": a["para"],
            "fundamento": a.get("fundamento") or a["detalhe"],
            "lei": linha["lei"], "artigo": linha["artigo"], "crime": linha["crime"],
        })
    return propostas


def aplicar_auditoria(propostas: list[dict]) -> None:
    dados = json.loads(CATALOGO_FONTE.read_text(encoding="utf-8"))
    por_id = {p["id"]: p for p in propostas}
    for c in dados:
        p = por_id.get(c["id"])
        if p:
            c[p["campo"]] = p["para"]
    texto = json.dumps(dados, ensure_ascii=False, indent=2) + "\n"
    CATALOGO_FONTE.write_bytes(texto.replace("\n", "\r\n").encode("utf-8"))


def aplicar_fontes_propostas() -> list[dict]:
    """Acrescenta a `data/fontes.json` os diplomas que o watcher propôs.

    Entram com `id` provisório (`NOVA-15410`) e `obs` explicando o que conferir:
    a URL do compilado segue padrão, mas o Planalto foge dele em lei
    complementar e em lei antiga. Corrigir isso no PR é mais barato do que
    escrever a entrada do zero — que é o ponto.
    """
    proposto = RAIZ / "crawler" / "relatorios" / "fontes-propostas.json"
    if not proposto.exists():
        return []
    novas = json.loads(proposto.read_text(encoding="utf-8"))
    if not novas:
        return []
    texto = FONTES.read_bytes().decode("utf-8")
    existentes = {f["id"] for f in json.loads(texto)["fontes"]}
    entram = [n for n in novas if n["id"] not in existentes]
    if not entram:
        return []
    # A quebra de linha é a do arquivo: CRLF na cópia de trabalho do Windows, LF
    # na CI. Até 25/10/2026 só o CRLF casava, e na CI o `rindex` levantaria —
    # o que nunca se viu porque a rodada de auditoria morria antes, no import.
    eol = "\r\n" if "\r\n" in texto else "\n"
    i = texto.rindex("}" + eol + "  ]")
    bloco = "," + eol + ("," + eol).join(
        "    " + json.dumps(n, ensure_ascii=False) for n in entram)
    FONTES.write_bytes((texto[:i + 1] + bloco + texto[i + 1:]).encode("utf-8"))
    return entram


def corpo_auditoria(propostas: list[dict], versao: str | None, relatorio: str,
                    fontes_novas: list[dict] | None = None) -> str:
    """Corpo do PR de auditoria: cada mudança com o fundamento que a sustenta."""
    por_campo: dict[str, list[dict]] = {}
    for p in propostas:
        por_campo.setdefault(p["campo"], []).append(p)

    L = [
        "## Auditoria dos campos de classificação", "",
        f"{len(propostas)} mudança(s) propostas em campos que **decidem atributos** e que "
        "a conferência de penas não alcançava."
        + " Não escreve nota nem sobe versão: classificação corrigida contra o rol é "
        "correção de dado. Se a mudança vier de lei nova, a entrada se escreve à mão "
        "(`src/data/changelog/create-changelog-entry.md`).", "",
        "> ⚠️ **Isto pede o seu juízo, não só uma conferida.** A máquina comparou o "
        "catálogo com o rol legal e com as fórmulas de ação penal do próprio diploma; "
        "onde a lei condiciona a classificação a circunstância do caso, ela não propôs "
        "nada. Cada linha abaixo cita o fundamento — confira antes de aprovar.", "",
    ]
    titulos = {"hediondo": "Hediondez", "acao": "Ação penal"}
    for campo, itens in sorted(por_campo.items()):
        L += [f"### {titulos.get(campo, campo)} — {len(itens)}", ""]
        for p in itens:
            L += [
                f"- **id {p['id']}** `{p['lei']} {p['artigo']}` — {p['de']} → **{p['para']}**",
                f"  - *{p['crime'][:100]}*",
                f"  - {p['fundamento']}",
                f"  - <{SITE}/tipos/{p['id']}>",
            ]
        L.append("")
    if fontes_novas:
        L += [f"### Diplomas novos ({len(fontes_novas)})", "",
              "O watcher do DOU encontrou lei que **parece criar tipo penal** e que nenhum "
              "diploma monitorado cobre. A entrada já vai aplicada em `data/fontes.json`, "
              "com `id` provisório — **confira a URL do compilado e troque o `id` por um "
              "descritivo** antes de aprovar. A partir do merge, o diploma passa a ser "
              "conferido toda semana.", ""]
        for n in fontes_novas:
            L += [f"- **{n['id']}** — {', '.join(n['rotulos'])}", f"  - <{n['url']}>",
                  f"  - {n['obs']}"]
        L.append("")
    L += ["---", "", "Relatório completo da auditoria, com o que NÃO virou proposta:", "",
          "<details><summary>abrir</summary>", "", relatorio, "", "</details>", ""]
    return "\n".join(L) + "\n"


# ── Textos ──────────────────────────────────────────────────────────────────
def _rotulo(fonte: dict) -> str:
    """Fonte de REFERÊNCIA (o CPP, sem tipo próprio) não tem rótulo: vale o id."""
    return fonte["rotulos"][0] if fonte.get("rotulos") else fonte["id"]


def corpo_pr(escolha: dict, versao: str | None, legais: list[dict] | None = None,
             fora: list[dict] | None = None) -> str:
    """Corpo do PR: uma seção por mudança, cada uma com o trecho da lei."""
    f = escolha["fonte"]
    correcoes, novas, humanos = escolha["correcoes"], escolha["novas"], escolha["humanos"]
    L = [
        f"## Diploma: **{', '.join(f['rotulos'])}**", "",
        f"Rodada automática do conferidor. Texto oficial conferido: <{f['url']}>", "",
        f"- **{len(correcoes)}** correção(ões) de moldura ou espécie de pena em linha existente;",
        f"- **{len(novas)}** linha(s) nova(s) proposta(s);",
        f"- **{len(escolha.get('modificadores') or [])}** modificador(es) de escopo declarado;",
        f"- **{len(escolha.get('sentinelas') or [])}** sentinela(s) apontando para lei mais recente;",
        (f"- fecha a versão **v{versao}**, com {_plural(len(legais or []), 'nota', 'notas')} "
         "de atualização." if versao
         else "- não escreve nota nem sobe versão: nenhuma mudança vem de lei recente."), "",
        "> Cada mudança é uma **proposta** conferida contra o texto compilado, não uma "
        "conclusão jurídica. O merge continua exigindo revisão humana.", "",
    ]

    if legais or fora:
        L += ["## Notas de atualização", "",
              "Vai para o feed só a alteração de lei: redação dada, ou dispositivo "
              "incluído, por lei deste ano ou do anterior. **Confira a natureza** de "
              "cada uma antes de aprovar: a proposta é mecânica (dispositivo novo = "
              "incriminadora), e a régua do projeto é a doutrinária — se a conduta já "
              "era punível, a natureza é in pejus.", ""]
        for m in legais or []:
            a = m["anotacao"]
            L.append(f"- id {m['id']} `{m['depois']['artigo']}`: *{ROTULO_NATUREZA[m['natureza']]}*, "
                     f"{a['norma']}, de {a['ano']}")
        for x in fora or []:
            L.append(f"- id {x['id']} `{x['artigo']}`: fora do feed, {x['motivo']}")
        L.append("")

    if correcoes:
        L += ["## Correções de linha existente", ""]
        for p in correcoes:
            a, d = p["antes"], p["depois"]
            L += [
                f"### `{a['artigo']}` — id {a['id']}", f"*{a['crime'][:110]}*", "",
                f"- **Na lei:** {p['evidencia']}",
                f"- **Antes:** {a['pena_min']}–{a['pena_max']} meses, {a['tipo_pena']}",
                f"- **Depois:** {d['pena_min']}–{d['pena_max']} meses, {d['tipo_pena']}",
                f"- **obs:** `{d['obs'][:150]}`",
                f"- Conferir: <{SITE}/tipos/{a['id']}>", "",
            ]

    if novas:
        L += [
            "## Linhas novas", "",
            "Do texto saem seis campos; `acao`, `violencia` e `grave_ameaca` são "
            "herdados do caput do mesmo artigo, e `tentativa`/`hediondo` seguem a "
            "regra do crime culposo. **É aí que a revisão deve olhar primeiro.**", "",
        ]
        for p in novas:
            linha, achado = p["linha"], p["achado"]
            herdado = ", ".join(p["herdado"]) or "nenhum"
            L += [
                f"### `{linha['artigo']}` — id {linha['id']} (novo)",
                f"*{linha['crime'][:110]}*", "",
                f"- **Na lei:** {achado['detalhe'][:220]}",
                f"- **Pena proposta:** {linha['pena_min']}–{linha['pena_max']} meses, "
                f"{linha['tipo_pena']} ({linha['elemento'].lower()})",
                f"- **Herdado do caput** (id {p['caput_id']}): {herdado}",
                f"- **Origem do achado:** {achado['tipo']}", "",
            ]

    if humanos:
        L += [
            f"## Fora do automático ({len(humanos)}) — seguem na issue", "",
            "Dispositivo revogado, pena só de multa, leitura incerta ou mais de uma "
            "linha do catálogo para o mesmo dispositivo: decisão de modelagem, não "
            "leitura de texto.", "",
        ]
        for a in humanos[:25]:
            L += [f"- `{a.get('chave', '?')}` — **{a['tipo']}**: {a['detalhe'][:110]}"]
        L += [""]

    modificadores = escolha.get("modificadores") or []
    if modificadores:
        L += [
            "## Modificadores de escopo declarado", "",
            "Propostos só quando o próprio dispositivo diz sobre o que incide (\"na "
            "hipótese do § 10\", \"a pena prevista no § 2º-A\", \"neste artigo\" em "
            "artigo de linha única). Fração e direção vêm do texto. **Não geram nota**: a "
            "nota da lei sai com as linhas; se a causa vier de lei recente e não houver "
            "linha, a entrada se escreve à mão. Confira o alcance: é a única leitura que "
            "a máquina faz por analogia de redação.", "",
        ]
        for p in modificadores:
            m = p["modificador"]
            L += [
                f"### `{m['dispositivo']}` — `{m['id']}` (novo)",
                f"*{m['nome']}*", "",
                f"- **Na lei:** {p['texto'][:300]}",
                f"- **Fração:** {_fracao_humana(m['fracao_min'], m['fracao_max'])} "
                f"({m['natureza']}) · **Alcance lido:** \"{p['lido']}\" → "
                f"`{'`, `'.join(m['escopo']['artigos'])}`",
                ("- **Linha derivada no catálogo:** sim — o front não oferece o aumento de novo"
                 if p["embutida"] else
                 "- **Linha derivada no catálogo:** não"
                 + (" — `ignora_embutida` para que o front o ofereça" if m.get("ignora_embutida") else "")),
                "",
            ]

    sentinelas = escolha.get("sentinelas") or []
    if sentinelas:
        L += [
            "## Sentinelas", "",
            "A sentinela é a string que prova que a página compilada está fresca. O "
            "compilado destas fontes já anota lei mais nova que a sentinela atual; o "
            "número novo é o da própria anotação.", "",
        ]
        for s in sentinelas:
            L.append(f"- `{s['fonte']}` ({s['rotulo']}): {s['de']} → **{s['para']}** — "
                     f"\"{s['evidencia']}\"")
        L.append("")

    L += [
        "---", "",
        "Gerado por `scripts/robos/propor/propor.py` a partir do texto compilado baixado "
        "nesta execução. Reproduzível localmente:", "",
        "```", f"python scripts/robos/nucleo/baixar.py --fonte {f['id']}",
        f"python scripts/robos/propor/propor.py --fonte {f['id']}", "```", "",
    ]
    return "\n".join(L) + "\n"


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _artigo_em_prosa(artigo: str) -> str:
    """"Art. 50, I" -> "art. 50, I" — sem derrubar o algarismo romano."""
    return re.sub(r"^Art\.", "art.", artigo.strip())


def _frase_correcoes(correcoes: list[dict]) -> str:
    """Até três correções descritas em prosa, para o corpo da entrada.

    Em anos e meses, como a lei fala e como o site mostra: o feed é lido por
    gente, e "12 a 60 meses" obriga quem lê a fazer a conta.
    """
    exemplos = []
    for p in correcoes[:3]:
        a, d = p["antes"], p["depois"]
        exemplos.append(
            f"o {_artigo_em_prosa(a['artigo'])} constava com "
            f"{_faixa_de_meses(a['pena_min'], a['pena_max'])} de "
            f"{a['tipo_pena'].lower()} e passa a "
            f"{_faixa_de_meses(d['pena_min'], d['pena_max'])} de "
            f"{d['tipo_pena'].lower()}")
    return "; ".join(exemplos)


# ── Notas de atualização ────────────────────────────────────────────────────
# O feed publica só alteração de LEI que cria, modifica ou extingue tipo penal
# (AGENTS.md). Uma moldura divergente pode ser lei nova ou dado que estava
# errado, e o que separa os dois é a anotação do compilado: redação dada, ou
# dispositivo incluído, por lei deste ano ou do anterior é alteração
# legislativa. A divergência sob redação antiga é correção de dado e fica fora
# do feed; o corpo do PR diz o porquê de cada uma.
ANOS_DE_LEI_RECENTE = 1
# A direção da mudança, em prosa. NÃO é mais o campo `tipo` da entrada — o
# contrato do changelog foi simplificado em 24/09/2026 e a entrada declara só o
# `alcance`. A direção continua servindo para DOIS fins aqui: agrupar as
# correções por sentido (uma entrada por lei e por direção) e escrever o título
# em português ("pena agravada", "pena abrandada"), que é onde o leitor a lê.
ROTULO_NATUREZA = {
    "incriminadora": "novatio legis incriminadora",
    "pejus": "novatio legis in pejus",
    "mellius": "novatio legis in mellius",
    "abolitio": "abolitio criminis",
}
_GRAVIDADE_ESPECIE = {"Prisão simples": 0, "Detenção": 1, "Reclusão": 2}


def _lei_recente(anot: dict | None, ano: int) -> bool:
    return bool(anot and anot.get("norma") and anot.get("ano")
                and anot["ano"] >= ano - ANOS_DE_LEI_RECENTE)


def natureza_da_correcao(p: dict) -> str | None:
    """in pejus se a pena só sobe; in mellius se só desce; None se sobe e desce."""
    a, d = p["antes"], p["depois"]
    sobe = d["pena_min"] > a["pena_min"] or d["pena_max"] > a["pena_max"]
    desce = d["pena_min"] < a["pena_min"] or d["pena_max"] < a["pena_max"]
    ga = _GRAVIDADE_ESPECIE.get(a.get("tipo_pena"))
    gd = _GRAVIDADE_ESPECIE.get(d.get("tipo_pena"))
    if ga is not None and gd is not None:
        sobe, desce = sobe or gd > ga, desce or gd < ga
    if sobe and not desce:
        return "pejus"
    if desce and not sobe:
        return "mellius"
    return None


def mudancas_da_lei(escolha: dict, ano: int) -> tuple[list[dict], list[dict]]:
    """(o que vai para as notas, o que fica fora delas e por quê)."""
    legais, fora = [], []
    for p in escolha["correcoes"]:
        anot, artigo = p.get("anotacao"), p["antes"]["artigo"]
        natureza = natureza_da_correcao(p)
        if not _lei_recente(anot, ano):
            fora.append({"id": p["id"], "artigo": artigo,
                         "motivo": "correção de dado; a redação vigente não é de lei recente"})
        elif natureza is None:
            fora.append({"id": p["id"], "artigo": artigo,
                         "motivo": "a pena sobe num limite e desce no outro; a natureza fica para a revisão"})
        else:
            legais.append({"id": p["id"], "natureza": natureza, "anotacao": anot,
                           "antes": p["antes"], "depois": p["depois"]})
    for n in escolha["novas"]:
        anot, linha = n["achado"].get("anotacao"), n["linha"]
        if _lei_recente(anot, ano) and anot.get("acao") == "incluido":
            legais.append({"id": linha["id"], "natureza": "incriminadora", "anotacao": anot,
                           "antes": None, "depois": linha})
        else:
            fora.append({"id": linha["id"], "artigo": linha["artigo"],
                         "motivo": "linha que faltava no catálogo; o dispositivo não foi incluído por lei recente"})
    return legais, fora


def _pela(norma: str) -> str:
    return "pelo" if norma.lower().startswith("decreto") else "pela"


def _faixa(linha: dict) -> str:
    return f"{_faixa_de_meses(linha['pena_min'], linha['pena_max'])} de {linha['tipo_pena'].lower()}"


def _links_ts(links: list[dict]) -> str:
    """O link externo sai como literal; o interno, por `urlPublica`.

    Desde 23/09/2026 o endereço do site é uma constante só, e nota publicada com
    URL escrita à mão faria de cada mudança de endereço uma reescrita de texto
    publicado. O robô escreve como a mão escreve.
    """
    linhas = []
    for l in links:
        rotulo = json.dumps(l["label"], ensure_ascii=False)
        if "interno" in l:
            alvo = f"urlPublica({json.dumps(l['interno'], ensure_ascii=False)})"
        else:
            alvo = json.dumps(l["href"], ensure_ascii=False)
        linhas.append(f"    {{label: {rotulo}, href: {alvo}}},")
    return "\n".join(linhas)


def entradas_changelog(escolha: dict, legais: list[dict], versao: str,
                       dia: str) -> list[tuple[Path, str]]:
    """Uma entrada por lei e por natureza. Texto puro (contrato do ChangelogEntry)."""
    rotulo = _rotulo(escolha["fonte"])
    grupos: dict[tuple[str, int, str], list[dict]] = {}
    for m in legais:
        a = m["anotacao"]
        grupos.setdefault((a["norma"], a["ano"], m["natureza"]), []).append(m)

    saida: list[tuple[Path, str]] = []
    for (norma, ano, natureza), itens in sorted(grupos.items()):
        base = f"{dia}-lei-{re.sub(r'[^0-9]', '', norma)}-{natureza}"
        ident, n = base, 2
        destino = ENTRADAS / dia[:4] / f"{ident}.ts"
        while destino.exists() or any(d == destino for d, _ in saida):
            ident = f"{base}-{n}"
            destino = ENTRADAS / dia[:4] / f"{ident}.ts"
            n += 1

        lei, qtd = f"{norma}, de {ano}", len(itens)
        if natureza == "incriminadora":
            titulo = f"{lei}: {_plural(qtd, 'tipo penal incluído', 'tipos penais incluídos')} ({rotulo})"
            acao = "incluídos" if qtd > 1 else "incluído"
            corpo = [f"{_artigo_em_prosa(m['depois']['artigo'])}: {m['depois']['crime']}, "
                     f"{_faixa(m['depois'])}." for m in itens[:8]]
        else:
            verbo = "agravada" if natureza == "pejus" else "abrandada"
            titulo = f"{lei}: {_plural(qtd, 'pena ' + verbo, 'penas ' + verbo + 's')} ({rotulo})"
            acao = "com redação dada"
            corpo = [f"{_artigo_em_prosa(m['antes']['artigo'])}: de {_faixa(m['antes'])} "
                     f"para {_faixa(m['depois'])}." for m in itens[:8]]
        if qtd > 8:
            corpo.append(f"E mais {qtd - 8} dispositivos, na mesma lei.")
        corpo.append(
            "A conferência é semanal e determinística: baixa o texto compilado, lê as "
            "molduras e compara com o publicado. A lei que deu a redação vem da anotação "
            "do próprio compilado.")
        resumo = (f"{rotulo}: {_plural(qtd, 'dispositivo', 'dispositivos')} {acao} "
                  f"{_pela(norma)} {lei}, segundo o texto compilado do Planalto.")
        links = []
        if itens[0]["anotacao"].get("url"):
            links.append({"label": f"{lei}, no Planalto", "href": itens[0]["anotacao"]["url"]})
        # O link interno sai por `urlPublica`, e não como URL literal: desde
        # 23/09/2026 o endereço do site é uma constante só, e nota publicada com
        # URL escrita à mão faria de cada mudança de endereço uma reescrita.
        links += [{"label": _artigo_em_prosa(m["depois"]["artigo"]),
                   "interno": f"/tipos/{m['id']}"} for m in itens[:5]]

        ts = f"""import type {{ChangelogEntry}} from '../../types';
import {{urlPublica}} from '../../../../site/config.ts';

const entrada: ChangelogEntry = {{
  id: '{ident}',
  date: '{dia}',
  title: {json.dumps(titulo, ensure_ascii=False)},
  summary:
    {json.dumps(resumo, ensure_ascii=False)},
  body: [
{chr(10).join('    ' + json.dumps(p, ensure_ascii=False) + ',' for p in corpo)}
  ],
  alcance: ['tipo'],
  version: 'v{versao}',
  links: [
{_links_ts(links)}
  ],
}};

export default entrada;
"""
        saida.append((destino, ts))
    return saida


# ── Execução ────────────────────────────────────────────────────────────────
def _relativo(destino: Path) -> str:
    return str(destino if RAIZ not in destino.parents
               else destino.relative_to(RAIZ)).replace("\\", "/")


def aplicar(escolha: dict, versao: str | None, dia: str, saida: Path) -> dict:
    """Aplica a rodada. Nota, e versão, só quando alguma mudança vem de lei recente."""
    if escolha["correcoes"]:
        corrigir.aplicar(escolha["correcoes"])
    if escolha["novas"]:
        criar.aplicar(escolha["novas"])
    if escolha.get("modificadores"):
        aplicar_modificadores(escolha["modificadores"])
    if escolha.get("sentinelas"):
        aplicar_sentinelas(escolha["sentinelas"])

    legais, fora = mudancas_da_lei(escolha, int(dia[:4]))
    destinos: list[Path] = []
    if versao and legais:
        for destino, ts in entradas_changelog(escolha, legais, versao, dia):
            destino.parent.mkdir(parents=True, exist_ok=True)
            # CRLF como o resto do repositório (as demais entradas são CRLF).
            destino.write_bytes(ts.replace("\n", "\r\n").encode("utf-8"))
            destinos.append(destino)
        subir_versao(versao)
    fechada = versao if destinos else None

    fonte = escolha["fonte"]
    meta = {
        "fonte": fonte["id"],
        "rotulo": _rotulo(fonte),
        "correcoes": len(escolha["correcoes"]),
        "novas": len(escolha["novas"]),
        "modificadores": len(escolha.get("modificadores") or []),
        "sentinelas": len(escolha.get("sentinelas") or []),
        "humanos": len(escolha["humanos"]),
        # O workflow lê as chaves; vazias, e não ausentes, quando não há nota.
        "versao": fechada or "",
        "ramo": f"conferidor/{fonte['id']}-{dia}",
        "titulo": (f"fix(catalogo): {escolha['total']} ajuste(s) em "
                   f"{_rotulo(fonte)} conferidos com o texto compilado" if escolha["total"]
                   else f"chore(fontes): {len(escolha.get('sentinelas') or [])} sentinela(s) "
                        "apontam para a lei mais recente do compilado"),
        "entrada": _relativo(destinos[0]) if destinos else "",
        "entradas": [_relativo(d) for d in destinos],
    }
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "corpo.md").write_text(corpo_pr(escolha, fechada, legais, fora),
                                    encoding="utf-8", newline="\n")
    (saida / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    return meta


def _rodada_de_auditoria(args) -> int:
    """PR das mudanças de classificação.

    Só corre quando não há correção de PENA pendente: um PR por rodada, e a pena
    tem prioridade — é o que a máquina lê com segurança. A classificação vem
    depois, e vem como proposta.
    """
    # O módulo é o `auditoria` importado no topo. Até 25/10/2026 havia aqui um
    # `import auditar` dos tempos em que os robôs dividiam uma pasta só: desde
    # 14/08 ele não resolvia, e a rodada de auditoria morria com 1 — o mesmo
    # código de "nada mecânico" —, sem PR e sem aviso.
    achados = auditoria.rodar()
    propostas = propostas_de_auditoria(achados)
    print(f"auditoria: {len(achados)} achado(s), {len(propostas)} viram proposta")
    for p in propostas[:40]:
        print(f"  id {p['id']:5d} {p['campo']:9s} {p['de']} -> {p['para']}  "
              f"{p['lei']} {p['artigo']}")
    if not propostas:
        return 1

    # Classificação corrigida contra o rol é correção de dado: sem nota e sem
    # versão. Se a mudança vier de lei nova, a entrada se escreve à mão.
    if not args.aplicar:
        print("(simulacao - nada foi escrito; a auditoria não escreve nota nem sobe versão)")
        return 0

    aplicar_auditoria(propostas)
    fontes_novas = aplicar_fontes_propostas()
    dia = hoje().isoformat()
    versao = None

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "corpo.md").write_text(
        corpo_auditoria(propostas, versao, auditoria.montar_relatorio(achados),
                        fontes_novas),
        encoding="utf-8", newline="\n")
    meta = {
        "fonte": "auditoria", "rotulo": "classificação",
        "correcoes": len(propostas), "novas": 0,
        "humanos": len(achados) - len(propostas), "versao": versao or "",
        "ramo": f"conferidor/auditoria-{dia}",
        "titulo": f"fix(catalogo): {len(propostas)} ajuste(s) de hediondez e ação penal",
        "entrada": "", "entradas": [],
    }
    (saida / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    print(f"aplicado; ramo {meta['ramo']}, " + (f"versão v{versao}" if versao else "sem versão"))
    return 0


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Monta a proposta da rodada do conferidor.")
    p.add_argument("--fonte", help="força o diploma (padrão: o de mais propostas)")
    p.add_argument("--com-novas", action="store_true",
                   help="também propõe linhas NOVAS (exige revisão de modelagem)")
    p.add_argument("--aplicar", action="store_true",
                   help="escreve no catálogo, no changelog e na versão")
    p.add_argument("--saida", default=str(RAIZ / "crawler" / "proposta"))
    p.add_argument("--auditoria", action="store_true",
                   help="propõe as mudanças de hediondez e ação penal (exigem juízo)")
    args = p.parse_args()

    if args.auditoria:
        return _rodada_de_auditoria(args)

    escolha = escolher(com_novas=args.com_novas, apenas=args.fonte)
    if escolha is None:
        print("nada mecânico nesta rodada — os achados restantes exigem decisão humana")
        return 1

    f = escolha["fonte"]
    print(f"{f['id']}: {len(escolha['correcoes'])} correção(ões), "
          f"{len(escolha['novas'])} linha(s) nova(s), "
          f"{len(escolha.get('modificadores') or [])} modificador(es), "
          f"{len(escolha.get('sentinelas') or [])} sentinela(s), "
          f"{len(escolha['humanos'])} para decisão humana")
    for x in escolha["correcoes"]:
        a, d = x["antes"], x["depois"]
        print(f"  corrige id {x['id']:5d} {a['artigo']:24s} {a['pena_min']}–{a['pena_max']} "
              f"→ {d['pena_min']}–{d['pena_max']} {d['tipo_pena']}")
    for x in escolha["novas"]:
        linha = x["linha"]
        print(f"  cria    id {linha['id']:5d} {linha['artigo']:24s} "
              f"{linha['pena_min']}–{linha['pena_max']} {linha['tipo_pena']}")
    for x in escolha.get("modificadores") or []:
        m = x["modificador"]
        print(f"  modif.  {m['dispositivo']:30s} {m['natureza']:10s} "
              f"{_fracao_humana(m['fracao_min'], m['fracao_max']):10s} → {m['escopo']['artigos']}")
    for s in escolha.get("sentinelas") or []:
        print(f"  sentin. {s['fonte']:20s} {s['de']} → {s['para']}")

    versao = versao_da_rodada()
    if not args.aplicar:
        legais, _ = mudancas_da_lei(escolha, hoje().year)
        fecho = (f"fecharia a v{versao} com {_plural(len(legais), 'nota', 'notas')}" if legais
                 else "sem nota nem versão: nada vem de lei recente")
        print(f"(simulação — nada foi escrito; {fecho})")
        return 0

    meta = aplicar(escolha, versao, hoje().isoformat(), Path(args.saida))
    print(f"aplicado; ramo {meta['ramo']}, "
          + (f"versão v{meta['versao']}, " if meta["versao"] else "sem versão, ")
          + f"corpo em {args.saida}/corpo.md")
    return 0


if __name__ == "__main__":
    # Exceção não tratada sai com 1, que aqui quer dizer "nada mecânico": o
    # workflow não distinguia a quebra do silêncio. Quebra sai com 2, que o
    # job trata como falha.
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
