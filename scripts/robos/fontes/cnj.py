# -*- coding: utf-8 -*-
"""Os precedentes do STF no Banco Nacional de Precedentes do CNJ.

https://pangeabnp.pdpj.jus.br — a API pública que alimenta o painel de
precedentes do CNJ. Responde a POST com um filtro em JSON e devolve, por
precedente: o tipo (ADI, ADPF, ADC, ADO; RG para tema de repercussão geral), o
número, a ementa e o texto da decisão (controle concentrado), a questão e a tese
(repercussão geral), o ato impugnado codificado e a data da última atualização.

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
TIPOS_STF = ("ADI", "ADPF", "ADC", "ADO", "RG")
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

    @property
    def rotulo(self) -> str:
        return f"Tema {self.numero} de repercussão geral" if self.tipo == "RG" else f"{self.tipo} {self.numero}"


def _data(texto: str | None) -> date | None:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", (texto or "").strip())
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def ler_resultados(dados: dict) -> list[Precedente]:
    saida = []
    for r in dados.get("resultados") or []:
        if r.get("tipo") == "RG":
            texto = " ".join(x for x in (r.get("questao"), r.get("tese")) if x)
        else:
            texto = " ".join(x for x in (r.get("textoEmenta"), r.get("textoDecisao")) if x)
        paradigmas = tuple(f"{p.get('numero')}" for p in r.get("processosParadigma") or [] if isinstance(p, dict))
        saida.append(Precedente(r.get("id") or "", r.get("tipo") or "", str(r.get("nr") or ""),
                                r.get("decisao"), _data(r.get("ultimaAtualizacao")),
                                r.get("textoAtoImpugnado") or "", re.sub(r"\s+", " ", texto).strip(),
                                paradigmas))
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


def atualizados_desde(desde: date, tipos: tuple[str, ...] = TIPOS_STF, paginas: int = 20) -> list[Precedente]:
    """Os precedentes do STF cuja última atualização é `desde` ou depois."""
    saida, pagina = [], 1
    while pagina <= paginas:
        dados = _consultar(filtro(atualizacaoDesde=desde.strftime("%d/%m/%Y"), tipos=list(tipos), pagina=pagina))
        lote = ler_resultados(dados)
        saida += lote
        if len(lote) < 50 or len(saida) >= int(dados.get("total") or 0):
            break
        pagina += 1
    return saida


def por_numero(tipo: str, numero: str) -> list[Precedente]:
    return ler_resultados(_consultar(filtro(nr=str(numero), tipos=[tipo])))
