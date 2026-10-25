# -*- coding: utf-8 -*-
"""Os caminhos que o construtor lê e escreve, num lugar só.

`data/crimes.json` é a FONTE, editável à mão; `static/data/crimes.json` e
`static/data/qualidade.json` são DERIVADOS, e só o construtor os escreve. Os
demais são os arquivos auxiliares de que os campos derivados dependem — ids
aposentados, trilha do conferidor, avisos e histórico legislativo.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "crimes.json"
APOSENTADOS = ROOT / "data" / "ids-aposentados.json"
FONTES = ROOT / "data" / "fontes.json"
CONFERENCIA = ROOT / "data" / "conferencia.json"
OUT = ROOT / "static" / "data" / "crimes.json"
RELATORIO = ROOT / "static" / "data" / "qualidade.json"

AVISOS = ROOT / "data" / "avisos.json"

HISTORICO = ROOT / "data" / "historico-legislativo.json"
