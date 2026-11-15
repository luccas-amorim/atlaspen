# -*- coding: utf-8 -*-
"""Audita os campos que o conferidor de penas não alcança.

O conferidor responde "a pena publicada é a que a lei comina?". Sobram quatro
campos que decidem atributos e que ninguém vigiava:

- **hediondez** — rol fechado (Lei 8.072, art. 1º); a auditoria é comparação
  contra a tabela curada em `data/hediondos.json`, mais um alarme quando o texto
  da lei muda;
- **ação penal** — a regra é pública incondicionada (art. 100 do CP), e a
  exceção está escrita no próprio diploma, em fórmulas reconhecíveis
  ("somente se procede mediante representação");
- **causas de aumento e diminuição** — o dispositivo que só majora pena não é
  tipo do catálogo, é modificador; aqui se lista o que a lei tem e
  `data/modificadores.json` não;
- **nome do tipo** — comparado com a epígrafe e com o texto do dispositivo, para
  achar registro que descreve outro crime.

**Nenhuma conclusão jurídica.** Cada achado é uma pergunta, e os que viram
proposta de mudança saem em PR, para revisão — nunca aplicados direto.

Uso:
    python scripts/robos/auditor/auditar.py                # relatório de tudo
    python scripts/robos/auditor/auditar.py --so hediondez
    python scripts/robos/auditor/auditar.py --json crawler/relatorios/auditoria.json

Saídas: 0 = nada a rever; 2 = erro; 3 = há achados.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
# `scripts/robos` para os pacotes dos robôs e do núcleo; `scripts` para o
# `pena_parser`, que é compartilhado com o construtor do catálogo e por isso
# não mora aqui.
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hediondez  # noqa: E402

from nucleo.dispositivo import SNAPSHOTS, chave, chaves_do_registro  # noqa: E402
from nucleo.parsear import parsear  # noqa: E402
from pena_parser import ler_penas  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

CATALOGO = RAIZ / "static" / "data" / "crimes.json"
FONTES = RAIZ / "data" / "fontes.json"
HEDIONDOS = RAIZ / "data" / "hediondos.json"
MODIFICADORES = RAIZ / "data" / "modificadores.json"
EXCECOES = Path(__file__).resolve().parent / "excecoes-auditoria.json"


def carregar(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def carregar_excecoes() -> list[dict]:
    if not EXCECOES.exists():
        return []
    return carregar(EXCECOES).get("excecoes", [])


def dispensado(excecoes: list[dict], achado: dict) -> bool:
    """Este achado já foi examinado e decidido?

    Casa sempre pelo TIPO do achado, mais um alvo: `ids` (registros do catálogo)
    ou `fonte` + `dispositivos` (chaves do compilado, para o que ainda não tem
    registro). Sem alvo a entrada é inválida e não dispensa nada — silenciar um
    tipo inteiro apagaria também o achado novo.
    """
    for e in excecoes:
        if e.get("tipo") != achado.get("tipo"):
            continue
        if achado.get("id") is not None and achado["id"] in (e.get("ids") or []):
            return True
        if (achado.get("fonte") and e.get("fonte") == achado["fonte"]
                and achado.get("dispositivo") in (e.get("dispositivos") or [])):
            return True
    return False


def dispositivos_de(fonte_id: str) -> dict:
    pasta = SNAPSHOTS / fonte_id
    arquivos = sorted(pasta.glob("*.html")) if pasta.exists() else []
    if not arquivos:
        return {}
    return {d.chave: d for d in parsear(arquivos[-1].read_text(encoding="utf-8"))}


# ── 1. Hediondez ────────────────────────────────────────────────────────────
def _impressao(fonte_id: str, chaves: list[str]) -> str | None:
    """Digital do texto vigente dos dispositivos que definem o rol.

    Serve a uma pergunta só: *a lista mudou desde que a tabela foi escrita?*
    Compara o texto consolidado (o que o parser elegeu como vigente), não o HTML
    — assim uma reformatação da página não dispara alarme falso, e uma emenda
    dispara.
    """
    disp = dispositivos_de(fonte_id)
    if not disp:
        return None
    partes = []
    for k in chaves:
        d = disp.get(k)
        if d is None:
            return None
        partes.append(d.texto or "")
        partes += [i["texto"] for i in d.incisos]
    bruto = unicodedata.normalize("NFC", "\n".join(partes))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:16]


# O casamento regra→registro e o alcance da tabela vivem em `scripts/hediondez.py`,
# compartilhados com o construtor do catálogo: duas implementações do mesmo
# critério divergem em silêncio, e o campo publicado passaria a discordar desta
# auditoria.
_casa = hediondez.casa


def auditar_hediondez(catalogo: list[dict]) -> list[dict]:
    tabela = carregar(HEDIONDOS)
    achados: list[dict] = []
    condicionais: list[int] = []

    impressao = _impressao("hediondos-8072", tabela["_meta"]["dispositivos_vigiados"])
    if impressao is None:
        achados.append({
            "campo": "hediondez", "tipo": "SEM-FONTE", "gravidade": 1,
            "detalhe": "a Lei 8.072 não está entre as fontes baixadas — sem ela, a "
                       "tabela de hediondez não pode ser verificada contra a lei",
        })
    elif tabela.get("impressao_do_texto") is None:
        achados.append({
            "campo": "hediondez", "tipo": "IMPRESSAO-AUSENTE", "gravidade": 1,
            "detalhe": f"grave `impressao_do_texto: \"{impressao}\"` em data/hediondos.json "
                       "para que a próxima mudança do rol seja detectada",
        })
    elif tabela["impressao_do_texto"] != impressao:
        achados.append({
            "campo": "hediondez", "tipo": "ROL-ALTERADO", "gravidade": 3,
            "detalhe": f"o texto do rol mudou desde {tabela['_meta']['conferido_em']} "
                       f"(impressão {tabela['impressao_do_texto']} → {impressao}). "
                       "Releia o art. 1º da Lei 8.072 e ajuste a tabela ANTES de "
                       "confiar nos achados abaixo",
        })

    def esta_fora(registro: dict) -> bool:
        """Diploma fora da auditoria — salvo os dispositivos já decididos.

        O `exceto` existe porque "fora de alcance" não é tudo ou nada. O CPM
        entrou inteiro na lista quando nenhum dos seus artigos tinha juízo de
        identidade feito; à medida que cada um é decidido, ele volta a ser
        auditado contra a tabela, e só o resto continua de fora. Sem isso, o
        trabalho de decidir não produziria vigilância nenhuma.
        """
        return hediondez.fora_de_alcance(registro, tabela)

    n_fora = 0
    for registro in catalogo:
        if esta_fora(registro):
            n_fora += 1
            continue
        # Registro que já DECLARA a condição está modelado: a hediondez dele é
        # circunstância do caso, e o catálogo diz isso em texto. Acusá-lo seria
        # cobrar uma resposta que ele deliberadamente não dá.
        if registro.get("hediondo_condicao"):
            continue
        excecao = next((e for e in tabela["excecoes"] if _casa(e, registro)), None)
        regra = next((r for r in tabela["regras"] if _casa(r, registro)), None)
        atual = registro.get("hediondo")

        if excecao:
            esperado, fundamento, condicional = excecao["hediondo"], excecao["fundamento"], False
        elif regra:
            esperado, fundamento = "Sim", regra["fundamento"]
            condicional = bool(regra.get("condicional"))
        else:
            esperado, fundamento, condicional = "Não", "fora do rol da Lei 8.072", False

        if atual == esperado:
            continue
        # Regra CONDICIONAL não decide nada: a hediondez depende de circunstância
        # do caso (grupo de extermínio, vítima criança, organização direcionada a
        # crime hediondo) ou de juízo de correspondência (crimes do CPM). Nesses,
        # tanto "Sim" quanto "Não" podem estar certos, e acusar seria ruído — a
        # lista deles sai no rodapé do relatório, para leitura.
        if condicional:
            condicionais.append(registro["id"])
            continue
        achados.append({
            "campo": "hediondez",
            "tipo": "HEDIONDEZ-DIVERGENTE", "gravidade": 2,
            "id": registro["id"], "lei": registro["lei"], "artigo": registro["artigo"],
            "crime": registro["crime"][:90],
            "de": atual, "para": esperado, "fundamento": fundamento,
            "condicional": condicional,
            "detalhe": f"catálogo diz {atual}; {fundamento} indica {esperado}",
        })

    # As pendências declaradas na própria tabela — o que se sabe que falta
    # decidir. Sem isto elas viveriam só no arquivo, e a rodada semanal deixaria
    # de lembrar que existem: silêncio de novo confundido com "está tudo certo".
    for pend in tabela.get("pendentes", []):
        # A pendência que já declara "ação: nenhuma" é limite conhecido, não
        # coisa a fazer: grave 0, e a rodada não abre issue por causa dela. Ela
        # continua IMPRESSA no relatório — o objetivo nunca foi escondê-la, foi
        # parar de chamar o mantenedor para ler o que ele mesmo já decidiu.
        declarada = (pend.get("acao") or "").strip().lower().startswith("nenhuma")
        achados.append({
            "campo": "hediondez", "tipo": "PENDENCIA-DECLARADA",
            "gravidade": 0 if declarada else 1,
            "detalhe": f"{pend['fundamento']} — {pend['descricao']} "
                       f"(ação prevista: {pend['acao']})",
        })

    if n_fora:
        achados.append({
            "campo": "hediondez", "tipo": "FORA-DE-ALCANCE", "gravidade": 0,
            "detalhe": f"{n_fora} registro(s) fora desta auditoria: "
                       + " ".join(f["motivo"] for f in tabela.get("fora_de_alcance", [])),
        })
    if condicionais:
        achados.append({
            "campo": "hediondez", "tipo": "DEPENDE-DO-CASO", "gravidade": 0,
            "ids": condicionais,
            "detalhe": f"{len(condicionais)} registro(s) em que a hediondez depende de "
                       "circunstância do caso ou de juízo de correspondência — a lei não "
                       "decide pelo tipo. Nenhum foi acusado; ficam para leitura: "
                       + ", ".join(str(i) for i in condicionais[:40]),
        })
    return achados


# ── 2. Ação penal ───────────────────────────────────────────────────────────
# As fórmulas com que a lei excepciona a regra do art. 100 do CP. A ordem
# importa: "mediante queixa" é privada; "representação" é pública condicionada.
_ACAO_PRIVADA = re.compile(r"somente\s+se\s+procede\s+mediante\s+queixa"
                           r"|s[óo]\s+se\s+procede\s+mediante\s+queixa"
                           r"|a[çc][ãa]o\s+penal\s+[ée]\s+privada", re.I)
_ACAO_CONDICIONADA = re.compile(
    r"somente\s+se\s+procede\s+mediante\s+representa[çc]"
    r"|s[óo]\s+se\s+procede\s+mediante\s+representa[çc]"
    r"|proced[ea]-se\s+mediante\s+representa[çc]"
    r"|depende\s+de\s+representa[çc]"
    r"|a[çc][ãa]o\s+penal\s+p[úu]blica\s+condicionada", re.I)

# A auditoria compara a ESPÉCIE, não a grafia. O catálogo chegou a escrever a
# ação privada de duas formas ("Privada" e "Ação Penal Privada"); desde
# 19/09/2026 o `transform_data.py` (VOCABULARIO) só aceita a segunda, e a
# equivalência aqui fica para relatório de dado antigo.
# Quando o próprio artigo declara a ação INCONDICIONADA numa hipótese (art. 153,
# §2º do CP) ou ressalva casos ("salvo quando praticados em prejuízo de entidade
# de direito público"), a fórmula não vale para o artigo inteiro — e a auditoria
# não pode propor nada sem ler qual hipótese é qual.
_RESSALVA = re.compile(
    r"a[çc][ãa]o\s+penal\s+(?:ser[áa]\s+)?(?:p[úu]blica\s+)?incondicionada"
    r"|salvo\s+quando|salvo\s+se|salvo\s+nos\s+casos", re.I)

_ROTULO_ACAO = {
    "privada": "Ação Penal Privada",
    "condicionada": "Pública Condicionada à Representação",
}
_EQUIVALENTES = {
    "ação penal privada": "privada", "privada": "privada",
    "ação penal privada personalíssima": "privada",
    "pública condicionada": "condicionada",
    "pública condicionada à representação": "condicionada",
    "pública condicionada à requisição": "condicionada",
    "ação penal pública condicionada": "condicionada",
    "pública incondicionada": "incondicionada",
    "ação penal pública incondicionada": "incondicionada",
}


def _texto_do_artigo(disp: dict, artigo_chave: str) -> str:
    """Texto do dispositivo mais o do caput e dos parágrafos do mesmo artigo.

    A regra de ação penal quase nunca está no dispositivo que tipifica: mora num
    parágrafo do fim do artigo ("§ 4º Somente se procede mediante queixa"), ou
    num artigo próprio de encerramento do capítulo — este último fora do alcance
    desta auditoria, e por isso declarado como limite no relatório.
    """
    base = artigo_chave.split("|")[0]
    partes = []
    for k, d in disp.items():
        if k.split("|")[0] == base:
            partes.append(d.texto or "")
    return " ".join(partes)


def auditar_acao_penal(catalogo: list[dict], indice_fontes: dict) -> list[dict]:
    achados: list[dict] = []
    cache: dict[str, dict] = {}
    for registro in catalogo:
        fid = indice_fontes.get(registro["lei"])
        k = chave(registro["artigo"])
        if not fid or not k:
            continue
        if fid not in cache:
            cache[fid] = dispositivos_de(fid)
        disp = cache[fid]
        if k not in disp:
            continue
        texto = _texto_do_artigo(disp, k)
        if _RESSALVA.search(texto):
            # O artigo distingue hipóteses ("quando resultar prejuízo para a
            # Administração Pública, a ação penal será incondicionada"). Qual
            # registro cai em qual hipótese é leitura humana — vira achado para
            # a issue, nunca proposta de troca.
            if _ACAO_PRIVADA.search(texto) or _ACAO_CONDICIONADA.search(texto):
                achados.append({
                    "campo": "acao_penal", "tipo": "ACAO-COM-RESSALVA", "gravidade": 1,
                    "id": registro["id"], "lei": registro["lei"],
                    "artigo": registro["artigo"], "crime": registro["crime"][:90],
                    "detalhe": "o artigo tem fórmula de ação penal E ressalva de hipótese; "
                               f"o catálogo registra {registro.get('acao')}",
                })
            continue
        if _ACAO_PRIVADA.search(texto):
            esperado = _ROTULO_ACAO["privada"]
        elif _ACAO_CONDICIONADA.search(texto):
            esperado = _ROTULO_ACAO["condicionada"]
        else:
            continue                      # silêncio da lei = regra do art. 100
        if registro.get("acao_condicao"):
            continue                      # a espécie depende do caso, e está declarada
        atual = (registro.get("acao") or "").strip()
        especie_atual = _EQUIVALENTES.get(atual.lower(), atual.lower())
        especie_esperada = "privada" if esperado == _ROTULO_ACAO["privada"] else "condicionada"
        if especie_atual == especie_esperada:
            continue
        achados.append({
            "campo": "acao_penal", "tipo": "ACAO-DIVERGENTE", "gravidade": 2,
            "id": registro["id"], "lei": registro["lei"], "artigo": registro["artigo"],
            "crime": registro["crime"][:90], "de": atual, "para": esperado,
            "detalhe": f"o artigo traz fórmula de ação {esperado.lower()}; "
                       f"o catálogo registra {atual}",
        })
    return achados


# ── 3. Causas de aumento e diminuição ───────────────────────────────────────
# Ampliada em 28/09/2026: "a pena aumenta-se de" (CP, art. 157, §2º; art. 171, §3º),
# "as penas aumentam-se de" (art. 342, §1º), "pode ser reduzida de" (art. 24, §2º) e
# "diminuir a pena de" (Lei 8.176, art. 1º-B, §1º) e "as penas poderão ser reduzidas
# de" (Lei 11.343, art. 33, §4º — o tráfico privilegiado) passavam em silêncio: 30
# dispositivos vigentes com majorante ou minorante que o auditor nunca acusou.
_MAJORANTE = re.compile(
    r"pena\s+(?:\w+\s+){0,3}(?:é|será|serão|são)\s+aumentad|aumenta(?:m)?-se\s+a\s+pena"
    r"|penas?\s+(?:[\w§º,-]+\s+){0,14}aumentam?-se\s+de"
    r"|pena\s+(?:\w+\s+){0,3}(?:é|será)\s+(?:reduzid|diminu[íi]d)|reduz-se\s+a\s+pena"
    r"|pena\s+(?:\w+\s+){0,3}(?:pode|poderá)\s+ser\s+(?:reduzid|diminu[íi]d)"
    r"|(?:diminuir|reduzir)\s+a\s+pena\s+de|diminu[íi]-la\s+de"
    r"|penas?\s+(?:[\w,]+\s+){0,4}(?:reduzid|diminu[íi]d)as?\s+(?:de|até|em)"
    r"|pena\s+ser[áa]\s+aplicada\s+em\s+dobro|aplica-se\s+em\s+dobro", re.I)
_FRACAO = re.compile(r"(?:de\s+)?(um|dois|tr[êe]s|1|2|3)[/\s]*(ter[çc]o|sexto|quarto|metade|meio|"
                     r"quinto|oitavo|d[ée]cimo)|dobro|triplo|metade", re.I)


def auditar_modificadores(indice_fontes: dict) -> list[dict]:
    """Aumentos e diminuições que a lei tem e `modificadores.json` não.

    Só LISTA. Modelar um modificador exige decidir o escopo — sobre quais tipos
    ele incide —, e isso não se lê do dispositivo isolado.
    """
    def _num(artigo: str) -> str:
        """"2º-A" e "2-A" são o mesmo artigo. "359-M-B" não é "359-M".

        O marcador ordinal é decoração de escrita: o catálogo de modificadores o
        usa ("art. 2º, §4º") e a chave do parser não ("Art. 2|§ 4º"). Sem
        normalizar, cada dispositivo com ordinal aparecia como MODIFICADOR-AUSENTE
        mesmo já estando modelado — foi o que fez o art. 2º, §4º da Lei 12.850
        constar da lista de 109, tendo linha própria desde a v1.2.0.
        """
        return re.sub(r"[ºo°]", "", artigo.strip().lower())

    def _diploma(rotulo: str) -> str:
        """"CPM (DL 1.001/69)" e "CPM" são o mesmo diploma.

        O catálogo de modificadores escreve o diploma curto ("CPM, art. 160,
        parágrafo único"); `fontes.json` guarda o rótulo longo, com o número do
        decreto-lei entre parênteses. Sem cortar o parêntese, os 18 aumentos do
        CPM e os 3 da LCP apareciam como ausentes depois de cadastrados.
        """
        return re.split(r"\s*\(", rotulo.strip(), maxsplit=1)[0].strip().lower()

    mods = carregar(MODIFICADORES)["modificadores"]
    ja_modelados = set()
    for m in mods:
        disp = m.get("dispositivo", "")
        mm = re.search(r"art\.?\s*([\w-]+)", disp, re.I)
        lei = re.match(r"([^,]+)", disp)
        if mm and lei:
            ja_modelados.add((_diploma(lei.group(1)), _num(mm.group(1))))

    achados: list[dict] = []
    fontes = {f["id"]: f for f in carregar(FONTES)["fontes"]}
    vistos = set()
    for rotulo, fid in sorted(indice_fontes.items()):
        for k, d in dispositivos_de(fid).items():
            if d.situacao != "vigente" or d.citacao:
                continue
            texto = d.texto or ""
            if not _MAJORANTE.search(texto) or not _FRACAO.search(texto):
                continue
            artigo = _num(k.split("|")[0].replace("Art. ", ""))
            # Todos os rótulos do diploma, não só o primeiro: o art. 326-B do
            # Código Eleitoral entrou no catálogo pela lei que o criou
            # ("Lei 14.192/21"), que é rótulo do mesmo diploma.
            modelado = any((_diploma(r), artigo) in ja_modelados
                           for r in fontes[fid]["rotulos"])
            if modelado or (fid, k) in vistos:
                continue
            vistos.add((fid, k))
            achados.append({
                "campo": "modificadores", "tipo": "MODIFICADOR-AUSENTE", "gravidade": 1,
                "fonte": fid, "dispositivo": k,
                "detalhe": texto[:150],
            })
    return achados


# ── 4-bis. Pena importada por remissão ──────────────────────────────────────
_MESMA_PENA = re.compile(r"\b(?:na|nas)\s+mesmas?\s+penas?\s+incorre", re.I)


def auditar_pena_por_remissao(catalogo: list[dict], indice_fontes: dict) -> list[dict]:
    """Dispositivo que importa a pena de outro — e o catálogo publica outra coisa.

    "Na mesma pena incorre" não deixa moldura no texto do parágrafo. `ler_penas`
    devolve vazio, e o conferidor PULA o dispositivo: o registro entra na conta
    dos "com pena definida por referência" e nunca é confrontado. São 137 hoje —
    um oitavo do catálogo, declarado como não conferido e, na prática, invisível.

    Foi por aí que três dos quatro incisos do §1º do art. 151 do CP publicaram 1
    a 3 anos de detenção. A pena deles é a do CAPUT, que é de 1 a 6 meses ou
    multa; a de 1 a 3 anos é a do §3º. Seis vezes o máximo, doze vezes o mínimo,
    e a diferença tira o tipo do rol de menor potencial ofensivo — some a
    transação penal.

    ACHADO PARA LEITURA, nunca correção automática: "as mesmas penas" tanto pode
    remeter ao caput quanto ao parágrafo imediatamente anterior. O §4º do art.
    289 do CP importa a pena do §3º, não a do caput, e está certo — comparar
    sempre com o caput acusaria um registro correto.
    """
    achados: list[dict] = []
    cache: dict[str, dict] = {}
    for registro in catalogo:
        fid = indice_fontes.get(registro["lei"])
        k = chave(registro["artigo"])
        if not fid or not k:
            continue
        if fid not in cache:
            cache[fid] = dispositivos_de(fid)
        disp = cache[fid]
        d = disp.get(k)
        if d is None or d.citacao or k.endswith("|caput"):
            continue
        if not _MESMA_PENA.search(f"{d.texto or ''} {d.pena_texto or ''}"):
            continue
        if ler_penas(d.pena_texto or ""):
            continue                      # tem moldura própria: o differ já confere
        caput = disp.get(f"{k.split('|')[0]}|caput")
        if caput is None:
            continue
        molduras = ler_penas(caput.pena_texto or caput.texto or "")
        if not molduras or molduras[0]["so_multa"]:
            continue
        lmin, lmax = molduras[0]["min_meses"], molduras[0]["max_meses"]
        cmin, cmax = registro["pena_min_meses"], registro["pena_max_meses"]
        if abs(cmin - lmin) <= 0.5 and abs(cmax - lmax) <= 0.5:
            continue
        achados.append({
            "campo": "pena_remissao", "tipo": "PENA-IMPORTADA-DIVERGE", "gravidade": 2,
            "id": registro["id"], "lei": registro["lei"], "artigo": registro["artigo"],
            "crime": registro["crime"][:90],
            "detalhe": f"o dispositivo diz 'na mesma pena incorre' e não traz moldura própria; "
                       f"o catálogo publica {cmin:g}–{cmax:g} meses e o CAPUT comina "
                       f"{lmin:g}–{lmax:g}. Confira a qual pena o dispositivo remete — pode ser "
                       "a do caput ou a do parágrafo anterior",
        })
    return achados


# ── 4. Nome do tipo ─────────────────────────────────────────────────────────
_PALAVRA = re.compile(r"[a-zà-ÿ]{5,}", re.I)
_VAZIAS = {"artigo", "pessoa", "outrem", "alguem", "alguém", "contra", "mediante",
           "quando", "aquele", "sobre", "qualquer", "outro", "outra", "forma"}


_ANOTACAO = re.compile(r"\([^)]*\)")


def _conduta(texto: str | None) -> str:
    """O texto do dispositivo sem as anotações do Planalto.

    O art. 1º do Decreto-Lei 16/1966 é "Constitui crime:", e a conduta está nas
    alíneas. Com a anotação "(Redação dada pelo Decreto-lei nº 56, de 1966)" a
    cabeça passava dos 60 caracteres, e os seis registros das alíneas eram
    acusados de nome suspeito contra um texto que não descreve conduta alguma.
    """
    return _ANOTACAO.sub("", texto or "").strip()


def _radicais(texto: str) -> set[str]:
    """Palavras longas, sem acento, cortadas em quatro letras.

    Comparação grosseira de propósito: o catálogo descreve a conduta, a lei a
    define, e as duas redações nunca coincidem literalmente. Quatro letras é o
    corte que faz "falsidade" alcançar "falsa" — abaixo disso o radical casa
    qualquer coisa, acima dele um nome legítimo vira suspeito."""
    limpo = unicodedata.normalize("NFKD", (texto or "").lower())
    limpo = "".join(c for c in limpo if not unicodedata.combining(c))
    return {p[:4] for p in _PALAVRA.findall(limpo) if p not in _VAZIAS}


def auditar_nomes(catalogo: list[dict], indice_fontes: dict) -> list[dict]:
    """Registros cujo nome não conversa com o texto do dispositivo.

    Heurística, e assumidamente frouxa: sinaliza para leitura humana, nunca
    propõe troca. Foi um caso desses (o art. 350 do Código Eleitoral com o nome
    de outro crime) que passou despercebido por meses.
    """
    achados: list[dict] = []
    cache: dict[str, dict] = {}
    for registro in catalogo:
        fid = indice_fontes.get(registro["lei"])
        chaves = chaves_do_registro(registro["artigo"])
        if not fid or not chaves:
            continue
        if fid not in cache:
            cache[fid] = dispositivos_de(fid)
        # Só o CAPUT: o parágrafo qualificado começa pela hipótese ("Se
        # resulta:") e não repete a conduta, então não há o que comparar —
        # comparar produzia cento e vinte acusações inúteis. Num registro
        # "c/c" a exigência vale para os DOIS lados: se um deles é parágrafo,
        # a conduta pode estar ali, e auditar só o outro compararia o nome com
        # o dispositivo errado — foi assim que "Latrocínio (tempo de guerra)"
        # era acusado contra a epígrafe do art. 405, "Roubo ou extorsão".
        if not all(k.endswith("|caput") for k in chaves):
            continue
        # Um registro "c/c" tem dois dispositivos, e o nome pode descrever
        # qualquer um deles. Só é suspeito quem não conversa com NENHUM.
        candidatos = []
        for k in chaves:
            d = cache[fid].get(k)
            if d is None or d.citacao or len(_conduta(d.texto)) < 60:
                continue
            candidatos.append(d)
        if not candidatos:
            continue
        d = candidatos[0]
        alvo = set()
        for c in candidatos:
            alvo |= _radicais(f"{c.epigrafe or ''} {c.texto or ''}")
        nome = _radicais(registro["crime"])
        if not nome or not alvo:
            continue
        comum = nome & alvo
        # Nome curto casa por acaso; exigir duas palavras em comum quando há
        # material suficiente dos dois lados evita acusar rótulo enxuto.
        if comum or len(nome) <= 2:
            continue
        achados.append({
            "campo": "nome", "tipo": "NOME-SUSPEITO", "gravidade": 1,
            "id": registro["id"], "lei": registro["lei"], "artigo": registro["artigo"],
            "crime": registro["crime"][:90],
            "detalhe": f"nenhuma palavra em comum com o dispositivo: "
                       f"{(d.epigrafe or d.texto or '')[:110]}",
        })
    return achados


def auditar_nomes_trocados(catalogo: list[dict], indice_fontes: dict) -> list[dict]:
    """O nome deste registro descreve MELHOR outro artigo do mesmo diploma?

    Este é o ponto cego da conferência de penas, e custou caro: ela confere a
    moldura contra o artigo que o REGISTRO DIZ ser. Nome trocado esconde pena
    trocada — o art. 313 do Código Eleitoral publicou por meses reclusão de 2 a 6
    anos, que é a pena do art. 348, de onde o nome tinha vindo, para um artigo
    que comina apenas dias-multa.

    E quando os dois artigos têm pena IDÊNTICA, nem a divergência aparece: o art.
    33 da Lei 9.605 passou com o nome do art. 34 porque os dois cominam detenção
    de um a três anos, ou multa, ou ambas.

    A comparação é de vocabulário, como em `auditar_nomes`, mas em vez de
    perguntar "o nome conversa com o dispositivo?" pergunta "há outro dispositivo
    com quem ele converse MAIS?". Exige vantagem de duas palavras para acusar:
    artigos vizinhos de um mesmo capítulo compartilham vocabulário, e um limiar
    apertado transformaria o relatório em ruído.
    """
    achados: list[dict] = []
    cache: dict[str, dict] = {}
    for registro in catalogo:
        fid = indice_fontes.get(registro["lei"])
        chaves = chaves_do_registro(registro["artigo"])
        if not fid or not chaves:
            continue
        if fid not in cache:
            cache[fid] = dispositivos_de(fid)
        disp = cache[fid]
        k = chaves[0]
        proprio = disp.get(k)
        if proprio is None or proprio.citacao:
            continue
        # Só o CAPUT, pelo mesmo motivo de `auditar_nomes`: o parágrafo começa
        # pela hipótese ("Se resulta:") e não repete a conduta, então o nome do
        # registro nunca conversa com ele — e qualquer caput do diploma pareceria
        # melhor. Comparar parágrafos produzia quarenta acusações inúteis. No
        # "c/c", a exigência vale para os dois lados.
        if not all(c.endswith("|caput") for c in chaves) or len(_conduta(proprio.texto)) < 60:
            continue
        nome = _radicais(registro["crime"])
        if len(nome) < 3:
            continue                       # nome enxuto casa com qualquer coisa
        # O registro "c/c" se compara com os DOIS dispositivos que o compõem, e
        # vale o melhor: o nome pode descrever a conduta de um ou do outro.
        meu = max(
            len(nome & _radicais(f"{d.epigrafe or ''} {d.texto or ''}"))
            for d in (disp.get(c) for c in chaves) if d is not None)
        melhor, melhor_chave, melhor_texto = meu, None, ""
        for chave_outra, d in disp.items():
            if chave_outra in chaves or d.citacao or d.situacao != "vigente":
                continue
            if not chave_outra.endswith("|caput") or len(d.texto or "") < 60:
                continue
            # E só artigos que COMINAM PENA. Um nome de tipo penal pode casar por
            # assunto com o artigo de definições, de competência ou de direitos
            # do mesmo diploma — "A retirada de tecidos, órgãos e partes do corpo
            # de pessoas falecidas…" é o art. 4º da Lei 9.434, e não é crime
            # nenhum. Um rótulo só pode ter vindo de outro TIPO.
            if not (d.pena_texto or "").strip():
                continue
            # Do outro artigo conta só o TEXTO, nunca a epígrafe. As epígrafes do
            # compilado carregam títulos de seção inteiros ("DOS CRIMES CONTRA OS
            # DESENHOS INDUSTRIAIS", "Do Direito à Saúde"), e um nome de tipo casa
            # com esses títulos por assunto, não por conduta — eram metade das
            # acusações, todas falsas.
            n = len(nome & _radicais(d.texto or ""))
            if n > melhor:
                melhor, melhor_chave = n, chave_outra
                melhor_texto = (d.epigrafe or d.texto or "")[:90]
        if melhor_chave is None or melhor - meu < 2 or melhor < 3:
            continue
        achados.append({
            "campo": "nome", "tipo": "NOME-DE-OUTRO-ARTIGO", "gravidade": 2,
            "id": registro["id"], "lei": registro["lei"], "artigo": registro["artigo"],
            "crime": registro["crime"][:90],
            "detalhe": f"o nome tem {melhor} palavras em comum com `{melhor_chave}` e apenas "
                       f"{meu} com o próprio dispositivo — {melhor_texto}. RECONFIRA A PENA: "
                       "ela pode ter vindo junto com o nome",
        })
    return achados


# ── Relatório ───────────────────────────────────────────────────────────────
TITULOS = {
    "hediondez": "Hediondez (Lei 8.072, art. 1º)",
    "acao_penal": "Ação penal",
    "modificadores": "Causas de aumento e diminuição",
    "nome": "Nome do tipo",
    "pena_remissao": "Pena importada por remissão",
    "excecoes": "Achados omitidos por decisão já tomada",
}
LIMITES = {
    "hediondez": "O rol é fechado, mas três incisos dependem de circunstância do caso "
                 "(grupo de extermínio, organização direcionada a crime hediondo, lesão "
                 "contra vítima qualificada) — nesses, `Não` é resposta legítima e não é "
                 "acusado. O inciso VI do parágrafo único (crimes do CPM com identidade "
                 "com os do rol) exige juízo de correspondência artigo a artigo: a varredura "
                 "do Livro II fechou em 23/09/2026 (decisão 29), as correspondências estão na "
                 "tabela e, desde 28/09/2026, o CPM é auditado inteiro contra ela — "
                 "`fora_de_alcance` ficou vazio.",
    "acao_penal": "Só enxerga a fórmula quando ela está no MESMO artigo do tipo. Regra de "
                  "ação penal em artigo de encerramento de capítulo (art. 145 do CP, por "
                  "exemplo) ou em outro diploma (Lei 9.099 para a lesão leve) não é "
                  "alcançada.",
    "modificadores": "Lista o que a lei tem e o catálogo de modificadores não. Não propõe "
                     "modelagem: definir o escopo — sobre quais tipos o aumento incide — "
                     "não se lê do dispositivo isolado.",
    "nome": "Heurística de palavras em comum, em duas direções. NOME-SUSPEITO acusa o "
            "rótulo que não conversa com o próprio dispositivo; NOME-DE-OUTRO-ARTIGO acusa "
            "o que conversa MAIS com outro artigo do mesmo diploma — o ponto cego da "
            "conferência de penas, que confere a moldura contra o artigo que o registro diz "
            "ser. Falso positivo é esperado: artigos de um mesmo capítulo descrevem condutas "
            "parecidas. Serve para leitura, nunca para troca automática.",
    "pena_remissao": "O dispositivo diz \"na mesma pena incorre\" e não deixa moldura no "
                     "próprio texto — por isso o conferidor de penas o PULA, e o registro "
                     "entra na conta dos \"com pena definida por referência\", que hoje tem "
                     "137 linhas e não é verificada. A comparação aqui é com o CAPUT, e ela "
                     "erra quando a remissão é ao parágrafo anterior: o §4º do art. 289 do CP "
                     "importa a pena do §3º e está certo. Serve para leitura, nunca para "
                     "troca automática.",
    "excecoes": "Não são achados: é a contagem do que saiu do relatório por decisão já "
                "tomada. Fica visível de propósito — uma dispensa que ninguém vê é "
                "indistinguível de um achado que nunca apareceu. O motivo e a data de "
                "cada uma estão em `scripts/robos/auditor/excecoes-auditoria.json`.",
}


def montar_relatorio(achados: list[dict]) -> str:
    L = [f"## Auditoria dos campos de classificação — {hoje().isoformat()}", ""]
    if not achados:
        L += ["Nenhuma divergência nos quatro campos auditados.", ""]
        return "\n".join(L) + "\n"

    por_campo: dict[str, list[dict]] = {}
    for a in achados:
        por_campo.setdefault(a["campo"], []).append(a)

    # "Achado" é o que pede ação. O resto é limite declarado, e chamar os dois
    # pelo mesmo nome fazia o cabeçalho anunciar trabalho onde não há.
    pedem = [a for a in achados if a.get("gravidade", 0) > 0]
    limites = len(achados) - len(pedem)
    if pedem:
        por_campo_pedem: dict[str, int] = {}
        for a in pedem:
            por_campo_pedem[a["campo"]] = por_campo_pedem.get(a["campo"], 0) + 1
        L.append(f"**{len(pedem)} achado(s) a rever**: "
                 + ", ".join(f"{v} em {TITULOS[k].split(' (')[0].lower()}"
                             for k, v in sorted(por_campo_pedem.items()))
                 + (f" — mais {limites} limite(s) declarado(s), abaixo." if limites else ""))
    else:
        L.append(f"**Nada a rever.** Os {limites} item(ns) abaixo são limites "
                 "declarados — registro fora do alcance da auditoria, hediondez que "
                 "depende do caso, achado já julgado e pendência com ação prevista "
                 "\"nenhuma\". Ficam impressos porque um limite que ninguém vê é "
                 "indistinguível de um achado que nunca apareceu.")
    L.append("")
    for campo, itens in sorted(por_campo.items()):
        L += [f"### {TITULOS[campo]} — {len(itens)}", "",
              f"> _Limite conhecido:_ {LIMITES[campo]}", ""]
        for a in sorted(itens, key=lambda x: -x["gravidade"])[:60]:
            cabeca = (f"id {a['id']} — `{a['lei']} {a['artigo']}`"
                      if "id" in a else f"`{a.get('fonte', '')} {a.get('dispositivo', '')}`")
            L.append(f"- **{a['tipo']}** {cabeca}")
            if a.get("crime"):
                L.append(f"  - *{a['crime']}*")
            L.append(f"  - {a['detalhe']}")
        if len(itens) > 60:
            L.append(f"- _(+{len(itens) - 60} não listados)_")
        L.append("")
    return "\n".join(L) + "\n"


def rodar(so: str | None = None) -> list[dict]:
    catalogo = carregar(CATALOGO)
    fontes = carregar(FONTES)["fontes"]
    indice_fontes = {r: f["id"] for f in fontes for r in f["rotulos"]}

    achados: list[dict] = []
    if so in (None, "hediondez"):
        achados += auditar_hediondez(catalogo)
    if so in (None, "acao"):
        achados += auditar_acao_penal(catalogo, indice_fontes)
    if so in (None, "modificadores"):
        achados += auditar_modificadores(indice_fontes)
    if so in (None, "nome"):
        achados += auditar_nomes(catalogo, indice_fontes)
        achados += auditar_nomes_trocados(catalogo, indice_fontes)
    if so in (None, "remissao"):
        achados += auditar_pena_por_remissao(catalogo, indice_fontes)

    # O que já foi julgado sai do relatório — mas só o que foi julgado. A
    # dispensa casa por tipo E alvo, nunca por tipo sozinho: achado NOVO no
    # mesmo dispositivo continua aparecendo. E a própria dispensa é contada e
    # nomeada: uma omissão invisível é indistinguível de achado que não houve.
    excecoes = carregar_excecoes()
    dispensados = [a for a in achados if dispensado(excecoes, a)]
    achados = [a for a in achados if a not in dispensados]
    if dispensados:
        por_tipo: dict[str, int] = {}
        for a in dispensados:
            por_tipo[a["tipo"]] = por_tipo.get(a["tipo"], 0) + 1
        achados.append({
            "campo": "excecoes", "tipo": "JA-JULGADO", "gravidade": 0,
            "detalhe": f"{len(dispensados)} achado(s) omitido(s) por decisão já tomada "
                       f"({', '.join(f'{n} {t}' for t, n in sorted(por_tipo.items()))}) "
                       "— ver scripts/robos/auditor/excecoes-auditoria.json, que guarda o motivo "
                       "e a data de cada uma",
        })
    return achados


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Audita hediondez, ação penal, modificadores e nomes.")
    p.add_argument("--so", choices=["hediondez", "acao", "modificadores", "nome",
                                    "remissao"])
    p.add_argument("--json", metavar="ARQUIVO")
    p.add_argument("--saida", default=str(RAIZ / "crawler" / "relatorios"))
    args = p.parse_args()

    achados = rodar(args.so)
    relatorio = montar_relatorio(achados)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"auditoria-{hoje().isoformat()}.md").write_text(relatorio, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(achados, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    print(relatorio)
    # Só o que PEDE AÇÃO decide o código de saída. Gravidade 0 é limite
    # declarado — registro que sai fora do alcance, hediondez que depende do
    # caso, achado já julgado, pendência com ação "nenhuma". Eles são impressos
    # de propósito (um limite que ninguém vê é indistinguível de um achado que
    # nunca apareceu), mas não podem abrir a issue da semana: uma issue que
    # chega toda segunda sem nada a fazer ensina a não abrir a issue — e é
    # justamente ela o único lugar onde o achado real apareceria.
    return 3 if any(a.get("gravidade", 0) > 0 for a in achados) else 0


if __name__ == "__main__":
    raise SystemExit(main())
