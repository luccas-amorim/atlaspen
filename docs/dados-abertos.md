---
id: dados-abertos
title: Dados abertos
description: Cada campo do registro, o formato dos dados, de onde vem cada dado e como ele é revisado, a licença de uso e como citar.
sidebar_position: 4
---

# Dados abertos

O catálogo completo é publicado como dado aberto em formato JSON:

- **Tipos penais:** [`/data/crimes.json`](pathname:///data/crimes.json) — um objeto por tipo penal.
- **Atributos penais:** [`/data/atributos.json`](pathname:///data/atributos.json) — os 22, com
  parâmetros, fundamento e alcance (ver [Atributos penais](#atributos-penais), abaixo).
- **Trilha de conferência:** [`/data/conferencia.json`](pathname:///data/conferencia.json) — contra
  qual página, quando e com que resultado cada registro foi conferido.
- **Relatório de qualidade:** [`/data/qualidade.json`](pathname:///data/qualidade.json) — contagens,
  lacunas conhecidas e contradições, a cada geração.
- **Licença:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — cite como
  **EQUIPE ATLASPEN. AtlasPen** (ver [Como citar](#como-citar)). O código que gera a base
  está sob [Apache 2.0](https://github.com/luccas-amorim/atlaspen/blob/main/LICENSE).

Esta página é o **dicionário**: o lugar único em que cada campo é definido. Os princípios
que decidem o que um campo pode afirmar estão em [Metodologia](./metodologia.md); como o
catálogo é construído e travado, em [Catálogo de tipos penais](./catalogo-tipos-penais.md).

### A base inteira em planilha

Para quem trabalha em Excel, LibreOffice ou Planilhas Google, a mesma base sai também em
uma planilha assinada:

> **[Baixar `atlaspen-base.xlsx`](pathname:///data/atlaspen-base.xlsx)**

Quatro abas: **Leia-me** (versão, data de geração, commit de origem, licença, como citar e
as armadilhas de leitura), **Tipos penais** (um registro por linha, com a URL pública de
cada um), **Atributos** (os 22, com fundamento, parâmetros e alcance) e **Matriz de
alcance** (os tipos com pena privativa × os 22 atributos, no cenário padrão).

Ela é **derivada e datada**: sai a cada publicação a partir destes mesmos JSON, sempre no
mesmo endereço — a nova substitui a anterior, e não há duas no ar ao mesmo tempo. Por isso
a aba Leia-me traz a data e o commit: planilha baixada é uma fotografia, e citar uma
fotografia sem dizer quando ela foi tirada é citar o que já mudou. Editá-la não altera a
base; o caminho de correção continua sendo uma issue ou um pull request.

## Três coisas que evitam erro de leitura

Antes do dicionário, o que mais custa a quem lê os dados pela primeira vez:

- **`id` é a URL pública e nunca é reatribuído.** Um id que sai do catálogo vai para
  `data/ids-aposentados.json` e não volta a ser usado. A numeração foi reiniciada duas
  vezes, em 31/07 e 06/08/2026 (versões 1.4.0 e 2.0.0 do protótipo), por decisão
  registrada: id anterior a essas datas se refere a outro crime.
- **Pena em meses**, sempre, no campo canônico (`pena_min_meses`, `pena_max_meses`). O mês
  do art. 11 do Código Penal tem 30 dias, então 0,5 são 15 dias. Os rótulos legíveis vêm à
  parte.
- **Campo condicional não é campo vazio.** Quando a lei não decide pelo tipo —
  `hediondo_condicao`, `acao_condicao`, `violencia_condicao` —, o campo principal fica no
  valor seguro e a hipótese fica escrita ao lado, em texto. Ler só o campo principal e
  ignorar a condição é ler metade.

## Esquema de cada registro

O registro de `id: 1`, tal como está publicado em `/data/crimes.json`. O primeiro bloco é a
fonte redigida à mão; o segundo, os derivados que `scripts/transform_data.py` calcula a
cada build; o terceiro, a trilha escrita pela rodada semanal de conferência.

```json
{
  "id": 1,
  "lei": "CP",
  "artigo": "Art. 121, caput",
  "crime": "Homicídio simples",
  "pena_min": 72,
  "pena_max": 240,
  "tipo_pena": "Reclusão",
  "acao": "Pública Incondicionada",
  "hediondo": "Não",
  "hediondo_condicao": "Hediondo somente quando praticado em atividade típica de grupo de extermínio, ainda que por um só agente. Fundamento: Lei 8.072, art. 1º, I.",
  "hediondo_nota": null,
  "elemento": "Doloso",
  "tentativa": "Sim",
  "violencia": "Sim",
  "grave_ameaca": "Não",
  "violencia_condicao": null,
  "pena_por_remissao": null,
  "sancoes_nao_privativas": [],
  "obs": "Matar alguém. 6-20 anos reclusão",

  "pena_min_meses": 72.0,
  "pena_max_meses": 240.0,
  "pena_min_rotulo": "6 anos",
  "pena_max_rotulo": "20 anos",
  "pena_faixa_rotulo": "6 a 20 anos",
  "pena_privativa": "Reclusão",
  "tem_pena_privativa": true,
  "tem_multa": false,
  "multa_regime": "nenhuma",
  "infracao_menor_potencial": false,
  "contravencao": false,
  "resultado_morte": true,
  "resultado_morte_derivado": true,
  "perdao_judicial_previsto": false,
  "hediondo_especie": "nao",
  "hediondo_fundamento": null,
  "hediondo_condicional": true,
  "acao_condicional": false,
  "violencia_condicional": false,
  "vigente": true,
  "avisos": null,
  "chave_dispositivo": "cp|art. 121, caput",
  "dispositivo_canonico": "cp|art. 121, caput",
  "ultima_alteracao": null,
  "alteracoes_legislativas": 0,
  "duplicata": false,
  "duplicata_divergente": false,
  "duplicata_ids": [],
  "derivado_auto": true,

  "fonte": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm",
  "conferido_em": "2026-09-21",
  "conferido_resultado": "conferido"
}
```

## Para que serve cada campo

Nem todo campo tem o mesmo peso: alguns definem o que o sistema responde, outros apenas
descrevem. As tabelas abaixo dizem **o que cada um é e onde é usado**, para quem for
reaproveitar os dados saber o que pode mudar sem quebrar uma conta.

### Fonte — redigida à mão, conferida contra o compilado

| Campo | O que é e onde é usado |
| --- | --- |
| `id` | Identificador estável; endereço público do tipo (`/tipos/N`; as URLs antigas, `/pesquisa/tipos?tipo=N`, levam a ele). **Nunca é reatribuído.** |
| `lei`, `artigo` | Identificam o dispositivo (`CP`, `Art. 121, §2º, I`). Juntos formam a `chave_dispositivo`, que detecta registro repetido, e ligam a linha ao texto oficial conferido toda semana. A grafia de `artigo` segue uma forma canônica, validada na entrada. |
| `crime` | Nome do tipo penal, exibido na busca. É dele — **e não do `obs`** — que se deduz o `resultado_morte`. |
| `pena_min`, `pena_max` | **A moldura**, em meses. Alimentam toda a dosimetria e todos os atributos com limiar de pena. Zerados **de propósito** quando há `pena_por_remissao`. |
| `tipo_pena` | `Reclusão`, `Detenção`, `Prisão simples`, `Multa`, `Morte` (só nos crimes militares de tempo de guerra, CPM, art. 56), `Outras penas` (sanção cominada que não é privativa nem pecuniária) ou `—`. Define o regime inicial e distingue o tipo sem pena privativa. |
| `acao` | Espécie de ação penal, em vocabulário fechado desde 19/09/2026: `Pública Incondicionada`, `Pública Condicionada à Representação`, `Pública Condicionada à Requisição`, `Ação Penal Privada` e `Ação Penal Privada Personalíssima` (CP, art. 236, parágrafo único). Condiciona os institutos que dependem de representação ou de queixa. |
| `acao_condicao` | Opcional. Quando a espécie de ação depende do caso (art. 161, §3º: privada se a propriedade é particular), aqui fica a hipótese, em texto, e `acao` fica na regra. |
| `hediondo` | `Sim` / `Não` — inclui os **equiparados** (tráfico, tortura, terrorismo). Fecha indulto, graça e comutação, e endurece as frações de progressão e livramento condicional. Vem acompanhado dos derivados `hediondo_especie` e `hediondo_fundamento`. |
| `hediondo_condicao` | Opcional. Quando a hediondez depende do **caso** — o homicídio só é hediondo se praticado em atividade de grupo de extermínio —, aqui fica a hipótese, em texto, e `hediondo` permanece `Não`. |
| `hediondo_nota` | Opcional. Divergência de **jurisprudência ou doutrina** sobre a hediondez — não circunstância do caso. O tipo não muda conforme o que aconteceu; muda conforme quem julga. |
| `elemento` | `Doloso`, `Culposo` ou `Preterdoloso`. Crime culposo admite substituição por restritiva qualquer que seja a pena, e não admite tentativa. |
| `tentativa` | O tipo admite tentativa? Habilita a redução do art. 14, II, na terceira fase da dosimetria. |
| `violencia`, `grave_ameaca` | Elementares que vedam substituição por restritivas, ANPP e arrependimento posterior. Não têm fonte textual que as declare: são qualificações do tipo, revisadas à mão. |
| `violencia_condicao` | Opcional. Quando a violência depende do caso (sequestro: a privação da liberdade pode ser obtida por fraude), aqui fica a hipótese; `violencia` fica em `Não`, e o motor calcula e mostra as duas hipóteses. |
| `pena_por_remissao` | Opcional. O tipo **não comina moldura própria**: importa a de outro dispositivo. `{dispositivo_fonte, lei_fonte, artigos_fonte, operador, fracao}` — o art. 304 do CP ("a pena cominada à falsificação"), o art. 315 do CPM. Incompatível com `pena_min`/`pena_max`. O operador segue a dosimetria: `diminuicao` com `1/3` multiplica a moldura de origem por 2/3; `aumento`, por 4/3. O motor avalia o tipo com a moldura de cada origem, e o veredito é o comum às origens, ou "depende" quando divergem. |
| `sancoes_nao_privativas` | Opcional. As sanções de um tipo que não comina prisão (art. 28 da Lei 11.343/06: advertência, prestação de serviços, medida educativa). Deriva `tem_pena_privativa: false`. |
| `vigencia_ate`, `vigencia_nota` | Opcionais. Data (AAAA-MM-DD) em que o dispositivo deixou de vigorar e o que houve — revogação, declaração de inconstitucionalidade — com o dispositivo que passa a reger a conduta. **A nota é obrigatória quando há a data**: um registro que sai do ar sem dizer por quê é pior que um registro errado. O registro **não sai do catálogo**: fato anterior continua regido por ele. |
| `obs` | **Descritivo.** Observação de leitura humana — origem da redação, formas do artigo, remissões. Não define a pena; o que dele ainda se extrai é a presença e o regime da multa. |

### Derivados — recalculados a cada build, não edite

| Campo | Para que existe |
| --- | --- |
| `pena_min_meses`, `pena_max_meses` | Moldura canônica para cálculo. Cópia de `pena_min`/`pena_max`, que são a autoridade. A unidade real da pena é o **dia**: o art. 11 do CP manda **desprezar** as frações de dia — desprezar, não arredondar, porque arredondar para cima agravaria a pena sem lei. |
| `pena_min_rotulo`, `pena_max_rotulo`, `pena_faixa_rotulo` | Exibição na unidade natural: "15 dias a 3 meses", "2 a 5 anos", "até 5 anos". |
| `pena_privativa` | `Reclusão`, `Detenção`, `Prisão simples` ou `Nenhuma`, mapeado de `tipo_pena` — `Multa`, `Morte` e `Outras penas` viram `Nenhuma`, porque não são pena de prisão. |
| `tem_pena_privativa` | O tipo comina prisão, própria ou por remissão? Se não, declara `sancoes_nao_privativas`, ou é o guarda-chuva de uma remissão desdobrada em registros "c/c". Quem tem `false` fica fora das estatísticas de alcance sem sair da consulta. |
| `tem_multa`, `multa_regime` | Multa `cumulativa`, `alternativa`, `isolada` ou `nenhuma`, lida dos conectores do `obs` (`e multa` → cumulativa; `ou multa` → alternativa). |
| `infracao_menor_potencial` | Porta de entrada da Lei 9.099/95 (art. 61): a contravenção, qualquer que seja a pena, e o crime com pena máxima até dois anos ou só com multa. Nunca o crime militar (art. 90-A); sempre o porte para consumo do art. 28 da Lei 11.343/06 (art. 48, §1º). |
| `contravencao` | Pena de prisão simples (LICP, art. 1º), ou registro da LCP ou da Lei 7.437/85, que declaram contravenção tudo o que tipificam. |
| `resultado_morte`, `resultado_morte_derivado` | Marcam o tipo com morte como resultado (art. 112, VI e VIII, LEP; art. 122, §2º). Regex sobre o **nome** do crime, nunca sobre `obs`; o segundo campo avisa que veio da heurística, sem revisão manual. |
| `perdao_judicial_previsto` | Só `true` nas hipóteses expressamente previstas em lei (art. 107, IX, CP), de uma lista curada — não há perdão judicial genérico. |
| `hediondo_especie`, `hediondo_fundamento` | **Não é heurística**: casamento com a tabela curada `data/hediondos.json`. `natureza` (rol do art. 1º da Lei 8.072/90, taxativo), `equiparado` (art. 5º, XLIII, da CF — o crime responde como hediondo sem o ser) ou `nao`, mais o dispositivo que produz a classificação. Hediondez afirmada sem regra na tabela reprova na CI. |
| `hediondo_condicional`, `acao_condicional`, `violencia_condicional` | `true` quando a fonte trouxe a condição correspondente. A interface mostra a hipótese; o campo principal está no padrão seguro. |
| `vigente` | `false` quando o registro declara `vigencia_ate`. Deriva da presença do campo, não de uma comparação com a data de hoje: um campo que virasse sozinho num dia qualquer quebraria o build sem ninguém ter tocado em nada. |
| `avisos` | Os avisos de `data/avisos.json` que alcançam o registro — ADI em curso, tese de repercussão geral, divergência entre tribunais —, cada um com a fonte e a data em que ela foi consultada. Não mudam o cálculo: dizem que a **norma está em disputa**. `null` quando nenhum o alcança. |
| `chave_dispositivo`, `duplicata`, `duplicata_divergente`, `duplicata_ids`, `duplicata_tipo` | Detecção de registro repetido. `duplicata_divergente` marcaria o mesmo dispositivo com penas conflitantes (`duplicata_tipo`: `pena`, `identidade` ou `hediondez`); a CI trava em zero. |
| `dispositivo_canonico` | A chave canônica do dispositivo (`cp\|art. 121, §2º, i`), a mesma do histórico legislativo e de `data/fontes.json`. O dispositivo é o primeiro citado no `artigo`: o "c/c" diz de onde vem a pena, não onde o tipo está. |
| `ultima_alteracao`, `alteracoes_legislativas` | Do histórico legislativo, pela mesma regra dos atributos: a lei que por último deu texto ao dispositivo (norma, ano, evento e link para o artigo da lei alteradora) e **quantas leis** mexeram nele. `0` é a redação original; `null` é "não se sabe": o compilado não anota quem deu o texto daquela unidade. |
| `derivado_auto` | Marca o registro cujos campos passaram por preenchimento automático. |

### Conferência — escrita pela rodada semanal

| Campo | Para que existe |
| --- | --- |
| `fonte` | A página do texto compilado contra a qual este registro é conferido. |
| `conferido_em` | Data da última conferência deste registro contra a lei (AAAA-MM-DD). |
| `conferido_resultado` | `conferido` (a moldura bate), `sem_moldura_na_lei` (o dispositivo não traz moldura própria: pena por referência ou sanção não privativa), `divergente` (virou achado) ou `dispensado` (exceção já julgada). |

Registro recém-criado, ainda não alcançado por uma rodada, tem os três campos nulos — o
que também é uma informação. A trilha vive em
[`/data/conferencia.json`](pathname:///data/conferencia.json), fora do catálogo editado à mão.

## Atributos penais

Os 22 atributos penais também são dado aberto:

- [`/data/atributos.json`](pathname:///data/atributos.json) é o **derivado**, gerado por
  `scripts/derivar_atributos.ts`: a base dos atributos mais o que dela se calcula;
- `data/atributos.json` e `data/historico-legislativo.json`, no repositório, são as
  **fontes**.

| Campo | Para que existe |
| --- | --- |
| `id` | Número estável e append-only, como o `id` dos tipos penais. |
| `slug` | O identificador das URLs do site (`?atributo=transacao`). |
| `nome`, `fundamento`, `categoria`, `natureza`, `descricao`, `requisitos`, `vedacoes` | O instituto, como a página [Atributos penais](./atributos-penais.md) o descreve. |
| `dispositivos` | Os dispositivos em que o atributo se funda, em chave canônica (abaixo). |
| `parametros` | Cada patamar, fração ou vedação, com o valor padrão (lei vigente) e as `redacoes`: a `fonte` (dispositivo, súmula ou decisão), a `norma` que deu a redação e o `fundamento` exibido. `valor` só aparece quando uma redação antiga dava outro número. `norma: null` quer dizer que o compilado não anota aquela unidade, e a base não a data. `sem_fonte_legal` marca o parâmetro de simulação, sem lei que o fixe. |
| `ultima_alteracao`, `alteracoes_legislativas` | **Derivados**, no atributo e em cada parâmetro. O evento legislativo mais recente nos dispositivos citados e quantos houve depois do texto original. `null` é "não se sabe". |
| `alcance` | **Derivado.** Os `id` dos tipos penais com pena privativa em que o atributo é `cabivel` e `condicional`, com os parâmetros no padrão e sob o cenário de referência declarado no próprio arquivo (pena concreta igual à mínima cominada, réu primário). Incabível é o resto. |

A **chave canônica** de um dispositivo é o `id` do diploma em `data/fontes.json`, uma
barra vertical e o dispositivo em minúsculas: `lep|art. 112, vi, c` é a alínea "c" do
inciso VI do art. 112 da LEP. Chave sem vírgula é o artigo inteiro.

O **histórico legislativo** é uma tabela, com uma linha por acontecimento na vida de um
dispositivo (`criacao`, `alteracao`, `revogacao`, `renumeracao`, `transferencia`): a
norma, o ano, a anotação tal como está no compilado e o link. As linhas de origem
`compilado` são extraídas por `scripts/robos/nucleo/historico.py`; as de origem `manual`
são preservadas quando ele roda de novo.

## De onde vem cada registro, e como ele é revisado

Um dado errado publicado é pior que um dado ausente. Quem cita o dado precisa saber o que
foi conferido, por quem, e o que não foi.

**A fonte é o texto compilado, não a lei publicada no dia.** Uma lei penal quase nunca
nasce sozinha: ela altera outra. Por isso a fonte do catálogo é o **texto compilado** do
`planalto.gov.br` — a versão que o próprio governo mantém atualizada, com a redação em
vigor no corpo do artigo e, ao lado de cada dispositivo, a nota de quem o incluiu, alterou
ou revogou. Ler o compilado é o que permite responder "qual é a pena **hoje**" sem
reconstruir a história da norma emenda por emenda.

**Toda segunda-feira, de madrugada, o repositório repete sozinho a conferência.** Baixa a
página compilada de cada diploma, decompõe cada página em dispositivos, confronta a pena
lida com a publicada no catálogo e reporta o que divergiu numa issue pública. Quando a
divergência é de leitura direta — a moldura de um registro que já existe não corresponde
ao que a lei comina —, abre também um pull request com a correção proposta. Na mesma
rodada, outros programas vigiam o que a conferência de penas não alcança: o Diário Oficial,
atrás de lei penal nova; a hediondez e a ação penal; a própria documentação; e, desde
outubro de 2026, o próprio compilado, perguntando ao registro do Senado e à compilação da
Câmara se ele anota as leis recentes e se a pena dele é a mesma. Cada um, com
seus critérios e seus limites, está descrito em [Os robôs](./os-robos.md) — e essa é a página a
ler antes de citar um dado, porque é lá que está escrito o que a máquina não vê.

Nada disso usa inteligência artificial. É comparação de texto: as mesmas regras, aplicadas
do mesmo jeito, toda semana — e por isso qualquer pessoa pode repetir a rodada e obter o
mesmo resultado.

**A máquina nunca publica sozinha.** O pull request é uma proposta e depende de aprovação
humana, e o alcance dela é deliberadamente estreito: corrigir a pena de um registro
existente. Criar um registro novo, remover um registro ou reclassificar um dispositivo
continua sendo decisão de gente, porque exige julgamento jurídico — o mesmo texto pode ser
um crime autônomo, uma causa de aumento da pena de outro crime, ou nem uma coisa nem
outra. Quando a leitura automática não é segura, o achado vira pergunta na triagem da
semana, não dado publicado.

### O que ainda não é conferido automaticamente

Honestidade sobre o alcance, para quem for citar:

- a conferência automática cobre **pena, espécie de pena, existência e situação** do
  dispositivo;
- **hediondez** é comparada com o rol do art. 1º da Lei 8.072/1990, e **ação penal** com as
  fórmulas escritas no próprio artigo — mas onde a lei condiciona a classificação a
  circunstância do caso, a máquina não decide nem propõe;
- **causas de aumento** e **nome do tipo** só geram lista para leitura humana: modelar um
  aumento exige decidir sobre quais tipos ele incide, e comparar nomes é heurística;
- **tentativa, violência e grave ameaça** não têm fonte textual que os declare — são
  qualificações do tipo, revisadas à mão;
- **decisão de tribunal superior** que altere o catálogo — uma ADI que retira dispositivo
  do ordenamento — não passa pelo Diário Oficial. Desde 25/10/2026 o Relator lê a do STF
  e a do STJ no Banco Nacional de Precedentes do CNJ, que é oficial e incompleto, e só
  aponta: o registro muda depois de lido o acórdão. A do STM nenhum robô vê;
- o [relatório de qualidade](pathname:///data/qualidade.json) publica, a cada build, as
  contradições conhecidas e os `id` envolvidos.

## Reprodutibilidade

Os campos derivados são gerados por `scripts/transform_data.py` a partir de
`data/crimes.json` (fonte), escrevendo o catálogo enriquecido em
`static/data/crimes.json`. O processo é determinístico: a mesma fonte produz sempre o mesmo
derivado, e a CI falha se o derivado commitado divergir da fonte. O derivado dos atributos
sai depois, de `scripts/derivar_atributos.ts` (`npm run atributos`), com a mesma exigência.

## Estabilidade e versionamento

O AtlasPen segue o [Semantic Versioning 2.0.0](https://semver.org/lang/pt-BR/) —
`MAIOR.MENOR.CORREÇÃO` — com uma leitura explícita do que cada posição significa **neste
projeto**. Sem essa convenção, "v2.1" e "v3.0" viram apenas rótulos de ordem.

Dois públicos dependem de estabilidade, e são eles que definem a **API pública** para
efeito de versionamento:

1. quem consome os **dados abertos** (`static/data/crimes.json`) e os cita em pesquisa;
2. quem referencia **URLs** (`/tipos/N`; as antigas, `/pesquisa/tipos?tipo=N`, levam a
   elas) em artigos e pareceres.

| Posição | Incrementa quando | Exemplos |
| --- | --- | --- |
| **MAIOR** (`X.0.0`) | **Salto na natureza do produto**: reestruturação funcional, arquitetural ou procedimental — o sistema passa a fazer algo de outra ordem, não apenas mais do mesmo. Ou quebra do contrato dos dados abertos ou das URLs. | Deixar de ser um catálogo mantido à mão e passar a ser conferido sozinho contra a fonte oficial; reiniciar a numeração dos `id`. |
| **MENOR** (`X.Y.0`) | O que já existe, com **acréscimos, alterações e remoções** de registros e telas — a natureza do produto permanece. | Acrescentar campo ao JSON, nova tela, novo atributo; incluir ou remover tipos penais. |
| **CORREÇÃO** (`X.Y.Z`) | Correção sem funcionalidade nova: erro de dosimetria, dado errado no catálogo, defeito de interface. | Corrigir a pena de um artigo; ajustar contraste. |

Nos dados abertos, isso quer dizer: acrescentar campo é MENOR; remover ou ressignificar
campo é MAIOR.

:::note[Correção de dado é CORREÇÃO, não MENOR]
Resolver uma contradição do catálogo muda o resultado de uma consulta — mas corrige um
erro, não acrescenta capacidade. Vai em `X.Y.Z`. Já **acrescentar um campo** que não
existia (`resultado_morte`) é `MENOR`, ainda que motivado por um erro: consumidores do JSON
ganham informação sem perder nenhuma.
:::

**Até o lançamento oficial, o projeto está em `0.x`** (desde 11/09/2026). Pelo próprio
semver, a versão 0 é desenvolvimento inicial: dados e URLs podem mudar sem aviso. As
versões de 1.0.0 a 2.0.6 que aparecem no histórico do repositório — e que a documentação
cita ao contar a história de uma regra — foram a numeração do **protótipo**; a v1.0.0 será
o lançamento oficial, com domínio próprio, e é a partir dela que esta regra vale. Os
próximos passos estão no
[README](https://github.com/luccas-amorim/atlaspen/blob/main/README.md#o-que-falta).

## Como citar

A base é uma fotografia que muda: a citação diz qual.

> EQUIPE ATLASPEN. *AtlasPen — Atlas Penal Brasileiro dos Tipos, Atributos e Impacto
> Legislativo*. Versão [versão], dados conferidos em [data da conferência]. 2026.
> Disponível em: <https://atlaspen.com.br/>. Acesso em: [data].

A versão e a data da última conferência estão no rodapé de cada página e na aba Leia-me da
planilha. A autoria é coletiva, e é a mesma que o `NOTICE` exige e o `CITATION.cff`
declara; quem faz o quê está em [Autoria e créditos](/projeto/creditos).

A pesquisa de 2008, que é o antecedente do AtlasPen, cita-se à parte:

> MACHADO, Maíra Rocha; MACHADO, Marta Rodriguez de Assis (coord.). SISPENAS: Sistema de
> Consulta sobre Crimes, Penas e Alternativas à Prisão. *Revista Jurídica*, Brasília,
> v. 10, n. 90, ed. esp., p. 1-26, abr./maio 2008.
