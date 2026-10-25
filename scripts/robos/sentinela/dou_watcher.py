# -*- coding: utf-8 -*-
"""Filtro semanal do Diário Oficial, Seção 1 — sem IA (F7).

O conferidor relê os diplomas de `data/fontes.json` e é cego para uma coisa
só: **lei penal nova e autônoma**, que ainda não está em página nenhuma que ele
vigie. Este módulo cobre exatamente esse ponto cego, e nada além dele.

Como funciona, em três passos:

1. **Só lei ordinária e lei complementar.** A Seção 1 publica ~330 atos por dia,
   e mais de 90% são portaria e despacho. Pelo princípio da RESERVA LEGAL (CF,
   art. 5º, XXXIX; CP, art. 1º), só essas duas espécies criam tipo penal — nem
   medida provisória (vedada pelo art. 62, §1º, I, "b"), nem lei delegada, nem
   decreto-lei (espécie extinta em 1988), nem emenda constitucional (que manda
   criminalizar, não criminaliza). Restam pouquíssimos por semana — poucos o
   bastante para baixar o texto INTEGRAL de cada um, em vez de filtrar pelo
   resumo truncado que a listagem traz.
2. **Triagem em três níveis, pelo PRECEITO SECUNDÁRIO** — a fórmula "Pena -",
   "reclusão, de", "detenção, de". Um ato que fale de pena sem cominar nenhuma
   não cria nem altera crime. Ver `classificar`.
3. **Saída para leitura humana.** Uma seção na issue semanal. Nada entra em
   lugar nenhum automaticamente.

**Falso positivo é aceitável; falso negativo, não.** Uma lei penal nova passar
batida custa meses de catálogo desatualizado. Mas o inverso tem um limite que a
medição encontrou: contra 14 dias reais de Seção 1 — 3.569 atos, 16 normativos —
o filtro anterior devolvia SEIS candidatas e **nenhuma** trazia preceito
secundário. Ler seis textos por semana para não achar nada é o jeito mais rápido
de parar de ler, e um filtro que ninguém lê é um filtro que não existe.

Por isso o corte NÃO apaga: o descartado sai nomeado, em uma linha, com o motivo.
Três segundos de leitura, e a decisão do filtro fica auditável.

Uso:
    python scripts/robos/sentinela/dou_watcher.py                    # 8 dias até hoje
    python scripts/robos/sentinela/dou_watcher.py --data 2026-06-12 --dias 3
    python scripts/robos/sentinela/dou_watcher.py --saida crawler/relatorios

Saídas: 0 = nada a olhar; 2 = erro de execução; 3 = há candidatas.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
# `scripts/robos` para os pacotes dos robôs e do núcleo; `scripts` para o
# `pena_parser`, que é compartilhado com o construtor do catálogo e por isso
# não mora aqui.
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
FONTES = RAIZ / "data" / "fontes.json"
from nucleo.preceito import (_ANO, _EMENTA_CRIMINALIZA,  # noqa: E402,F401
                             _NUMERO_LEI, _PENA_POR_REMISSAO,
                             _REVOGA_DISPOSITIVO, _TIPIFICA, comina_pena)
from fontes.rede import UA_NAVEGADOR, FalhaDeRede, Rede  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

RELATORIOS = RAIZ / "crawler" / "relatorios"

LISTAGEM = "https://www.in.gov.br/leiturajornal?secao={secao}&data={data}"
ARTIGO = "https://www.in.gov.br/web/dou/-/{slug}"
# Sem Accept/Accept-Language de navegador o in.gov.br devolve 403 — só o
# User-Agent não basta (o Planalto, no baixar.py, se contenta com o UA).
CABECALHOS = {
    "User-Agent": UA_NAVEGADOR,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
PAUSA = 1.2                      # s entre requisições: ~15 por rodada
REDE = Rede(CABECALHOS, timeout=60, espera=lambda n: PAUSA * 3)

# Seção 1 e sua edição EXTRA — é na extra que sai a lei sancionada às pressas.
SECOES = ("do1", "do1e")

# Espécies que podem criar ou revogar tipo penal. São DUAS, pelo princípio da
# reserva legal (CF, art. 5º, XXXIX; CP, art. 1º): lei ordinária e lei
# complementar. É esse corte que faz o volume desabar — mais de 90% da Seção 1 é
# portaria e despacho.
#
# O que SAIU desta lista em 14/08/2026, e por quê:
#
# - **Medida provisória.** A CF, art. 62, §1º, I, "b", veda MP sobre direito
#   penal. Ela ficava aqui por um argumento de desenho — "o watcher registra o
#   que foi publicado, não julga constitucionalidade" —, e o argumento não se
#   sustenta contra a reserva legal: MP não gera tipo penal, ponto. Vigiar por
#   ela era vigiar o que não pode existir, e as três MPs da primeira rodada real
#   entraram e foram descartadas uma a uma.
# - **Lei delegada.** A delegação não alcança direitos individuais (CF, art. 68,
#   §1º, II), e matéria penal é deles.
# - **Decreto-lei.** A espécie não existe desde 1988: os que há são anteriores, e
#   nenhum novo será publicado. Vigiar por ela é esperar o que não vem.
# - **Emenda constitucional.** Não cria tipo penal — os arts. 5º, XLI a XLIII,
#   são mandados de criminalização, dirigidos ao legislador ordinário.
ESPECIES = re.compile(r"^(Lei|Lei\s+Complementar)$", re.IGNORECASE)

# O vocabulário de treze termos SAIU em 11/08/2026, e a razão é aritmética. Ele
# existia para decidir quais dos ~16 atos normativos de uma quinzena mereciam a
# requisição de 1,2 s que traz o texto integral. Abrir os dezesseis custa vinte
# segundos — e cada termo da lista era uma chance de falso negativo, que é o
# risco que este módulo declara inaceitável: uma ementa que diga "altera o
# Decreto-Lei nº 2.848 para dispor sobre a conduta de X" não tem nenhum dos
# treze, e o ato nem chegava a ser aberto.
#
# Agora todo ato das espécies aceitas é baixado por inteiro, e quem decide é o
# preceito secundário (`_TIPIFICA`), que foi medido e funciona.

_PARAMS = re.compile(r'<script[^>]*id="params"[^>]*>(.*?)</script>', re.S)
_TEXTO_DOU = re.compile(r'<div[^>]*class="[^"]*texto-dou[^"]*"[^>]*>(.*?)</div>\s*</div>',
                        re.S)
_TAG = re.compile(r"(?s)<[^>]+>")


# ── Rede ────────────────────────────────────────────────────────────────────
def baixar(url: str, tentativas: int = 2) -> str | None:
    """HTML da página, ou None quando a data não tem edição (404/500)."""
    try:
        bruto = REDE.obter(url, ausentes=(404, 500), tentativas=tentativas)
    except FalhaDeRede as e:
        raise e.causa from e
    if bruto is None:
        return None      # dia sem edição daquela seção
    # O in.gov.br anuncia UTF-8 e cumpre; o fallback existe porque o
    # acervo oficial brasileiro tem histórico de misturar codificação.
    try:
        return bruto.decode("utf-8")
    except UnicodeDecodeError:
        return bruto.decode("cp1252", errors="replace")


def _limpar(html: str) -> str:
    import html as _h
    return re.sub(r"\s+", " ", _h.unescape(_TAG.sub(" ", html))).strip()


def listar(dia: date, secao: str) -> list[dict]:
    """Atos publicados naquele dia e seção (o JSON que a própria página carrega)."""
    pagina = baixar(LISTAGEM.format(secao=secao, data=dia.strftime("%d-%m-%Y")))
    if not pagina:
        return []
    m = _PARAMS.search(pagina)
    if not m:
        return []
    try:
        return json.loads(m.group(1)).get("jsonArray", []) or []
    except json.JSONDecodeError:
        return []


def texto_integral(slug: str) -> str:
    """Texto do ato. Vazio quando a página não abre — o resumo cobre a falta."""
    pagina = baixar(ARTIGO.format(slug=slug))
    if not pagina:
        return ""
    m = _TEXTO_DOU.search(pagina)
    return _limpar(m.group(1)) if m else ""


# ── Filtros ─────────────────────────────────────────────────────────────────
def padrao_dos_diplomas(fontes: list[dict]) -> tuple[re.Pattern, dict[str, str]]:
    """Expressão que reconhece a citação de qualquer diploma monitorado.

    Os números saem da URL do compilado, não do rótulo: `del2848compilado.htm`
    dá 2848, `l10.826compilado.htm` dá 10826, `lcp64.htm` dá 64. É o único campo
    que TODO diploma tem e que carrega o número — rótulos como "CP" ou "ECA"
    não carregam.
    """
    numeros: dict[str, str] = {}
    for f in fontes:
        base = f["url"].rsplit("/", 1)[-1]
        base = re.sub(r"(compilado|orig)?\.html?$", "", base, flags=re.I)
        m = re.search(r"(\d[\d.]*)", base)
        if not m:
            continue
        numeros[m.group(1).replace(".", "").lstrip("0")] = f["id"]

    # "Lei nº 9.605", "Lei 9605", "Decreto-Lei nº 2.848" — a espécie na frente é
    # o que impede casar número de processo, de CNPJ ou de valor.
    alternativas = "|".join(
        rf"{n[:-3]}\.?{n[-3:]}" if len(n) > 3 else n
        for n in sorted(numeros, key=len, reverse=True))
    padrao = re.compile(
        r"(?:Leis?|Lei\s+Complementar|Decretos?-Leis?|Decreto-Lei)\s*"
        r"(?:n[ºo°.\s]*)?\s*(" + alternativas + r")\b", re.IGNORECASE)
    return padrao, numeros


def marcas_penais(texto: str) -> list[str]:
    """As marcas que o ato traz, para o relatório dizer POR QUE o abriu.

    Não filtra mais nada — filtrar era o defeito. Serve só para que a linha do
    relatório mostre o que o classificador viu.
    """
    achadas = []
    for rotulo, padrao in (("preceito secundário", _TIPIFICA),
                           ("pena por remissão", _PENA_POR_REMISSAO),
                           ("ementa criminalizadora", _EMENTA_CRIMINALIZA),
                           ("revogação de dispositivo", _REVOGA_DISPOSITIVO)):
        if padrao.search(texto):
            achadas.append(rotulo)
    return achadas


# A ementa que ANUNCIA o crime, para o caso de o texto integral não abrir. É a
# rede de segurança do nível 1: sem o corpo do ato, não há "Pena -" a encontrar.
def classificar(texto: str, ementa: str, citados: list[str]) -> tuple[str, str]:
    """(nível, por quê) — o que fazer com este ato.

    A triagem tinha um filtro só, largo: casava quem citasse diploma monitorado
    OU tivesse vocabulário penal. Medido contra 14 dias reais de Seção 1 (3.569
    atos, 16 normativos), ele devolvia SEIS candidatas e **nenhuma** trazia
    preceito secundário. Uma lei sobre saúde mental na criança entrava por
    alterar o ECA; uma sobre fundo garantidor, pela palavra "revoga"; uma sobre
    honorários de advogado, por citar o Estatuto da OAB. Ler seis textos por
    semana para não achar nada é o jeito mais rápido de parar de ler.

    O discriminador que funciona já existia no módulo, usado só para propor
    fonte nova: a fórmula do PRECEITO SECUNDÁRIO — "Pena -", "reclusão, de".
    Contra os mesmos 14 dias ela devolve zero; contra a Lei 15.358/2026, que
    criou dois tipos, ela acerta. É o que separa lei penal de lei que fala de
    pena.

    Três níveis, e o terceiro não some — é contado e nomeado no relatório:

    - **novo**: tem preceito secundário e NÃO cita diploma monitorado. É o ponto
      cego declarado do conferidor: tipo penal em página que ninguém vigia.
    - **monitorado**: tem preceito secundário, ou revoga dispositivo, E cita
      diploma que já vigiamos. O conferidor vai ver a mudança na página dele na
      rodada seguinte — o que se ganha aqui é a antecedência e o aviso de que a
      sentinela daquela fonte talvez precise mudar.
    - **descartado**: o resto. Citação sem preceito penal, ou palavra solta.
    """
    # A ementa que CITA diploma monitorado é gatilho por si, mas só quando o
    # texto integral não abriu: aí não há "Pena -" a encontrar, e o ato tem de
    # ser olhado por gente, seja qual for o verbo.
    cega = not (texto or "").strip()
    forte = (comina_pena(texto) or bool(_EMENTA_CRIMINALIZA.search(ementa))
             or (cega and bool(citados)))
    if forte and not citados:
        return "novo", "comina pena e não se apoia em diploma monitorado"
    if forte and citados:
        return "monitorado", "comina pena e altera diploma monitorado"
    if citados and _REVOGA_DISPOSITIVO.search(texto):
        return "monitorado", "revoga dispositivo de diploma monitorado"
    if citados:
        return "descartado", "cita diploma monitorado sem cominar pena"
    return "descartado", "não comina pena nem cita diploma monitorado"


def triar(itens: list[dict], padrao: re.Pattern, numeros: dict[str, str],
          buscar_texto=texto_integral) -> list[dict]:
    """Atos normativos triados em três níveis (ver `classificar`).

    Devolve TODOS os que tocam em matéria penal de algum modo, com o nível
    anotado. Quem decide o que aparece por extenso no relatório é
    `montar_relatorio` — aqui nada é jogado fora, para que o corte seja
    auditável e o `--json` continue trazendo a janela inteira.
    """
    candidatas: list[dict] = []
    for item in itens:
        if not ESPECIES.match((item.get("artType") or "").strip()):
            continue
        resumo = " ".join(filter(None, [item.get("title"), item.get("content")]))
        integral = buscar_texto(item.get("urlTitle", "")) or ""
        texto = f"{resumo} {integral}"

        citados = sorted({numeros[m.group(1).replace(".", "").lstrip("0")]
                          for m in padrao.finditer(texto)
                          if m.group(1).replace(".", "").lstrip("0") in numeros})
        # SEM pré-filtro: todo ato das espécies aceitas é classificado. O corte
        # é do classificador, e o descartado sai nomeado no relatório — três
        # segundos de leitura, e a decisão fica auditável. Filtrar antes era
        # trocar vinte segundos de requisição por uma classe de falso negativo.
        termos = marcas_penais(texto)
        nivel, porque = classificar(texto, resumo, citados)
        candidatas.append({
            "nivel": nivel,
            "porque": porque,
            "titulo": (item.get("title") or "").strip(),
            "especie": (item.get("artType") or "").strip(),
            "data": item.get("pubDate") or "",
            "url": ARTIGO.format(slug=item.get("urlTitle", "")),
            "diplomas_citados": citados,
            "termos": termos[:8],
            "integral": bool(integral),
            "ementa": (item.get("content") or "")[:300],
            # O texto integral fica no JSON da rodada. Sem ele, mudar o filtro
            # não permite RETRIAR o que já passou: o achado antigo só guardava a
            # ementa, e responder "este ato teria entrado pelo critério novo?"
            # virava ato de fé. Com ele, cada mudança de filtro é um teste
            # retroativo contra as rodadas guardadas.
            "texto_integral": integral,
        })
        candidatas[-1]["fonte_proposta"] = propor_fonte(
            candidatas[-1], integral, set(numeros))
    return candidatas



# Vocabulário que distingue "lei que CRIA crime" de "lei que fala de pena". Só o
# primeiro justifica vigiar um diploma novo toda semana.
_MESES = {m: i for i, m in enumerate(
    ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
     "setembro", "outubro", "novembro", "dezembro"), 1)}
_DATA_DO_TITULO = re.compile(r"DE\s+(\d{1,2})[º°o]?\s+DE\s+(\w+)\s+DE\s+(\d{4})", re.I)


def data_do_titulo(titulo: str) -> date | None:
    """ "LEI Nº 15.410, DE 20 DE MAIO DE 2026" -> 2026-05-20."""
    m = _DATA_DO_TITULO.search(titulo or "")
    mes = _MESES.get(m.group(2).lower().replace("marco", "março")) if m else None
    if not mes:
        return None
    try:
        return date(int(m.group(3)), mes, int(m.group(1)))
    except ValueError:
        return None


def propor_fonte(candidata: dict, integral: str, ja_monitorados: set[str]) -> dict | None:
    """Entrada de `data/fontes.json` para uma lei que parece criar tipo penal.

    Proposta, não conclusão: o `id` e os `rotulos` são chutes razoáveis, e a
    pergunta que importa — *esta lei cria tipo penal próprio?* — continua sendo
    humana. O valor está em não ter de escrever a entrada do zero: a URL do
    compilado segue padrão fixo no Planalto, e a sentinela sai do próprio texto.
    """
    if not _TIPIFICA.search(integral or ""):
        return None
    # Lei que CITA diploma monitorado está alterando algo que já vigiamos: o
    # crime novo vai aparecer na página daquele diploma, e criar fonte para ela
    # duplicaria a vigilância. O que interessa aqui é a lei que não se apoia em
    # nenhuma das páginas vigiadas — a penal nova e autônoma.
    if candidata.get("diplomas_citados"):
        return None
    m = _NUMERO_LEI.search(candidata["titulo"])
    ma = _ANO.search(candidata["titulo"])
    if not m or not ma:
        return None
    numero = m.group(1).replace(".", "")
    ano = ma.group(1)
    if numero in ja_monitorados:
        return None
    faixa = f"_ato{(int(ano) - (int(ano) - 2023) % 4)}-{(int(ano) - (int(ano) - 2023) % 4) + 3}"
    complementar = "complementar" in candidata["titulo"].lower()
    arquivo = f"lcp{numero}.htm" if complementar else f"l{numero}.htm"
    proposta = {
        "id": f"NOVA-{numero}",
        "rotulos": [f"Lei {numero[:-3]}.{numero[-3:]}/{ano[-2:]}" if len(numero) > 3
                    else f"Lei {numero}/{ano[-2:]}"],
        "url": f"https://www.planalto.gov.br/ccivil_03/{faixa}/{ano}/lei/{arquivo}",
    }
    # A URN que o construtor exige (`validar_fontes`) sai do próprio título:
    # "LEI Nº 15.410, DE 20 DE MAIO DE 2026" é a data da assinatura, que é a da
    # URN LexML. Sem data legível, a entrada sai sem `urn` e o build do PR diz
    # o que falta.
    assinatura = data_do_titulo(candidata["titulo"])
    if assinatura:
        especie = "lei.complementar" if complementar else "lei"
        proposta["urn"] = f"urn:lex:br:federal:{especie}:{assinatura.isoformat()};{numero}"
    return {
        **proposta,
        "sentinela": numero,
        "obs": (f"PROPOSTA automática a partir do DOU de {candidata['data']}. Confira a "
                f"URL (o Planalto muda o padrão em leis complementares e antigas), "
                f"escolha um `id` descritivo e ajuste os rótulos para os que o catálogo "
                f"usar. Ato: {candidata['url']}"),
    }


# ── Relatório ───────────────────────────────────────────────────────────────
TITULO_NIVEL = {
    "novo": "Possível tipo penal em diploma NÃO monitorado",
    "monitorado": "Mexe em diploma que o conferidor já vigia",
}


def montar_relatorio(candidatas: list[dict], inicio: date, fim: date) -> str:
    L = [f"## DOU — normas possivelmente penais ({inicio:%d/%m} a {fim:%d/%m})", ""]
    ler = [c for c in candidatas if c["nivel"] in TITULO_NIVEL]
    descartados = [c for c in candidatas if c["nivel"] == "descartado"]

    if not ler and not descartados:
        L += ["Nenhum ato normativo da Seção 1 tocou em matéria penal nesta janela.", ""]
        return "\n".join(L) + "\n"

    if not ler:
        L += [f"**Nada a ler.** {len(descartados)} ato(s) normativo(s) na janela, "
              "e nenhum comina pena — a lista está no fim, para conferência.", ""]
    else:
        L += [f"**{len(ler)}** ato(s) a olhar, de {len(candidatas)} ato(s) "
              "normativo(s) na janela. O corte é o **preceito secundário**: um ato que fale de "
              "pena sem cominar nenhuma não cria nem altera crime.", ""]

    for nivel in ("novo", "monitorado"):
        do_nivel = [c for c in ler if c["nivel"] == nivel]
        if not do_nivel:
            continue
        L += [f"### {TITULO_NIVEL[nivel]} — {len(do_nivel)}", ""]
        if nivel == "novo":
            L += ["É o ponto cego do conferidor: crime em página que ninguém vigia. "
                  "Acrescente o diploma em `data/fontes.json` e ele passa a ser "
                  "conferido toda semana.", ""]
        else:
            L += ["O conferidor vai ver a mudança na página do diploma na rodada "
                  "seguinte. O que se ganha aqui é a antecedência — e o aviso de que a "
                  "**sentinela** daquela fonte talvez precise apontar para esta lei.", ""]
        for c in do_nivel:
            L += [f"#### {c['titulo']}", "",
                  f"- {c['especie']}, {c['data']} — <{c['url']}>",
                  f"- **Por que entrou:** {c['porque']}"]
            if c["diplomas_citados"]:
                L.append(f"- **Diplomas citados:** {', '.join(c['diplomas_citados'])}")
            if not c["integral"]:
                L.append("- ⚠️ texto integral não pôde ser lido; a triagem usou só a ementa")
            L.append(f"- Ementa: {c['ementa']}")
            if c.get("fonte_proposta"):
                L += ["- Entrada proposta para `data/fontes.json` (o PR da semana já a "
                      "traz aplicada, para conferir):", "", "```json",
                      json.dumps(c["fonte_proposta"], ensure_ascii=False, indent=2),
                      "```"]
            L.append("")

    # O descarte é NOMEADO. O princípio do módulo é que falso negativo não se
    # tolera; um corte que apagasse o item da vista trocaria ruído por cegueira.
    # Uma linha por ato custa três segundos de leitura e mantém o corte auditável.
    if descartados:
        L += [f"### Descartados — {len(descartados)}", "",
              "Atos normativos que não cominam pena. Todo ato das espécies "
              "aceitas é baixado por inteiro e classificado — não há filtro "
              "antes da leitura. Ficam aqui nomeados, não escondidos:", ""]
        for c in descartados:
            cit = f" (cita {', '.join(c['diplomas_citados'])})" if c["diplomas_citados"] else ""
            L.append(f"- [{c['titulo']}]({c['url']}) — {c['porque']}{cit}")
        L.append("")

    tocados = sorted({d for c in candidatas for d in c["diplomas_citados"]})
    if tocados:
        L += ["> _Sentinelas a conferir:_ os diplomas " + ", ".join(f"`{d}`" for d in tocados)
              + " foram citados nesta janela. Se alguma dessas leis os alterou, a "
              "`sentinela` deles em `data/fontes.json` deve passar a apontar para a "
              "emenda nova — é ela que prova que a página baixada está fresca.", ""]
    return "\n".join(L) + "\n"


def rodar(fim: date, dias: int) -> list[dict]:
    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    padrao, numeros = padrao_dos_diplomas(fontes)

    itens: list[dict] = []
    vistos: set[str] = set()
    for i in range(dias):
        dia = fim - timedelta(days=i)
        for secao in SECOES:
            for item in listar(dia, secao):
                slug = item.get("urlTitle") or ""
                if slug in vistos:
                    continue
                vistos.add(slug)
                itens.append(item)
            time.sleep(PAUSA)
    return triar(itens, padrao, numeros)


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Filtra o DOU em busca de lei penal nova.")
    p.add_argument("--data", help="fim da janela (AAAA-MM-DD); padrão: hoje")
    p.add_argument("--dias", type=int, default=8,
                   help="tamanho da janela; 8 cobre a semana e o atraso do cron")
    p.add_argument("--saida", default=str(RELATORIOS))
    args = p.parse_args()

    fim = date.fromisoformat(args.data) if args.data else hoje()
    inicio = fim - timedelta(days=args.dias - 1)
    candidatas = rodar(fim, args.dias)

    relatorio = montar_relatorio(candidatas, inicio, fim)
    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"dou-{fim.isoformat()}.md").write_text(relatorio, encoding="utf-8")
    (destino / f"dou-{fim.isoformat()}.json").write_text(
        json.dumps(candidatas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # O PR da semana lê daqui as entradas de diploma a acrescentar em fontes.json.
    (destino / "fontes-propostas.json").write_text(
        json.dumps([c["fonte_proposta"] for c in candidatas if c.get("fonte_proposta")],
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relatorio)
    return 3 if candidatas else 0


if __name__ == "__main__":
    raise SystemExit(main())
