# -*- coding: utf-8 -*-
"""Inventário de diplomas com preceito penal — Fase 1 da Conferência integral.

Estabelece o denominador do catálogo: para cada diploma, baixa o texto
COMPILADO oficial do Planalto, delimita o intervalo de artigos penais e conta
os preceitos secundários vigentes (linhas "Pena —"), ignorando texto riscado
(revogado). O resultado é ``data/diplomas.json``.

Uso:
    python scripts/inventario_diplomas.py --baixar --cache DIR    # baixa os compilados
    python scripts/inventario_diplomas.py --cache DIR             # relatório no terminal
    python scripts/inventario_diplomas.py --cache DIR --gerar     # (re)escreve data/diplomas.json

Unidade de medida: **preceito secundário** — cada cominação de pena vigente no
texto compilado. Não coincide com "tipo penal" do catálogo, que desdobra
incisos e condutas (ex.: as qualificadoras do art. 121, §2º, do CP dividem um
preceito em sete tipos). O denominador é contável e conferível; o desdobramento
em tipos é decisão editorial do catálogo.

O cache de HTML fica fora do repositório (é grande e refetchável); o que se
versiona é ``data/diplomas.json``, já conferido. Quando a página que o
Planalto serve a clientes não interativos estiver desatualizada (aconteceu com
a Lei 11.340/2006), a conferência é feita no navegador e o número entra como
``ajuste`` com o motivo registrado.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html as htmllib
import json
import re
import sys
import time
from pathlib import Path

BASE = "https://www.planalto.gov.br/ccivil_03/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AtlasPen-inventario"
RAIZ = Path(__file__).resolve().parent.parent
# A rede é a dos robôs (`scripts/robos/fontes/rede.py`), com uma tentativa só:
# o que não abre é relatado e a coleta segue.
sys.path.insert(0, str(RAIZ / "scripts" / "robos"))
from fontes.rede import Rede  # noqa: E402

REDE = Rede({"User-Agent": UA}, tentativas=1, timeout=60)
HOJE = "2026-07-19"

# ---------------------------------------------------------------------------
# Metadados curados por diploma.
#
#   url        caminho relativo em ccivil_03 do texto compilado
#   faixas     intervalos (inclusive) de artigos PENAIS; a contagem só olha
#              linhas de pena dentro deles — exclui infrações administrativas
#              ("Pena – multa" do ECA/Estatuto da Pessoa Idosa) e citações de
#              emenda a outros diplomas no fim das leis
#   situacao   vigente | revogado | nao_recepcionado
#   ajuste     substitui a contagem automática quando o texto comina pena em
#              linha corrida ("...punível com detenção de..."), com o motivo
#   rotulos    valores do campo `lei` em data/crimes.json que pertencem a este
#              diploma (tipos hospedados no CP entram no CP)
# ---------------------------------------------------------------------------
META: dict[str, dict] = {
    "cp": {
        "nome": "Código Penal — Parte Especial",
        "norma": "Decreto-Lei nº 2.848, de 7 de dezembro de 1940",
        "url": "decreto-lei/del2848compilado.htm",
        "faixas": [[121, 361]],
        "rotulos": ["CP", "CP (atualiz.)", "Lei 14.133/21", "Lei 14.811/24",
                    "Lei 14.478/22"],
        "obs": "Inclui os tipos inseridos por leis posteriores (337-E a 337-P, "
               "146-A, 171-A, 359-I a 359-T), rotulados no catálogo pela lei "
               "que os criou.",
    },
    "cpm": {
        "nome": "Código Penal Militar — Parte Especial",
        "norma": "Decreto-Lei nº 1.001, de 21 de outubro de 1969",
        "url": "decreto-lei/del1001compilado.htm",
        "faixas": [[136, 410]],
        "rotulos": ["CPM (DL 1.001/69)"],
        "obs": "Crimes militares em tempo de paz (136–354) e de guerra (355–408).",
    },
    "lcp": {
        "nome": "Lei das Contravenções Penais",
        "norma": "Decreto-Lei nº 3.688, de 3 de outubro de 1941",
        "url": "decreto-lei/del3688.htm",
        "faixas": [[18, 70]],
        "rotulos": ["LCP (DL 3.688/41)"],
        "obs": "Revogados (fora da conta): arts. 27, 39, 60, 61 e 65; o art. 25 "
               "foi declarado não recepcionado pelo STF (RE 583.523), mas segue "
               "no texto compilado.",
    },
    "ce": {
        "nome": "Código Eleitoral",
        "norma": "Lei nº 4.737, de 15 de julho de 1965",
        "url": "leis/l4737compilado.htm",
        "faixas": [[289, 354]],
        "rotulos": ["CE (Lei 4.737/65)", "Lei 14.192/21"],
        "obs": "Inclui o art. 326-B (Lei 14.192/2021), rotulado no catálogo "
               "pela lei que o criou.",
    },
    "ctb": {
        "nome": "Código de Trânsito Brasileiro (crimes de trânsito)",
        "norma": "Lei nº 9.503, de 23 de setembro de 1997",
        "url": "leis/l9503compilado.htm",
        "faixas": [[302, 312]],
        "rotulos": ["CTB", "CTB (atualiz.)"],
    },
    "eca": {
        "nome": "Estatuto da Criança e do Adolescente (crimes)",
        "norma": "Lei nº 8.069, de 13 de julho de 1990",
        "url": "leis/l8069compilado.htm",
        "faixas": [[225, 244]],
        "rotulos": ["ECA", "ECA (atualiz.)"],
        "obs": "Arts. 245–258-C são infrações administrativas (fora da conta).",
    },
    "lei9605": {
        "nome": "Crimes contra o meio ambiente",
        "norma": "Lei nº 9.605, de 12 de fevereiro de 1998",
        "url": "leis/l9605.htm",
        "faixas": [[29, 69]],
        "rotulos": ["Lei 9.605/98", "Lei 9.605/98 (atualiz.)"],
    },
    "lei13869": {
        "nome": "Abuso de autoridade",
        "norma": "Lei nº 13.869, de 5 de setembro de 2019",
        "url": "_ato2019-2022/2019/lei/L13869.htm",
        "faixas": [[9, 38]],
        "rotulos": ["Lei 13.869/19"],
    },
    "lei11343": {
        "nome": "Lei de Drogas",
        "norma": "Lei nº 11.343, de 23 de agosto de 2006",
        "url": "_ato2004-2006/2006/lei/l11343.htm",
        "faixas": [[28, 39]],
        "rotulos": ["Lei 11.343/06"],
        "ajuste": {
            "esperados": 10,
            "motivo": "O art. 28 não comina pena privativa (sanções dos incisos "
                      "I a III) e por isso não tem linha 'Pena —'; soma-se 1 aos "
                      "9 preceitos medidos.",
        },
    },
    "lei8137": {
        "nome": "Crimes contra a ordem tributária, econômica e relações de consumo",
        "norma": "Lei nº 8.137, de 27 de dezembro de 1990",
        "url": "leis/l8137.htm",
        "faixas": [[1, 7]],
        "rotulos": ["Lei 8.137/90"],
        "obs": "Arts. 5º e 6º revogados pela Lei nº 12.529/2011.",
    },
    "lei7492": {
        "nome": "Crimes contra o sistema financeiro nacional",
        "norma": "Lei nº 7.492, de 16 de junho de 1986",
        "url": "leis/l7492.htm",
        "faixas": [[2, 23]],
        "rotulos": ["Lei 7.492/86"],
    },
    "lei7716": {
        "nome": "Crimes de preconceito (racismo)",
        "norma": "Lei nº 7.716, de 5 de janeiro de 1989",
        "url": "leis/l7716.htm",
        "faixas": [[1, 20]],
        "rotulos": ["Lei 7.716/89", "Lei 7.716/89 (atualiz.)"],
    },
    "lei10826": {
        "nome": "Estatuto do Desarmamento",
        "norma": "Lei nº 10.826, de 22 de dezembro de 2003",
        "url": "leis/2003/l10.826.htm",
        "faixas": [[12, 21]],
        "rotulos": ["Lei 10.826/03"],
    },
    "cdc": {
        "nome": "Código de Defesa do Consumidor (infrações penais)",
        "norma": "Lei nº 8.078, de 11 de setembro de 1990",
        "url": "leis/l8078compilado.htm",
        "faixas": [[61, 80]],
        "rotulos": ["CDC (Lei 8.078/90)"],
    },
    "lei10741": {
        "nome": "Estatuto da Pessoa Idosa (crimes)",
        "norma": "Lei nº 10.741, de 1º de outubro de 2003",
        "url": "leis/2003/l10.741compilado.htm",
        "faixas": [[96, 109]],
        "rotulos": ["Lei 10.741/03"],
        "ajuste": {
            "esperados": 16,
            "motivo": "O art. 100 comina pena em linha corrida ('crime punível "
                      "com reclusão de 6 meses a 1 ano e multa'); soma-se 1 aos "
                      "15 preceitos medidos. Arts. 56–58 são infrações "
                      "administrativas (fora da conta).",
        },
    },
    "lei12850": {
        "nome": "Organizações criminosas",
        "norma": "Lei nº 12.850, de 2 de agosto de 2013",
        "url": "_ato2011-2014/2013/lei/l12850.htm",
        "faixas": [[2, 21]],
        "rotulos": ["Lei 12.850/13"],
    },
    "lei15358": {
        "nome": "Marco Legal do Combate ao Crime Organizado (Lei Antifacção)",
        "norma": "Lei nº 15.358, de 24 de março de 2026",
        "url": "_ato2023-2026/2026/lei/L15358.htm",
        "faixas": [[2, 3]],
        "rotulos": ["Lei 15.358/26"],
        "obs": "O §1º do art. 2º é causa de aumento e o §5º é causa de "
               "diminuição — ambos em data/modificadores.json. O §3º do art. "
               "2º foi vetado, e as remissões a ele (art. 4º desta Lei e "
               "art. 1º, par. ún., VIII, da Lei 8.072/90) são inócuas.",
    },
    "lei11101": {
        "nome": "Lei de Falências (crimes falimentares)",
        "norma": "Lei nº 11.101, de 9 de fevereiro de 2005",
        "url": "_ato2004-2006/2005/lei/l11101.htm",
        "faixas": [[168, 178]],
        "rotulos": ["Lei 11.101/05"],
    },
    "lei2889": {
        "nome": "Genocídio",
        "norma": "Lei nº 2.889, de 1º de outubro de 1956",
        "url": "leis/l2889.htm",
        "faixas": [[1, 3]],
        "rotulos": ["Lei 2.889/56"],
        "ajuste": {
            "esperados": 3,
            "motivo": "O art. 1º comina as penas por remissão ao CP ('com as "
                      "penas do art. 121, §2º...'), sem linha 'Pena —'; "
                      "soma-se 1 aos 2 preceitos medidos.",
        },
    },
    "lei9434": {
        "nome": "Transplante de órgãos (crimes)",
        "norma": "Lei nº 9.434, de 4 de fevereiro de 1997",
        "url": "leis/l9434.htm",
        "faixas": [[14, 23]],
        "rotulos": ["Lei 9.434/97"],
        "obs": "Arts. 21–23-A são sanções administrativas; o art. 23-B "
               "(transporte irregular de órgãos, Lei 14.722/2023) é crime e "
               "entra na conta.",
    },
    "lei11105": {
        "nome": "Lei de Biossegurança (crimes)",
        "norma": "Lei nº 11.105, de 24 de março de 2005",
        "url": "_ato2004-2006/2005/lei/l11105.htm",
        "faixas": [[24, 29]],
        "rotulos": ["Lei 11.105/05"],
    },
    "lei9455": {
        "nome": "Tortura",
        "norma": "Lei nº 9.455, de 7 de abril de 1997",
        "url": "leis/l9455.htm",
        "faixas": [[1, 1]],
        "rotulos": ["Lei 9.455/97"],
        "ajuste": {
            "esperados": 4,
            "motivo": "Só o caput tem linha 'Pena —'; §2º (omissão, detenção "
                      "1–4), §3º-lesão grave (reclusão 4–10) e §3º-morte "
                      "(reclusão 8–16) cominam em linha corrida.",
        },
    },
    "lei9504": {
        "nome": "Lei das Eleições (crimes)",
        "norma": "Lei nº 9.504, de 30 de setembro de 1997",
        "url": "leis/l9504.htm",
        "faixas": [[33, 91]],
        "rotulos": ["Lei 9.504/97"],
        "ajuste": {
            "esperados": 10,
            "motivo": "Todos os preceitos vêm em linha corrida ('constitui "
                      "crime, punível com...'): arts. 33 §4º; 34 §2º; 39 §5º; "
                      "40; 57-H §§1º e 2º; 68 §2º; 72; 87 §4º; 91 p. único.",
        },
    },
    "lei9279": {
        "nome": "Propriedade industrial (crimes)",
        "norma": "Lei nº 9.279, de 14 de maio de 1996",
        "url": "leis/l9279.htm",
        "faixas": [[183, 195]],
        "rotulos": ["Lei 9.279/96"],
        "obs": "O art. 186 estende os tipos a hipóteses equivalentes, sem "
               "preceito próprio.",
    },
    "lei13260": {
        "nome": "Antiterrorismo",
        "norma": "Lei nº 13.260, de 16 de março de 2016",
        "url": "_ato2015-2018/2016/lei/l13260.htm",
        "faixas": [[2, 6]],
        "rotulos": ["Lei 13.260/16"],
    },
    "dl6259": {
        "nome": "Loterias (contravenções)",
        "norma": "Decreto-Lei nº 6.259, de 10 de fevereiro de 1944",
        "url": "decreto-lei/1937-1946/del6259.htm",
        "faixas": [[45, 58]],
        "rotulos": ["DL 6.259/44"],
    },
    "lei13146": {
        "nome": "Estatuto da Pessoa com Deficiência (crimes)",
        "norma": "Lei nº 13.146, de 6 de julho de 2015",
        "url": "_ato2015-2018/2015/lei/l13146.htm",
        "faixas": [[88, 91]],
        "rotulos": ["Lei 13.146/15"],
        "obs": "A Lei nº 15.163/2025 qualificou o abandono (art. 90, §§).",
    },
    "lei9613": {
        "nome": "Lavagem de dinheiro",
        "norma": "Lei nº 9.613, de 3 de março de 1998",
        "url": "leis/l9613compilado.htm",
        "faixas": [[1, 1]],
        "rotulos": ["Lei 9.613/98", "Lei 9.613/98 (atualiz.)"],
    },
    "lei1521": {
        "nome": "Crimes contra a economia popular",
        "norma": "Lei nº 1.521, de 26 de dezembro de 1951",
        "url": "leis/l1521.htm",
        "faixas": [[2, 4]],
        "rotulos": ["Lei 1.521/51"],
    },
    "lei6385": {
        "nome": "Mercado de valores mobiliários (crimes)",
        "norma": "Lei nº 6.385, de 7 de dezembro de 1976",
        "url": "leis/l6385compilada.htm",
        "faixas": [[27, 27]],
        "rotulos": ["Lei 6.385/76"],
        "obs": "Arts. 27-C, 27-D e 27-E.",
    },
    "lei9609": {
        "nome": "Programas de computador (crimes)",
        "norma": "Lei nº 9.609, de 19 de fevereiro de 1998",
        "url": "leis/l9609.htm",
        "faixas": [[12, 12]],
        "rotulos": ["Lei 9.609/98"],
    },
    "lei9029": {
        "nome": "Práticas discriminatórias no trabalho",
        "norma": "Lei nº 9.029, de 13 de abril de 1995",
        "url": "leis/l9029.htm",
        "faixas": [[2, 2]],
        "rotulos": ["Lei 9.029/95"],
    },
    "lei6766": {
        "nome": "Parcelamento do solo urbano (crimes)",
        "norma": "Lei nº 6.766, de 19 de dezembro de 1979",
        "url": "leis/l6766.htm",
        "faixas": [[50, 52]],
        "rotulos": ["Lei 6.766/79"],
        "obs": "O art. 51 remete às penas do art. 50, sem preceito próprio.",
    },
    "lei8176": {
        "nome": "Crimes contra a ordem econômica (combustíveis)",
        "norma": "Lei nº 8.176, de 8 de fevereiro de 1991",
        "url": "leis/l8176.htm",
        "faixas": [[1, 2]],
        "rotulos": ["Lei 8.176/91"],
    },
    "lei8245": {
        "nome": "Lei do Inquilinato (disposições penais)",
        "norma": "Lei nº 8.245, de 18 de outubro de 1991",
        "url": "leis/l8245.htm",
        "faixas": [[43, 44]],
        "rotulos": ["Lei 8.245/91"],
        "ajuste": {
            "esperados": 2,
            "motivo": "Pena em linha corrida: art. 43 (contravenção, prisão "
                      "simples de 5 dias a 6 meses) e art. 44 (crime, detenção "
                      "de 3 meses a 1 ano).",
        },
    },
    "lei1579": {
        "nome": "Comissões Parlamentares de Inquérito (crimes)",
        "norma": "Lei nº 1.579, de 18 de março de 1952",
        "url": "leis/l1579.htm",
        "faixas": [[4, 4]],
        "rotulos": ["Lei 1.579/52"],
    },
    "lei14344": {
        "nome": "Lei Henry Borel",
        "norma": "Lei nº 14.344, de 24 de maio de 2022",
        "url": "_ato2019-2022/2022/lei/L14344.htm",
        "faixas": [[25, 26]],
        "rotulos": ["Lei 14.344/22"],
    },
    "lei7802": {
        "nome": "Agrotóxicos (antiga)",
        "norma": "Lei nº 7.802, de 11 de julho de 1989",
        "url": "leis/l7802.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 14.785/2023, art. 65, I",
        "data_revogacao": "2023-12-28",
        "rotulos": [],
    },
    "lei14785": {
        "nome": "Agrotóxicos (crimes)",
        "norma": "Lei nº 14.785, de 27 de dezembro de 2023",
        "url": "_ato2023-2026/2023/lei/l14785.htm",
        "faixas": [[56, 57]],
        "rotulos": ["Lei 14.785/23"],
    },
    "lei11340": {
        "nome": "Lei Maria da Penha (crime do art. 24-A)",
        "norma": "Lei nº 11.340, de 7 de agosto de 2006",
        "url": "_ato2004-2006/2006/lei/l11340.htm",
        "faixas": [[24, 24]],
        "rotulos": ["Lei 11.340/06"],
        "ajuste": {
            "esperados": 1,
            "motivo": "A página servida a clientes não interativos está "
                      "desatualizada (texto original de 2006); conferido no "
                      "navegador em 19/07/2026: único preceito é o art. 24-A, "
                      "hoje reclusão de 2 a 5 anos e multa (Lei 14.994/2024).",
        },
    },
    "lei9296": {
        "nome": "Interceptação telefônica (crimes)",
        "norma": "Lei nº 9.296, de 24 de julho de 1996",
        "url": "leis/l9296.htm",
        "faixas": [[10, 10]],
        "rotulos": ["Lei 9.296/96"],
        "obs": "Art. 10 e art. 10-A (Lei 13.964/2019).",
    },
    "lei9472": {
        "nome": "Lei Geral de Telecomunicações (crime do art. 183)",
        "norma": "Lei nº 9.472, de 16 de julho de 1997",
        "url": "leis/l9472.htm",
        "faixas": [[183, 185]],
        "rotulos": ["Lei 9.472/97"],
        "obs": "O art. 184 remete à pena do art. 183; o art. 185 não comina.",
    },
    "lei4729": {
        "nome": "Sonegação fiscal",
        "norma": "Lei nº 4.729, de 14 de julho de 1965",
        "url": "leis/1950-1969/l4729.htm",
        "faixas": [[1, 2]],
        "rotulos": ["Lei 4.729/65"],
        "obs": "Em grande parte derrogada pela Lei nº 8.137/1990, que absorveu "
               "as condutas; formalmente vigente.",
    },
    "lei6001": {
        "nome": "Estatuto do Índio (crimes)",
        "norma": "Lei nº 6.001, de 19 de dezembro de 1973",
        "url": "leis/l6001.htm",
        "faixas": [[58, 58]],
        "rotulos": ["Lei 6.001/73"],
    },
    "lei4591": {
        "nome": "Condomínios e incorporações (crimes)",
        "norma": "Lei nº 4.591, de 16 de dezembro de 1964",
        "url": "leis/l4591.htm",
        "faixas": [[65, 66]],
        "rotulos": ["Lei 4.591/64"],
        "obs": "O art. 66 define contravenções punidas na forma do art. 10 da "
               "Lei nº 1.521/1951.",
    },
    "lei4117": {
        "nome": "Código Brasileiro de Telecomunicações (crime do art. 70)",
        "norma": "Lei nº 4.117, de 27 de agosto de 1962",
        "url": "leis/l4117.htm",
        "faixas": [[70, 70]],
        "rotulos": ["Lei 4.117/62"],
        "ajuste": {
            "esperados": 1,
            "motivo": "O art. 70 comina detenção em linha corrida.",
        },
    },
    "lei4595": {
        "nome": "Sistema Financeiro Nacional (crimes revogados)",
        "norma": "Lei nº 4.595, de 31 de dezembro de 1964",
        "url": "leis/l4595.htm",
        "faixas": [[34, 44]],
        "rotulos": ["Lei 4.595/64"],
        "ajuste": {
            "esperados": 0,
            "motivo": "Nenhum crime vigente: os três da lei foram revogados — o art. 34, §1º, pela Lei 13.506/2017; o art. 38, §7º, pela LC 105/2001; e o art. 44, §7º, pela Lei 13.506/2017. O diploma fica no inventário porque o acervo o usa para nomear o dispositivo revogado (conferido em 20/09/2026).",
        },
    },
    "lei5553": {
        "nome": "Retenção de documentos",
        "norma": "Lei nº 5.553, de 6 de dezembro de 1968",
        "url": "leis/l5553.htm",
        "faixas": [[3, 3]],
        "rotulos": ["Lei 5.553/68"],
        "ajuste": {
            "esperados": 1,
            "motivo": "O art. 3º comina prisão simples em linha corrida.",
        },
    },
    "lei9807": {
        "nome": "Proteção a vítimas e testemunhas",
        "norma": "Lei nº 9.807, de 13 de julho de 1999",
        "url": "leis/l9807.htm",
        "faixas": [],
        "rotulos": ["Lei 9.807/99"],
        "ajuste": {
            "esperados": 0,
            "motivo": "Não há preceito penal vigente: o crime de revelação de "
                      "identidade de protegido foi vetado na origem. O registro "
                      "que o catálogo mantinha (id 1038, 'art. 19') não "
                      "corresponde ao texto compilado e foi removido.",
        },
    },
    "lei14597": {
        "nome": "Lei Geral do Esporte (crimes)",
        "norma": "Lei nº 14.597, de 14 de junho de 2023",
        "url": "_ato2023-2026/2023/lei/L14597.htm",
        "faixas": [[165, 171], [198, 201]],
        "rotulos": ["Lei 14.597/23"],
        "obs": "Sucedeu os crimes do Estatuto do Torcedor (Lei nº 10.671/2003, "
               "revogada pelo art. 217, III).",
    },
    "dl201": {
        "nome": "Crimes de prefeitos e vereadores",
        "norma": "Decreto-Lei nº 201, de 27 de fevereiro de 1967",
        "url": "decreto-lei/del0201.htm",
        "faixas": [[1, 1]],
        "rotulos": ["DL 201/67"],
        "ajuste": {
            "esperados": 2,
            "motivo": "O art. 1º, §1º, comina em linha corrida: reclusão de 2 a "
                      "12 anos (itens I e II) e detenção de 3 meses a 3 anos "
                      "(itens III a XXIII).",
        },
    },
    "lei9263": {
        "nome": "Planejamento familiar (crimes)",
        "norma": "Lei nº 9.263, de 12 de janeiro de 1996",
        "url": "leis/l9263.htm",
        "faixas": [[15, 21]],
        "rotulos": ["Lei 9.263/96"],
    },
    "lei6538": {
        "nome": "Serviços postais (crimes)",
        "norma": "Lei nº 6.538, de 22 de junho de 1978",
        "url": "leis/l6538.htm",
        "faixas": [[36, 45]],
        "rotulos": ["Lei 6.538/78"],
    },
    "lei6453": {
        "nome": "Atividades nucleares (crimes)",
        "norma": "Lei nº 6.453, de 17 de outubro de 1977",
        "url": "leis/l6453.htm",
        "faixas": [[19, 27]],
        "rotulos": ["Lei 6.453/77"],
    },
    "lei7643": {
        "nome": "Pesca de cetáceos",
        "norma": "Lei nº 7.643, de 18 de dezembro de 1987",
        "url": "leis/l7643.htm",
        "faixas": [[2, 2]],
        "rotulos": ["Lei 7.643/87"],
        "ajuste": {
            "esperados": 1,
            "motivo": "O art. 2º comina reclusão em linha corrida.",
        },
    },
    "lei4947": {
        "nome": "Direito agrário (crimes)",
        "norma": "Lei nº 4.947, de 6 de abril de 1966",
        "url": "leis/l4947.htm",
        "faixas": [[19, 20]],
        "rotulos": ["Lei 4.947/66"],
    },
    "lei5741": {
        "nome": "Crédito habitacional — SFH (crime do art. 9º)",
        "norma": "Lei nº 5.741, de 1º de dezembro de 1971",
        "url": "leis/l5741.htm",
        "faixas": [[9, 9]],
        "rotulos": ["Lei 5.741/71"],
        "ajuste": {
            "esperados": 1,
            "motivo": "O art. 9º comina detenção em linha corrida.",
        },
    },
    "lei5478": {
        "nome": "Ação de alimentos (crime do art. 22)",
        "norma": "Lei nº 5.478, de 25 de julho de 1968",
        "url": "leis/l5478.htm",
        "faixas": [[22, 22]],
        "rotulos": ["Lei 5.478/68"],
        "obs": "O art. 21 apenas dá redação ao art. 244 do CP (contado lá).",
    },
    "lei7347": {
        "nome": "Ação civil pública (crime do art. 10)",
        "norma": "Lei nº 7.347, de 24 de julho de 1985",
        "url": "leis/l7347compilada.htm",
        "faixas": [[10, 10]],
        "rotulos": ["Lei 7.347/85"],
        "ajuste": {
            "esperados": 1,
            "motivo": "O art. 10 comina reclusão em linha corrida.",
        },
    },
    "lei6091": {
        "nome": "Transporte de eleitores (crimes)",
        "norma": "Lei nº 6.091, de 15 de agosto de 1974",
        "url": "leis/l6091.htm",
        "faixas": [[11, 11]],
        "rotulos": ["Lei 6.091/74"],
    },
    "lc64": {
        "nome": "Lei de Inelegibilidades (crime do art. 25)",
        "norma": "Lei Complementar nº 64, de 18 de maio de 1990",
        "url": "leis/lcp/lcp64.htm",
        "faixas": [[25, 25]],
        "rotulos": ["LC 64/90"],
    },
    "lei12984": {
        "nome": "Discriminação de pessoas com HIV/aids",
        "norma": "Lei nº 12.984, de 2 de junho de 2014",
        "url": "_ato2011-2014/2014/lei/l12984.htm",
        "faixas": [[1, 1]],
        "rotulos": ["Lei 12.984/14"],
        "ajuste": {
            "esperados": 1,
            "motivo": "O art. 1º comina reclusão em linha corrida.",
        },
    },
    "lei7437": {
        "nome": "Contravenções de preconceito",
        "norma": "Lei nº 7.437, de 20 de dezembro de 1985",
        "url": "leis/l7437.htm",
        "faixas": [[3, 9]],
        "rotulos": ["Lei 7.437/85"],
        "obs": "Alcance remanescente restrito ao preconceito de sexo e de "
               "estado civil: as hipóteses de raça, cor, etnia, religião e "
               "procedência viraram crime na Lei nº 7.716/1989.",
    },
    "lei8906": {
        "nome": "Estatuto da Advocacia (crime do art. 7º-B)",
        "norma": "Lei nº 8.906, de 4 de julho de 1994",
        "url": "leis/l8906.htm",
        "faixas": [[7, 7]],
        "rotulos": ["Lei 8.906/94"],
        "obs": "Violação de prerrogativa de advogado (incluído pela Lei nº "
               "13.869/2019; pena da Lei nº 14.365/2022).",
    },
    # --- revogados / não recepcionados (registro para o acervo histórico) ---
    "lei10671": {
        "nome": "Estatuto do Torcedor",
        "norma": "Lei nº 10.671, de 15 de maio de 2003",
        "url": "leis/2003/l10.671.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 14.597/2023, art. 217, III",
        "data_revogacao": "2023-06-15",
        "rotulos": [],
    },
    "lei7170": {
        "nome": "Lei de Segurança Nacional",
        "norma": "Lei nº 7.170, de 14 de dezembro de 1983",
        "url": "leis/l7170.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 14.197/2021 (crimes contra o Estado Democrático, "
                      "hoje CP arts. 359-I a 359-T)",
        "data_revogacao": "2021-12-01",
        "data_revogacao_nota": "A Lei 14.197/2021 entrou em vigor 90 dias depois de publicada.",
        "rotulos": [],
    },
    "lei4898": {
        "nome": "Abuso de autoridade (antiga)",
        "norma": "Lei nº 4.898, de 9 de dezembro de 1965",
        "url": "leis/l4898.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 13.869/2019",
        "data_revogacao": "2020-01-03",
        "data_revogacao_nota": "A Lei 13.869/2019 entrou em vigor 120 dias depois de publicada.",
        "rotulos": [],
    },
    "lei6368": {
        "nome": "Entorpecentes (antiga)",
        "norma": "Lei nº 6.368, de 21 de outubro de 1976",
        "url": "leis/l6368.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 11.343/2006",
        "data_revogacao": "2006-10-08",
        "data_revogacao_nota": "A Lei 11.343/2006 entrou em vigor 45 dias depois de publicada.",
        "rotulos": [],
    },
    "lei5250": {
        "nome": "Lei de Imprensa",
        "norma": "Lei nº 5.250, de 9 de fevereiro de 1967",
        "url": "leis/l5250.htm",
        "situacao": "nao_recepcionado",
        "revogadora": "ADPF 130 (STF, 2009)",
        "data_revogacao": "1988-10-05",
        "data_revogacao_nota": "Não recepcionada: perdeu a vigência com a Constituição de 1988. O STF o declarou na ADPF 130, em 2009.",
        "rotulos": [],
    },
    "lei2252": {
        "nome": "Corrupção de menores (antiga)",
        "norma": "Lei nº 2.252, de 1º de julho de 1954",
        "url": "leis/1950-1969/l2252.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 12.015/2009 (conduta hoje no ECA, art. 244-B)",
        "data_revogacao": "2009-08-10",
        "rotulos": [],
    },
    "lei9437": {
        "nome": "Armas de fogo (antiga)",
        "norma": "Lei nº 9.437, de 20 de fevereiro de 1997",
        "url": "leis/l9437.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 10.826/2003",
        "data_revogacao": "2003-12-23",
        "rotulos": [],
    },
    "lei8666": {
        "nome": "Licitações (antiga)",
        "norma": "Lei nº 8.666, de 21 de junho de 1993",
        "url": "leis/l8666cons.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 14.133/2021 (crimes movidos para o CP, arts. "
                      "337-E a 337-P)",
        "data_revogacao": "2021-04-01",
        "data_revogacao_nota": "Os crimes (arts. 89 a 108) saíram na data da publicação da Lei 14.133/2021 (art. 193, I); o resto da lei, depois (art. 193, II).",
        "rotulos": [],
    },
    "dl7661": {
        "nome": "Falências (antiga)",
        "norma": "Decreto-Lei nº 7.661, de 21 de junho de 1945",
        "url": "decreto-lei/del7661.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 11.101/2005",
        "data_revogacao": "2005-06-09",
        "data_revogacao_nota": "A Lei 11.101/2005 entrou em vigor 120 dias depois de publicada, ressalvado o art. 192, que mantém o decreto-lei nos processos já em curso.",
        "rotulos": [],
    },
    "lei6815": {
        "nome": "Estatuto do Estrangeiro",
        "norma": "Lei nº 6.815, de 19 de agosto de 1980",
        "url": "leis/l6815.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 13.445/2017, art. 124, II",
        "data_revogacao": "2017-11-21",
        "data_revogacao_nota": "A Lei 13.445/2017 entrou em vigor 180 dias depois de publicada.",
        "rotulos": [],
    },
    # Os dois abaixo vieram do gerador de candidatos do acervo
    # (scripts/robos/acervo/candidatos.py), em 25/10/2026: a ficha do Senado
    # das leis vigiadas aponta a revogação no todo, e a página do Planalto do
    # diploma revogado e o artigo da lei revogadora a confirmam.
    "lei7646": {
        "nome": "Programas de computador (antiga)",
        "norma": "Lei nº 7.646, de 18 de dezembro de 1987",
        "url": "leis/l7646.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 9.609/1998, art. 16",
        "data_revogacao": "1998-02-20",
        "data_revogacao_nota": "A Lei 9.609/1998 entrou em vigor na data da publicação (DOU de 20/02/1998).",
        "rotulos": [],
    },
    "lei8974": {
        "nome": "Biossegurança (antiga)",
        "norma": "Lei nº 8.974, de 5 de janeiro de 1995",
        "url": "leis/l8974.htm",
        "situacao": "revogado",
        "revogadora": "Lei nº 11.105/2005, art. 42",
        "data_revogacao": "2005-03-28",
        "data_revogacao_nota": "A Lei 11.105/2005 entrou em vigor na data da publicação (DOU de 28/03/2005).",
        "rotulos": [],
    },
}

# Diplomas considerados e deliberadamente fora do denominador.
EXCLUIDOS = [
    {"norma": "Lei nº 1.079/1950 (crimes de responsabilidade)",
     "motivo": "Infrações político-administrativas, não tipos penais comuns; o "
               "DL 201/1967, art. 1º, entra por ser crime comum julgado pelo "
               "Judiciário."},
    {"norma": "Lei nº 8.072/1990, Lei nº 9.099/1995, LEP (7.210/1984), CPP",
     "motivo": "Alteram atributos penais e processo sem tipificar — componentes da "
               "Fase 4 do roadmap."},
    {"norma": "Lei nº 8.429/1992 (improbidade)",
     "motivo": "Sanções cíveis, não penais."},
    {"norma": "LGPD (Lei nº 13.709/2018)",
     "motivo": "Não tipifica crimes (nota de referência removida na v1.1.0)."},
    {"norma": "Decreto-Lei nº 25/1937 (patrimônio histórico)",
     "motivo": "O art. 21 apenas equipara; os tipos estão na Lei nº 9.605/1998, "
               "arts. 62–65."},
    {"norma": "Lei nº 6.938/1981, art. 15 (poluição)",
     "motivo": "Superado pela Lei nº 9.605/1998 (derrogação tácita)."},
    {"norma": "Lei nº 5.197/1967, art. 27 (fauna)",
     "motivo": "Derrogado tacitamente pela Lei nº 9.605/1998, arts. 29 ss."},
    {"norma": "Lei nº 5.700/1971 (símbolos nacionais)",
     "motivo": "Sanções de multa administrativa."},
    {"norma": "Lei nº 13.344/2016, Lei nº 9.983/2000, Lei nº 12.737/2012, "
              "Lei nº 14.197/2021, Lei nº 14.133/2021 (crimes), Lei nº "
              "14.811/2024, Lei nº 14.478/2022 (art. 171-A), Lei nº 13.445/2017 "
              "(art. 232-A do CP)",
     "motivo": "Inserem tipos no CP/CE; contados no diploma hospedeiro."},
]

RE_PENA = re.compile(
    r"\bP(?:ENAS?|enas?)\s*(?:[-–—:]\s|\s+(?=[Dd]etenção|[Rr]eclusão|[Pp]risão"
    r"|[Mm]ulta|DETENÇÃO|RECLUSÃO|PRISÃO|MULTA))"
)
# Cabeçalho de artigo: ancorado no início da linha e com "Art" maiúsculo, para
# não casar remissões ("o disposto no art. 44") nem citações de emenda a outros
# diplomas, que o Planalto abre com aspas («"Art. 172. Emitir..."»). Algumas
# páginas antigas grafam "Art . 20" (espaço antes do ponto).
RE_ART = re.compile(r"^\s*Art\s*\.?\s*(\d+)")


def baixar(cache: Path, apenas: set[str] | None = None) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for slug, meta in META.items():
        if apenas and slug not in apenas:
            continue
        destino = cache / f"{slug}.html"
        if destino.exists() and destino.stat().st_size > 1000:
            print(f"  cache  {slug}")
            continue
        url = BASE + meta["url"]
        try:
            corpo = REDE.obter(url, ausentes=())
        except Exception as exc:  # noqa: BLE001 — relatar e seguir
            print(f"  ERRO   {slug}: {getattr(exc, 'causa', exc)} ({url})")
            continue
        destino.write_bytes(corpo)
        print(f"  ok     {slug}  {len(corpo):>8} bytes")
        time.sleep(0.5)


def _decodificar(bruto: bytes) -> str:
    m = re.search(rb"charset=([\w\-]+)", bruto[:4096], re.IGNORECASE)
    enc = (m.group(1).decode("ascii", "replace") if m else "windows-1252").lower()
    try:
        return bruto.decode(enc, errors="replace")
    except LookupError:
        return bruto.decode("windows-1252", errors="replace")


def _texto_vigente(html: str) -> str:
    """Remove texto revogado (riscado) e converte o HTML em linhas de texto."""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # O Planalto marca dispositivo revogado/alterado com <strike>/<s>/<del>.
    html = re.sub(r"<(strike|s|del)\b[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # O fonte do Planalto quebra linha a ~70 colunas NO MEIO dos parágrafos;
    # colapsa antes, para que a estrutura venha só das tags de bloco.
    html = re.sub(r"[\r\n\t]+", " ", html)
    html = re.sub(r"<(p|br|div|tr|li|h\d)[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    texto = htmllib.unescape(html)
    texto = texto.replace("\xa0", " ")
    return texto


def _nas_faixas(n: int, faixas: list[list[int]]) -> bool:
    return any(lo <= n <= hi for lo, hi in faixas)


def extrair(html: str, faixas: list[list[int]]) -> dict:
    """Preceitos vigentes ('Pena —') dentro das faixas de artigos penais."""
    art_atual: int | None = None
    preceitos = 0
    artigos: set[int] = set()
    por_artigo: dict[int, int] = {}
    for linha in _texto_vigente(html).splitlines():
        linha = linha.strip()
        if not linha:
            continue
        m = RE_ART.match(linha)
        if m:
            art_atual = int(m.group(1))
        achados = len(RE_PENA.findall(linha))
        if achados and art_atual is not None and _nas_faixas(art_atual, faixas):
            preceitos += achados
            artigos.add(art_atual)
            por_artigo[art_atual] = por_artigo.get(art_atual, 0) + achados
    return {"preceitos": preceitos, "artigos": sorted(artigos), "por_artigo": por_artigo}


def _intervalos(artigos: list[int]) -> str:
    if not artigos:
        return "—"
    blocos: list[str] = []
    inicio = fim = artigos[0]
    for n in artigos[1:]:
        if n <= fim + 1:
            fim = n
        else:
            blocos.append(f"{inicio}" if inicio == fim else f"{inicio}–{fim}")
            inicio = fim = n
    blocos.append(f"{inicio}" if inicio == fim else f"{inicio}–{fim}")
    return "arts. " + ", ".join(blocos)


def _tipos_por_slug() -> dict[str, int]:
    catalogo = json.loads((RAIZ / "data" / "crimes.json").read_text(encoding="utf-8"))
    rotulo_para_slug: dict[str, str] = {}
    for slug, meta in META.items():
        for rotulo in meta.get("rotulos", []):
            rotulo_para_slug[rotulo] = slug
    contagem: dict[str, int] = {}
    sem_dono: dict[str, int] = {}
    for registro in catalogo:
        slug = rotulo_para_slug.get(registro["lei"])
        if slug is None:
            sem_dono[registro["lei"]] = sem_dono.get(registro["lei"], 0) + 1
        else:
            contagem[slug] = contagem.get(slug, 0) + 1
    for rotulo, n in sorted(sem_dono.items()):
        print(f"AVISO: rótulo do catálogo sem diploma no inventário: {rotulo!r} ({n})",
              file=sys.stderr)
    return contagem


def montar(cache: Path) -> dict:
    tipos = _tipos_por_slug()
    diplomas = []
    total = 0
    for slug, meta in META.items():
        situacao = meta.get("situacao", "vigente")
        item: dict = {
            "id": slug,
            "nome": meta["nome"],
            "norma": meta["norma"],
            "situacao": situacao,
            "fonte_url": BASE + meta["url"],
            "conferido_em": HOJE,
        }
        if situacao != "vigente":
            item["norma_revogadora"] = meta["revogadora"]
            # A perda de vigência dos dispositivos PENAIS do diploma, que é o que o
            # acervo mede; a nota explica vacatio, revogação escalonada ou não recepção.
            item["data_revogacao"] = meta.get("data_revogacao")
            if meta.get("data_revogacao_nota"):
                item["data_revogacao_nota"] = meta["data_revogacao_nota"]
            item["preceitos_esperados"] = 0
        else:
            arquivo = cache / f"{slug}.html"
            medido = extrair(_decodificar(arquivo.read_bytes()), meta["faixas"])
            item["artigos_penais"] = _intervalos(medido["artigos"]) if medido["artigos"] else "—"
            item["preceitos_medidos"] = medido["preceitos"]
            ajuste = meta.get("ajuste")
            if ajuste:
                item["preceitos_esperados"] = ajuste["esperados"]
                item["ajuste_motivo"] = ajuste["motivo"]
                if not medido["artigos"]:
                    faixas = meta["faixas"]
                    item["artigos_penais"] = _intervalos(
                        sorted({lo for lo, _ in faixas} | {hi for _, hi in faixas}))
            else:
                item["preceitos_esperados"] = medido["preceitos"]
        item["tipos_catalogados"] = tipos.get(slug, 0)
        if meta.get("rotulos"):
            item["rotulos_catalogo"] = meta["rotulos"]
        if meta.get("obs"):
            item["obs"] = meta["obs"]
        total += item["preceitos_esperados"]
        diplomas.append(item)
    return {
        "_meta": {
            "gerado_em": HOJE,
            "gerado_por": "scripts/inventario_diplomas.py",
            "unidade": "preceito secundário: cada cominação de pena vigente no "
                       "texto compilado do Planalto. Tipos do catálogo desdobram "
                       "incisos e condutas, então tipos_catalogados pode "
                       "legitimamente exceder preceitos_esperados.",
            "fonte": "Textos compilados oficiais de planalto.gov.br "
                     "(ccivil_03), texto vigente (revogações riscadas "
                     "excluídas), conferidos em " + HOJE + ".",
            "total_preceitos_esperados": total,
        },
        "diplomas": diplomas,
        "excluidos": EXCLUIDOS,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--baixar", action="store_true")
    ap.add_argument("--apenas", help="slugs separados por vírgula")
    ap.add_argument("--gerar", action="store_true",
                    help="escreve data/diplomas.json")
    args = ap.parse_args()

    apenas = set(args.apenas.split(",")) if args.apenas else None
    if args.baixar:
        baixar(args.cache, apenas)
        return 0

    inventario = montar(args.cache)
    if args.gerar:
        destino = RAIZ / "data" / "diplomas.json"
        with open(destino, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(inventario, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"escrito {destino}")
    print(f"{'diploma':34s} {'situação':10s} {'esper.':>6s} {'catál.':>6s}  artigos")
    for d in inventario["diplomas"]:
        nome = d["nome"][:33]
        print(f"{nome:34s} {d['situacao']:10s} {d['preceitos_esperados']:6d} "
              f"{d['tipos_catalogados']:6d}  {d.get('artigos_penais', '—')}")
    print(f"\nTotal de preceitos esperados (vigentes): "
          f"{inventario['_meta']['total_preceitos_esperados']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
