# -*- coding: utf-8 -*-
"""Os invariantes DUROS do catálogo: o que falha o build, independentemente de `--estrito`.

Cada `validar_*` recebe a lista de registros e devolve a lista de problemas, em
texto, na ordem em que os encontrou; `validar_tudo` encadeia todos na ordem em
que o construtor sempre os rodou. Aqui também moram `ids_aposentados` e
`proximo_id`, porque o id append-only (C3) é a mais silenciosa das convenções,
e o Proponente precisa do próximo id livre pela mesma conta que a validação usa.
"""
import json
import re
from collections import Counter

# A hediondez tem tabela curada (`data/hediondos.json`) e módulo próprio, que o
# Auditor e este construtor compartilham para não divergirem em silêncio.
import hediondez as _hediondez  # noqa: E402
# A régua de grafia do campo `artigo` é a mesma que o histórico legislativo e o
# Auditor usam para ler o dispositivo (`dispositivo_canonico`): quem a valida
# na entrada é quem impede que uma grafia nova deixe de casar regra em silêncio.
from dispositivo_canonico import problemas_de_grafia  # noqa: E402

from .caminhos import APOSENTADOS, FONTES
from .tabelas import NAO_TIPIFICA, OPERADORES_REMISSAO, VOCABULARIO


def validar_moldura(crimes: list) -> list:
    """A moldura é a AUTORIDADE — e por isso tem de estar bem escrita.

    Desde a v1.2.17 é `pena_min`/`pena_max` que define a pena publicada; o `obs`
    voltou a ser descritivo. Duas exigências, verificadas a cada build:

    1. **Inteiro quando inteiro.** `24.0` e `24` valem o mesmo para o cálculo,
       mas o primeiro polui o diff e muda o tipo no JSON público. A regra vale
       para todo mundo — quem edita à mão e quem gera correção automática.
    2. **Mínimo não pode passar do máximo.**
    """
    problemas = []
    for c in crimes:
        for campo in ("pena_min", "pena_max"):
            v = c.get(campo)
            if isinstance(v, float) and float(v).is_integer():
                problemas.append(
                    f"id {c.get('id')}: {campo}={v!r} deve ser inteiro ({int(v)})")
            if v is not None and not isinstance(v, (int, float)):
                problemas.append(f"id {c.get('id')}: {campo}={v!r} não é número")
        mn, mx = float(c.get("pena_min") or 0), float(c.get("pena_max") or 0)
        if mn > mx:
            problemas.append(f"id {c.get('id')}: pena_min {mn} maior que pena_max {mx}")
    return problemas


def validar_vocabulario(crimes: list) -> list:
    """Invariante DURO: todo campo categórico usa o vocabulário fechado."""
    return [
        f"id={c.get('id')} ({c.get('lei')} {c.get('artigo')}): {campo}={c.get(campo)!r} "
        f"fora do vocabulário {sorted(valores)}"
        for c in crimes for campo, valores in VOCABULARIO.items()
        if c.get(campo) not in valores
    ]


def validar_hediondez(crimes: list, tabela: dict) -> list:
    """Invariante DURO: hediondez afirmada tem dispositivo que a sustente.

    Em 19/09/2026 esta regra encontrou oito registros do CPM marcados como
    hediondos sem nada na tabela: roubo e extorsão militares, cuja hediondez vem
    do juízo de identidade do art. 1º, parágrafo único, VI, e que ninguém tinha
    escrito. Dois deles não se sustentaram.
    """
    problemas = []
    for c in crimes:
        r = _hediondez.classificar(c, tabela)
        onde = f"id={c.get('id')} ({c.get('lei')} {c.get('artigo')})"
        if c.get("hediondo") == "Sim" and r["especie"] == "nao":
            problemas.append(
                f"{onde}: hediondo sem regra em data/hediondos.json — escreva a regra "
                f"com o inciso do rol, ou corrija o campo")
        if (c.get("hediondo") == "Não" and r["especie"] != "nao"
                and not r["condicional"] and not c.get("hediondo_condicao")):
            problemas.append(
                f"{onde}: a tabela diz hediondo ({r['fundamento']}) e o registro diz que não")
    return problemas


def validar_tipos_penais(crimes: list) -> list:
    """Invariante DURO: todo registro é um tipo penal com sanção cominada.

    Um registro sem pena privativa E sem sanções próprias (ex.: uma nota de
    referência) não é um tipo penal: com pena zero ele satisfaria qualquer teto e
    contaminaria as estatísticas de alcance dos atributos.

    A exceção legítima é o tipo penal cujas sanções não são privativas de
    liberdade — art. 28 da Lei 11.343/06 —, que declara `sancoes_nao_privativas`.

    A segunda exceção é o tipo que NÃO COMINA moldura própria porque importa a
    de outro dispositivo — art. 304 do CP ("pena cominada à falsificação"), art.
    315 do CPM, arts. 2º e 3º da Lei 2.889/56. Ele declara `pena_por_remissao`.
    Sem esse estado, a moldura vazia era indistinguível de campo não preenchido,
    e a alternativa — publicar a moldura de um dos dispositivos-fonte — afirmava
    como certa uma pena que depende de qual falsificação foi usada.
    """
    problemas = []
    for c in crimes:
        nome = c.get("crime") or ""
        if NAO_TIPIFICA.search(nome):
            problemas.append(
                f"id={c.get('id')} ({c.get('lei')} {c.get('artigo')}): "
                f"não é tipo penal — {nome[:60]}"
            )
            continue
        tem_pena = bool(c.get("pena_max") or c.get("pena_min"))
        tem_sancao = bool(c.get("sancoes_nao_privativas"))
        # Tipo que comina SÓ multa (multa isolada) é sanção válida — ex.: o caput
        # do art. 146-A (bullying), "Pena: multa, se não constitui crime mais grave".
        tem_multa_isolada = c.get("tipo_pena") == "Multa"
        tem_remissao = bool(c.get("pena_por_remissao"))
        if not tem_pena and not tem_sancao and not tem_multa_isolada and not tem_remissao:
            problemas.append(
                f"id={c.get('id')} ({c.get('lei')} {c.get('artigo')}): sem pena cominada, sem "
                f"`sancoes_nao_privativas` e sem multa — se for tipo penal, declare a sanção; se não, remova"
            )
    return problemas


def validar_pena_por_remissao(crimes: list) -> list:
    """Quem importa a moldura de outro dispositivo tem de dizer DE ONDE.

    O estado só é honesto se disser o dispositivo-fonte: sem ele, `pena_min` e
    `pena_max` zerados voltam a ser indistinguíveis de campo não preenchido — que
    é exatamente o defeito que o campo existe para eliminar. E quem declara
    remissão não pode publicar moldura própria: seriam duas respostas para a
    mesma pergunta.
    """
    problemas = []
    for c in crimes:
        rem = c.get("pena_por_remissao")
        if rem is None:
            continue
        if not isinstance(rem, dict) or not (rem.get("dispositivo_fonte") or "").strip():
            problemas.append(
                f"id {c['id']}: `pena_por_remissao` sem `dispositivo_fonte` — "
                "diga de qual dispositivo a moldura vem")
            continue
        if rem.get("operador") not in OPERADORES_REMISSAO:
            problemas.append(
                f"id {c['id']}: operador {rem.get('operador')!r} inválido — "
                f"use um de {sorted(OPERADORES_REMISSAO)}")
        if rem.get("operador") != "nenhum" and not rem.get("fracao"):
            problemas.append(
                f"id {c['id']}: operador {rem.get('operador')!r} exige `fracao`")
        # `dispositivo_fonte` é prosa e não dá para navegar. `lei_fonte` +
        # `artigos_fonte` são o que a tela usa para listar os dispositivos que
        # carregam a moldura — sem eles o usuário fica sem para onde ir, já que
        # o simulador não é oferecido nestes registros.
        alvos = [x for x in crimes
                 if x.get("lei") == rem.get("lei_fonte")
                 and any((x.get("artigo") or "").startswith(a)
                         for a in rem.get("artigos_fonte") or [])]
        if not rem.get("lei_fonte") or not rem.get("artigos_fonte"):
            problemas.append(
                f"id {c['id']}: `pena_por_remissao` sem `lei_fonte`/`artigos_fonte` "
                "— declare os dispositivos de origem, senão a tela não tem para "
                "onde mandar quem consulta")
        elif not alvos:
            problemas.append(
                f"id {c['id']}: `artigos_fonte` {rem['artigos_fonte']} não casa "
                f"nenhum registro de {rem['lei_fonte']!r} — remissão para o vazio")
        elif any(not (x.get("pena_max") or x.get("pena_min")) for x in alvos
                 if not x.get("pena_por_remissao")):
            problemas.append(
                f"id {c['id']}: alguma origem de `pena_por_remissao` não tem moldura "
                "própria — a remissão tem de chegar a uma pena")
        if c.get("pena_min") or c.get("pena_max"):
            problemas.append(
                f"id {c['id']}: declara `pena_por_remissao` E moldura própria "
                f"({c.get('pena_min')}-{c.get('pena_max')}) — só uma das duas")
    return problemas


def validar_vigencia(crimes: list) -> list:
    """Dispositivo que deixou de vigorar precisa dizer O QUE ACONTECEU.

    `vigencia_ate` sozinho é pior que nada: o registro sai do ar sem explicar por
    quê, e quem consulta um fato anterior não sabe se ainda pode se apoiar nele.
    A nota tem de trazer o motivo e, quando houver, o dispositivo que passa a
    reger a conduta.
    """
    problemas = []
    for c in crimes:
        ate = c.get("vigencia_ate")
        if ate and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(ate)):
            problemas.append(
                f"id {c['id']}: `vigencia_ate` = {ate!r} não é uma data AAAA-MM-DD")
        if ate and not (c.get("vigencia_nota") or "").strip():
            problemas.append(
                f"id {c['id']}: declara `vigencia_ate` sem `vigencia_nota` — um "
                "registro que deixou de vigorar tem de dizer o que houve e qual "
                "dispositivo passa a reger a conduta")
        if c.get("vigencia_nota") and not ate:
            problemas.append(
                f"id {c['id']}: tem `vigencia_nota` sem `vigencia_ate` — se o "
                "dispositivo continua vigente, a nota é `obs`")
    return problemas


def validar_condicionais(crimes: list) -> list:
    """Classificação circunstanciada não pode ser afirmada como se fosse do tipo.

    Um registro que declara `hediondo_condicao` está dizendo "depende do caso" —
    e marcar `hediondo: "Sim"` ao lado disso afirmaria o que a lei não afirma,
    além de ligar sozinho as vedações do art. 5º, XLIII, da Constituição.

    Desde 23/09/2026 o mesmo vale para `violencia_condicao`, criado pela decisão
    8. A condição existe porque o tipo se consuma SEM violência: o sequestro
    pode ser obtido por fraude, a resistência por ameaça que não é grave. Marcar
    "Sim" ao lado da condição retiraria ANPP (CPP, art. 28-A) e substituição
    (CP, art. 44, I) de quem tem direito a elas — que é exatamente o dano que a
    revisão fina foi corrigir.
    """
    problemas = []
    for c in crimes:
        if c.get("hediondo_condicao") and c.get("hediondo") == "Sim":
            problemas.append(
                f"id {c['id']}: declara `hediondo_condicao` e ainda assim marca "
                "`hediondo: Sim` — a condição existe justamente porque o tipo, "
                "sozinho, não decide")
        if c.get("violencia_condicao") and c.get("violencia") == "Sim":
            problemas.append(
                f"id {c['id']}: declara `violencia_condicao` e ainda assim marca "
                "`violencia: Sim` — a condição existe justamente porque o tipo "
                "se consuma sem violência")
    return problemas


def validar_elemento_e_tentativa(crimes: list) -> list:
    """A régua do elemento subjetivo decide a tentativa (decisões 20 e 31).

    Escrita em 23/09/2026, depois de o campo passar anos sem critério:

    - **Preterdoloso** — a lei exclui o dolo no resultado (CP 129, §3º; CPM 209,
      §3º-A), ou o resultado doloso configura outro crime, tratado em concurso.
      Não admite tentativa: não se tenta o que só se produz culposamente.
    - **Qualificado pelo resultado** — o tipo abriga resultado doloso OU culposo,
      num crime só (latrocínio, STF Súmula 610; estupro com resultado, NUCCI,
      22. ed., p. 665-666). Admite tentativa.
    - **Culposo** — não admite tentativa (CP, art. 14, II).
    - **Doloso** — a régua não decide; o campo é lido do tipo.

    É trava, e não convenção, porque a distinção entre as duas primeiras foi o
    trabalho da decisão 31: deixá-la só no texto seria perdê-la no primeiro
    registro novo.
    """
    problemas = []
    for c in crimes:
        elemento, tentativa = c.get("elemento"), c.get("tentativa")
        if elemento in ("Preterdoloso", "Culposo") and tentativa == "Sim":
            problemas.append(
                f"id {c['id']} ({c.get('lei')} {c.get('artigo')}): elemento "
                f"{elemento!r} com `tentativa: Sim` — não se tenta o resultado "
                "que a lei não quer doloso (decisões 20 e 31)")
        if elemento == "Qualificado pelo resultado" and tentativa == "Não":
            problemas.append(
                f"id {c['id']} ({c.get('lei')} {c.get('artigo')}): elemento "
                "'Qualificado pelo resultado' com `tentativa: Não` — o tipo "
                "abriga resultado doloso, e o dolo se tenta (decisões 20 e 31)")
    return problemas


def validar_ids(crimes: list) -> list:
    """Invariantes DUROS do identificador. Nunca são débito tolerável.

    O `id` é a URL pública de cada tipo penal (`/pesquisa/tipos?tipo=N`) e o site
    está publicado. Ele é APPEND-ONLY: um id novo vai para o fim (max + 1) e um id
    existente jamais é reatribuído a outro dispositivo, sob pena de um link antigo
    passar a apontar para o crime errado — falha silenciosa e difícil de notar.

    Importa sobretudo a partir da v2.0.0, quando o crawler do DOU passa a propor
    inclusões automáticas no catálogo.
    """
    problemas = []
    ids = [c.get("id") for c in crimes]

    sem_id = [i for i, v in enumerate(ids) if v is None]
    if sem_id:
        problemas.append(f"{len(sem_id)} registro(s) sem `id` (posições {sem_id[:5]})")

    repetidos = sorted(i for i, n in Counter(ids).items() if n > 1 and i is not None)
    if repetidos:
        problemas.append(
            f"{len(repetidos)} `id` repetido(s): {repetidos[:10]} — cada id é uma URL pública"
        )

    nao_inteiros = [v for v in ids if v is not None and not isinstance(v, int)]
    if nao_inteiros:
        problemas.append(f"{len(nao_inteiros)} `id` não inteiro(s): {nao_inteiros[:5]}")

    # id APOSENTADO nunca volta. A regra "próximo id = max + 1" tem um furo: se
    # a remoção foi no topo da numeração, o max cai e o id seguinte reaproveita
    # um endereço que já significou outro crime. Aconteceu na v1.4.0, quando 15
    # ids do fim saíram de uma vez.
    reusados = sorted(set(ids) & ids_aposentados())
    if reusados:
        problemas.append(
            f"{len(reusados)} `id` reaproveitado(s) de registro já retirado: "
            f"{reusados[:10]} — ver data/ids-aposentados.json")

    return problemas


def ids_aposentados() -> set[int]:
    """ids que já foram URL pública e saíram do catálogo (data/ids-aposentados.json)."""
    if not APOSENTADOS.exists():
        return set()
    registro = json.loads(APOSENTADOS.read_text(encoding="utf-8"))
    return {i for grupo in registro.get("aposentados", []) for i in grupo["ids"]}


def proximo_id(crimes: list) -> int:
    """O próximo id livre: acima de tudo que existe E de tudo que já existiu."""
    return max({c["id"] for c in crimes if isinstance(c.get("id"), int)}
               | ids_aposentados()) + 1


def validar_grafia_artigo(crimes: list) -> list:
    """Grafia canônica do dispositivo (débito técnico 4, fechado em 25/09/2026).

    Em 23/09/2026, 37 registros escreviam `§ 2º` com espaço contra 375 sem, e a
    exclusão que tirava a forma culposa do art. 273 do CP do rol de hediondos
    nunca casou — um erro jurídico escondido por meses por uma variação de
    grafia. A grafia foi normalizada; esta validação impede que a variação
    volte: o que a régua não lê reprova aqui, com a mensagem do que corrigir.
    """
    problemas = []
    for c in crimes:
        for defeito in problemas_de_grafia(c.get("artigo") or ""):
            problemas.append(
                f"id={c.get('id')} ({c.get('lei')} {c.get('artigo')!r}): grafia do artigo — {defeito}")
    return problemas


# A URN LexML de cada diploma é a chave que liga `data/fontes.json` ao Senado e
# ao normas.leg.br (plano de fontes abertas, F2). Errada, ela não quebra: aponta
# para OUTRA norma, e o Cotejador passa a comparar o CP com a lei errada.
_URN = re.compile(r"^urn:lex:br:federal:[a-z]+(?:\.[a-z]+)*:\d{4}-\d{2}-\d{2};\d+$")


def validar_fontes(caminho=FONTES) -> list:
    """Cada diploma de `data/fontes.json` com uma URN bem formada, e só uma vez."""
    fontes = json.loads(caminho.read_text(encoding="utf-8"))["fontes"]
    problemas = []
    vistas = Counter(f.get("urn") for f in fontes)
    for f in fontes:
        urn = f.get("urn")
        if not urn:
            problemas.append(f"fontes.json: {f['id']} sem `urn`")
        elif not _URN.match(urn):
            problemas.append(f"fontes.json: {f['id']} com `urn` malformada: {urn!r}")
        elif vistas[urn] > 1:
            problemas.append(f"fontes.json: {f['id']} repete a `urn` {urn} de outro diploma")
    return problemas


def validar_tudo(crimes: list, tabela_hediondez: dict) -> list:
    """Todos os invariantes, na ordem em que o construtor sempre os rodou.

    A ordem importa só para quem lê o stderr: os erros saem agrupados por
    validação, e a do `id` vem primeiro porque é a que ninguém pode ignorar.
    """
    # Invariantes estruturais: falham sempre, independentemente de --estrito.
    return (validar_ids(crimes) + validar_tipos_penais(crimes)
            + validar_vocabulario(crimes)
            + validar_hediondez(crimes, tabela_hediondez)
            + validar_moldura(crimes) + validar_condicionais(crimes)
            + validar_elemento_e_tentativa(crimes)
            + validar_vigencia(crimes)
            + validar_pena_por_remissao(crimes)
            + validar_grafia_artigo(crimes)
            + validar_fontes())
