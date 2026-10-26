# -*- coding: utf-8 -*-
"""Os precedentes do STF e do STJ no Banco Nacional de Precedentes do CNJ.

https://pangeabnp.pdpj.jus.br — a API pública que alimenta o painel de
precedentes do CNJ. Responde a POST com um filtro em JSON e devolve, por
precedente: o órgão, o tipo, o número, a situação ("Vigente", "Cancelado",
"Revisado"…), a ementa e o texto da decisão (controle concentrado), a questão e a
tese (repercussão geral, repetitivo, súmula), o ato impugnado codificado e a
data da última atualização. Os tipos lidos estão em `CONSULTAS`; o filtro exige
a lista deles (sem ela, 400). Do STM o banco não tem nada (contado em 25/10/2026).

Fonte OFICIAL, e incompleta. Medido em 25/10/2026: da ADPF 130 (Lei de Imprensa)
ela tem só a cautelar de 2008, não o mérito de 2009; a ADPF 291 (CPM, art. 235)
não está lá. Por isso confirma o que tem, e o silêncio dela não prova nada. Nada
daqui escreve no catálogo (AGENTS.md, "fonte secundária aponta, não escreve"):
uma decisão do STF muda o registro só depois de lida por quem assina.

O endereço e o filtro são os do `scripts/baixar_jurisprudencia.py` do ctresb/leis
(MIT, ver `LICENSE-ctresb-leis.txt`). Medido aqui: `atualizacaoDesde` casa com a
`ultimaAtualizacao` do precedente e só funciona como `dd/mm/aaaa` — em ISO o
filtro é ignorado e volta o banco inteiro.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from fontes.rede import Rede

API = "https://pangeabnp.pdpj.jus.br/api/v1/precedentes"
# Contados em 25/10/2026. Ficam de fora a controvérsia do STJ (CT, 830), que é
# proposta de afetação e não decide nada, e a suspensão em IRDR (SIRDR, 11).
CONSULTAS = {
    "STF": ("ADI", "ADPF", "ADC", "ADO", "RG", "SUM", "SV"),
    "STJ": ("SUM", "RR", "IAC"),
}
TIPOS_STF = CONSULTAS["STF"]
REDE = Rede({"User-Agent": "AtlasPen (+https://github.com/luccas-amorim/atlaspen)",
             "Accept": "application/json", "Content-Type": "application/json"},
            tentativas=3, timeout=120, intervalo=0.5)


@dataclass(frozen=True)
class Precedente:
    id: str                     # "stf-rg-113", "stf-adpf-496"
    tipo: str                   # "RG", "ADPF", "ADI"…
    numero: str
    decisao: str | None         # "MERITO", "MEDIDA_CAUTELAR", "EMBARGOS_DE_DECLARACAO"… (concentrado)
    atualizado_em: date | None
    ato_impugnado: str          # codificado: "LEG-FED DEL-002848 ANO-1940 ART-00331 …"
    texto: str                  # ementa e decisão (concentrado), ou questão e tese (RG)
    paradigmas: tuple[str, ...] = field(default=())   # o processo-paradigma do tema (RG)
    orgao: str = "STF"
    situacao: str | None = None  # "Vigente", "Cancelado", "Revisado", "APROVADO"…

    @property
    def rotulo(self) -> str:
        if self.tipo == "RG":
            return f"Tema {self.numero} de repercussão geral"
        if self.tipo == "RR":
            return f"Tema {self.numero} dos repetitivos do {self.orgao}"
        if self.tipo == "SV":
            return f"Súmula Vinculante {self.numero}"
        if self.tipo == "SUM":
            return f"Súmula {self.numero} do {self.orgao}"
        return f"{self.tipo} {self.numero}" + (f" do {self.orgao}" if self.orgao != "STF" else "")


def _data(texto: str | None) -> date | None:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", (texto or "").strip())
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def _limpo(texto: str | None) -> str:
    """Sem HTML (a tese do STJ vem em `<p>…</p><br>`) e sem o "não informado" que
    o CNJ põe no campo vazio — o enunciado das súmulas do STF está na `questao`, e
    a `tese` delas diz só isso."""
    t = re.sub(r"<[^>]+>", " ", texto or "")
    return "" if t.strip().lower() == "não informado" else t


def ler_resultados(dados: dict) -> list[Precedente]:
    saida = []
    for r in dados.get("resultados") or []:
        if r.get("textoEmenta") or r.get("textoDecisao"):
            partes = (r.get("textoEmenta"), r.get("textoDecisao"))
        else:
            partes = (r.get("questao"), r.get("tese"))
        texto = " ".join(_limpo(x) for x in partes if _limpo(x))
        paradigmas = tuple(f"{p.get('numero')}" for p in r.get("processosParadigma") or [] if isinstance(p, dict))
        saida.append(Precedente(r.get("id") or "", r.get("tipo") or "", str(r.get("nr") or ""),
                                r.get("decisao"), _data(r.get("ultimaAtualizacao")),
                                r.get("textoAtoImpugnado") or "", re.sub(r"\s+", " ", texto).strip(),
                                paradigmas, r.get("orgao") or "STF", r.get("situacao")))
    return saida


def filtro(**campos) -> dict:
    base = {"buscaGeral": "", "todasPalavras": "", "quaisquerPalavras": "", "semPalavras": "",
            "trechoExato": "", "atualizacaoDesde": "", "atualizacaoAte": "", "cancelados": True,
            "ordenacao": "Text", "nr": "", "pagina": 1, "tamanhoPagina": 50,
            "orgaos": ["STF"], "tipos": list(TIPOS_STF)}
    base.update(campos)
    return base


def _consultar(f: dict) -> dict:
    bruto = REDE.obter(API, ausentes=(), corpo=json.dumps({"filtro": f}).encode())
    dados = json.loads(bruto)
    if not isinstance(dados.get("resultados"), list):
        raise ValueError("o CNJ respondeu sem a lista de resultados")
    return dados


def atualizados_desde(desde: date, orgao: str = "STF", tipos: tuple[str, ...] | None = None,
                      paginas: int = 20) -> list[Precedente]:
    """Os precedentes do órgão cuja última atualização é `desde` ou depois."""
    tipos = tipos or CONSULTAS[orgao]
    saida, pagina = [], 1
    while pagina <= paginas:
        dados = _consultar(filtro(atualizacaoDesde=desde.strftime("%d/%m/%Y"), orgaos=[orgao],
                                  tipos=list(tipos), pagina=pagina))
        lote = ler_resultados(dados)
        saida += lote
        if len(lote) < 50 or len(saida) >= int(dados.get("total") or 0):
            break
        pagina += 1
    return saida


def por_numero(tipo: str, numero: str, orgao: str = "STF") -> list[Precedente]:
    return ler_resultados(_consultar(filtro(nr=str(numero), orgaos=[orgao], tipos=[tipo])))
