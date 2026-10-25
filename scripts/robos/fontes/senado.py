# -*- coding: utf-8 -*-
"""A legislação federal na API de Dados Abertos do Senado.

https://legis.senado.leg.br/dadosabertos — documentação em `/api-docs`.

Dois serviços interessam aos robôs:

- **`legislacao/{tipo}/{numero}/{ano}`** (ou `legislacao/urn?urn=`): a ficha de uma
  norma, com a lista de normas POSTERIORES que a tocaram (`vides`) e, para cada
  uma, os dispositivos tocados e o que houve com cada um — acréscimo, alteração,
  revogação, e as versões vetadas de cada um;
- **`legislacao/lista?tipo=LEI&ano=`**: as leis de um ano, com número, data e
  ementa.

É METADADO catalogado à mão por gente do Senado, e erra. Medido em 25/10/2026:
a Lei 11.106/2005 revogou os arts. 217, 219 a 222 e 240 do CP, e o Senado
registra as seis como "Alteração"; o mesmo vale para os arts. 185, 279 e 281,
revogados, que ele registra como alterados. Por isso o que sai daqui APONTA —
onde olhar, que lei conferir — e nunca escreve no catálogo nem no acervo
(plano de fontes abertas, princípio 1).

A mesma ficha diz a mesma coisa duas vezes: em `vides`, norma posterior por
norma posterior, e em `disps`, dispositivo por dispositivo. E as duas não chegam
sempre juntas: às 02:20 de 25/10/2026 a ficha do CP trazia 164 `vides`; às 02:48,
nenhum, com os 590 `disps` intactos. Por isso `ler_norma` lê as duas e junta.

A data que o Senado dá é a de ASSINATURA, não a de vigência: vigência é com
`nucleo/vigencia.py`.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import date

from fontes.rede import Rede

BASE = "https://legis.senado.leg.br/dadosabertos"
# O serviço responde JSON quando o Accept pede; sem ele, XML.
REDE = Rede({"User-Agent": "AtlasPen (+https://github.com/luccas-amorim/atlaspen)",
             "Accept": "application/json"},
            tentativas=3, timeout=60, intervalo=0.5)

# O que o Senado chama de alteração que fica no texto. "Legislação Correlata",
# "Regulamentação" e "Ressalva" são remissões, não mudança de texto.
ALTERACAO_PERMANENTE = "Declaração de Alteração Permanente"
ESPECIES_LEGISLATIVAS = frozenset({
    "Lei", "Lei Complementar", "Emenda Constitucional", "Medida Provisória", "Decreto-Lei",
})


# ── O que se lê ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Item:
    """Um dispositivo tocado por uma norma posterior."""
    dispositivo: str            # como o Senado escreve: "Art. 66, caput, Inciso 5, Alínea j"
    unidade: str | None         # a unidade canônica, sem a fonte: "art. 66, v, j"; None se não se lê
    comentario: str             # "Acréscimo", "Alteração", "Revogação", "Alteração Vetada"…

    @property
    def vetado(self) -> bool:
        return "vetad" in self.comentario.lower()


@dataclass(frozen=True)
class Posterior:
    """Uma norma posterior que tocou a norma lida (um `vide` do Senado)."""
    nome: str                   # "Lei nº 15.410 de 20/05/2026"
    numero: str | None          # "15.410", com ponto de milhar, como as sentinelas
    assinatura: date | None
    declaracao: str             # "Declaração de Alteração Permanente", "… Correlata"…
    itens: tuple[Item, ...]

    @property
    def permanente(self) -> bool:
        return self.declaracao == ALTERACAO_PERMANENTE

    @property
    def especie(self) -> str:
        """"Lei", "Lei Complementar", "Emenda Constitucional", "Medida Provisória",
        "Acórdão da Ação Direta de Inconstitucionalidade", "Mensagem de Veto Parcial"…"""
        return re.split(r"\s+n[ºo°]", self.nome, maxsplit=1)[0].strip()

    @property
    def legislativa(self) -> bool:
        """Norma que muda texto por si: lei, lei complementar, emenda, MP, decreto-lei.

        Acórdão do STF e mensagem de veto também aparecem como "alteração
        permanente", mas não são a lei que a sentinela anota."""
        return self.especie in ESPECIES_LEGISLATIVAS

    def itens_vigentes(self) -> tuple[Item, ...]:
        """Os itens que não foram vetados: o que de fato mudou o texto."""
        return tuple(i for i in self.itens if not i.vetado)


REVOGACAO_NO_TODO = "Declaração de Revogação Permanente da Norma no Todo"


@dataclass(frozen=True)
class Anterior:
    """Uma norma ANTERIOR que a norma lida tocou (um `ediv` do Senado)."""
    codigo: str                 # o código do Senado, para `legislacao/{codigo}`
    nome: str                   # "Lei nº 4.898 de 09/12/1965"
    declaracao: str             # "Declaração de Revogação Permanente da Norma no Todo"…
    itens: tuple[Item, ...]

    @property
    def revogada_no_todo(self) -> bool:
        return self.declaracao == REVOGACAO_NO_TODO

    def revogacoes(self) -> tuple[Item, ...]:
        """Os dispositivos dela que a norma lida revogou (sem os vetados)."""
        return tuple(i for i in self.itens
                     if i.comentario.lower().startswith("revoga") and not i.vetado)


@dataclass(frozen=True)
class Norma:
    codigo: str
    nome: str                   # "Lei nº 7.210 de 11/07/1984"
    urn: str | None             # "urn:lex:br:federal:lei:1984-07-11;7210"
    assinatura: date | None
    ementa: str
    posteriores: tuple[Posterior, ...]
    anteriores: tuple[Anterior, ...] = ()

    def alteracoes(self, so_legislativas: bool = True) -> list[Posterior]:
        """As alterações permanentes com pelo menos um item que não foi vetado,
        da mais antiga para a mais recente."""
        return [p for p in self.posteriores
                if p.permanente and p.itens_vigentes() and (p.legislativa or not so_legislativas)]

    def ultima_alteracao(self) -> Posterior | None:
        alt = self.alteracoes()
        return alt[-1] if alt else None


@dataclass(frozen=True)
class Resumo:
    """Uma linha de `legislacao/lista`."""
    numero: int
    nome: str
    assinatura: date | None
    ementa: str


# ── Leitura do JSON (sem rede, testável com fixture) ────────────────────────
def _lista(valor) -> list:
    """O serviço devolve objeto quando há um item só, e lista quando há vários."""
    if not valor:
        return []
    return valor if isinstance(valor, list) else [valor]


def _data(texto: str | None) -> date | None:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", (texto or "").strip())
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


_NUMERO = re.compile(r"n[ºo°]\s*([\d.]+)", re.I)


def _urn(url: str | None) -> str | None:
    if not url:
        return None
    valores = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("urn")
    return valores[0] if valores else None


_ROMANOS = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
            (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]


def _romano(n: int) -> str:
    saida = []
    for valor, letra in _ROMANOS:
        while n >= valor:
            saida.append(letra)
            n -= valor
    return "".join(saida)


_ART = re.compile(r"^Art\.?\s*(\d+)((?:-[A-Za-z]+)*)$", re.I)
_PAR = re.compile(r"^§\s*(\d+)((?:-[A-Za-z]+)*)$")
_INC = re.compile(r"^Inciso\s+(\d+)((?:-[A-Za-z]+)*)$", re.I)
_ALI = re.compile(r"^Al[íi]nea\s+([a-z])$", re.I)


def unidade(dispositivo: str) -> str | None:
    """A notação do Senado na chave canônica do histórico, sem a fonte.

        "Art. 66, caput, Inciso 5, Alínea j" -> "art. 66, v, j"
        "Art. 112, § 1"                      -> "art. 112, §1º"
        "Art. 52, § 10"                      -> "art. 52, §10º"
        "Art. 112, caput, Inciso 6-A"        -> "art. 112, vi-a"
        "Art. 41, Parágrafo Único"           -> "art. 41, parágrafo único"
        "Art. 146-E, caput"                  -> "art. 146-e, caput"
        "Art. 9-A"                           -> "art. 9-a"   (o artigo inteiro)

    É a mesma forma de `historico.chave_canonica`: o caput só aparece quando a
    unidade é ele mesmo. O que não se lê (anexo, "Item 5", "Parte Geral")
    devolve None, em vez de uma chave inventada.

    Duas marcas do Senado não são unidade da lei e saem: "Pena" ou
    "Pena/Penalidade" (o preceito secundário DA unidade: "Art. 154-A, Pena" é o
    art. 154-A) e "apenas o Caput" ("Art. 157, § 2, apenas o Caput" é o §2º).
    """
    partes = [p.strip() for p in (dispositivo or "").split(",") if p.strip()]
    partes = [p for p in partes if p.lower() not in ("pena", "pena/penalidade", "apenas o caput")]
    if not partes:
        return None
    m = _ART.match(partes[0])
    if not m:
        return None
    saida = [f"art. {m.group(1)}{m.group(2).lower()}"]
    resto = partes[1:]
    if resto and resto[0].lower() == "caput":
        resto = resto[1:]
        if not resto:
            return ", ".join(saida + ["caput"])
    for p in resto:
        if (q := _PAR.match(p)):
            # A chave canônica põe o ordinal em todo parágrafo, inclusive acima
            # de 9 (`§10º`): é assim que `dispositivo_canonico.partes()` e o
            # histórico gravam, embora o campo `artigo` do catálogo escreva `§10`.
            saida.append(f"§{int(q.group(1))}º{q.group(2).lower()}")
        elif p.lower() == "parágrafo único":
            saida.append("parágrafo único")
        elif (q := _INC.match(p)):
            saida.append(_romano(int(q.group(1))) + q.group(2).lower())
        elif (q := _ALI.match(p)):
            saida.append(q.group(1).lower())
        else:
            return None
    return ", ".join(saida)


_DATA_NO_NOME = re.compile(r"\bde\s+(\d{2}/\d{2}/\d{4})")
# "Alteração (Declaração de Alteração Permanente)": o que houve, e a declaração.
_REF = re.compile(r"^(.*?)\s*\((Declaração[^()]*)\)\s*$")


def _item(dispositivo: str, comentario: str) -> Item:
    d = (dispositivo or "").strip()
    return Item(d, unidade(d), (comentario or "").strip())


def ler_norma(dados: dict) -> Norma | None:
    """A ficha de `legislacao/{tipo}/{numero}/{ano}`; None se a norma não existe.

    As normas posteriores saem da união de `vides` e `disps`, agrupadas por
    (nome da norma, declaração): uma lei pode ser alteração permanente e
    legislação correlata ao mesmo tempo, em dispositivos diferentes.
    """
    docs = _lista(((dados.get("DetalheDocumento") or {}).get("documentos") or {}).get("documento"))
    if not docs:
        return None
    doc = docs[0]
    ident = doc.get("identificacao") or {}

    grupos: dict[tuple[str, str], dict] = {}

    def grupo(nome: str, declaracao: str, assinatura: date | None) -> dict:
        g = grupos.setdefault((nome, declaracao), {"assinatura": None, "itens": {}})
        g["assinatura"] = g["assinatura"] or assinatura
        return g

    for v in _lista((doc.get("vides") or {}).get("vide")):
        nome = (v.get("nomeNormaPosterior") or "").strip()
        g = grupo(nome, (v.get("comentario") or "").strip(), _data(v.get("datAssinatura")))
        for i in _lista((v.get("itens") or {}).get("item")):
            it = _item(i.get("dispositivo"), i.get("comentario"))
            g["itens"][(it.dispositivo, it.comentario)] = it

    for disp in _lista((doc.get("disps") or {}).get("disp")):
        dispositivo = (disp.get("nomeDispositivo") or "").split(" [")[0]
        refs = disp.get("refs")
        for r in _lista(refs.get("ref") if isinstance(refs, dict) else None):
            nome = (r.get("dispositivo") or "").strip()
            m = _REF.match((r.get("comentario") or "").strip())
            comentario, declaracao = (m.group(1), m.group(2)) if m else (r.get("comentario") or "", "")
            d = _DATA_NO_NOME.search(nome)
            g = grupo(nome, declaracao.strip(), _data(d.group(1)) if d else None)
            it = _item(dispositivo, comentario)
            g["itens"].setdefault((it.dispositivo, it.comentario), it)

    posteriores = []
    for (nome, declaracao), g in grupos.items():
        m = _NUMERO.search(nome)
        posteriores.append(Posterior(nome, m.group(1) if m else None, g["assinatura"],
                                     declaracao, tuple(g["itens"].values())))
    posteriores.sort(key=lambda p: (p.assinatura or date.min, p.nome))

    anteriores = tuple(
        Anterior(str(e.get("codnormaAnterior", "")), (e.get("nomeNormaAnterior") or "").strip(),
                 (e.get("comentario") or "").strip(),
                 tuple(_item(i.get("dispositivo"), i.get("comentario"))
                       for i in _lista((e.get("itens") or {}).get("item"))))
        for e in _lista((doc.get("edivs") or {}).get("ediv")))
    return Norma(str(doc.get("id", "")), (ident.get("normaNome") or "").strip(),
                 _urn(ident.get("urlDocumento")), _data(ident.get("dataassinatura")),
                 (doc.get("ementa") or "").strip(), tuple(posteriores), anteriores)


def ler_lista(dados: dict) -> list[Resumo]:
    docs = _lista(((dados.get("ListaDocumento") or {}).get("documentos") or {}).get("documento"))
    saida = []
    for d in docs:
        try:
            numero = int(d.get("numero"))
        except (TypeError, ValueError):
            continue
        saida.append(Resumo(numero, (d.get("normaNome") or "").strip(),
                            _data(d.get("dataassinatura")), (d.get("ementa") or "").strip()))
    return sorted(saida, key=lambda r: r.numero)


# ── Rede ────────────────────────────────────────────────────────────────────
def _json(url: str) -> dict | None:
    bruto = REDE.obter(url, ausentes=(404,))
    return json.loads(bruto) if bruto else None


def url_norma(tipo: str, numero: int | str, ano: int | str) -> str:
    return f"{BASE}/legislacao/{tipo}/{numero}/{ano}"


def url_urn(urn: str) -> str:
    return f"{BASE}/legislacao/urn?urn={urllib.parse.quote(urn, safe=':;')}"


def url_lista(ano: int, tipo: str = "LEI") -> str:
    return f"{BASE}/legislacao/lista?tipo={tipo}&ano={ano}"


def norma(tipo: str, numero: int | str, ano: int | str) -> Norma | None:
    """`norma("LEI", 7210, 1984)`; tipos: LEI, LCP, DEL, CON…"""
    dados = _json(url_norma(tipo, numero, ano))
    return ler_norma(dados) if dados else None


def norma_por_codigo(codigo: str) -> Norma | None:
    """A ficha pelo código interno do Senado (o `codnormaAnterior` de um ediv)."""
    dados = _json(f"{BASE}/legislacao/{codigo}")
    return ler_norma(dados) if dados else None


def norma_por_urn(urn: str) -> Norma | None:
    dados = _json(url_urn(urn))
    return ler_norma(dados) if dados else None


def leis_do_ano(ano: int, tipo: str = "LEI") -> list[Resumo]:
    dados = _json(url_lista(ano, tipo))
    return ler_lista(dados) if dados else []


# ── Vetos ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Veto:
    """Um veto do ano (`materia/vetos/{ano}`).

    A lista não traz o resultado da votação: ela diz se o veto ainda tramita.
    Veto em tramitação pode ser derrubado, e a derrubada muda o texto; quando
    isso acontece, a promulgação das partes vetadas é anotada no compilado, e
    o Cotejador de frescor a vê como qualquer outra lei."""
    numero: str                 # "55/2026"
    total: bool
    em_tramitacao: bool
    assunto: str
    ementa: str                 # a ementa da MATÉRIA vetada, que diz o que ela altera
    publicado_em: str | None
    url_mensagem: str | None


def ler_vetos(dados: dict) -> list[Veto]:
    vetos = _lista(((dados.get("ListaVetosAnoCN") or {}).get("Vetos") or {}).get("Veto"))
    saida = []
    for v in vetos:
        mat = v.get("Materia") or {}
        vet = v.get("MateriaVetada") or {}
        saida.append(Veto(f"{mat.get('Numero', '?')}/{mat.get('Ano', '?')}",
                          (v.get("Total") or "") == "Sim",
                          (mat.get("EmTramitacao") or "") == "Sim",
                          (v.get("Assunto") or "").strip(),
                          (vet.get("Ementa") or mat.get("Ementa") or "").strip(),
                          v.get("DataPublicacao"),
                          (v.get("Mensagem") or {}).get("UrlPlanalto")))
    return saida


def vetos_do_ano(ano: int) -> list[Veto]:
    dados = _json(f"{BASE}/materia/vetos/{ano}")
    return ler_vetos(dados) if dados else []
