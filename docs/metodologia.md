---
id: metodologia
title: Metodologia
description: A unidade de análise, o que o catálogo afirma e o que deliberadamente cala, de onde vem cada dado e como os atributos são calculados.
sidebar_position: 2
---

# Metodologia

Esta página diz como o AtlasPen decide o que entra na base, o que cada registro pode
afirmar e como os atributos são calculados a partir dele. É a página dos princípios. O
detalhe de cada campo está em [Dados abertos](./dados-abertos.md); como o catálogo é construído
e travado, em [Catálogo de tipos penais](./catalogo-tipos-penais.md); por que falamos em
*atributos*, e não em *benefícios*, no [Manifesto pelo termo "atributo"](/projeto/manifesto-atributo).

## Unidade de análise: o tipo penal

A unidade de análise é o **tipo penal**: cada conduta com cominação de pena própria. Isso
inclui a forma simples e as qualificadas, as privilegiadas, as culposas e cada inciso ou
alínea que gere pena autônoma. Um artigo do Código Penal pode render um registro ou uma
dezena; o que conta é a moldura, não o número do artigo.

Não são tipos penais, e não entram como registro: a causa de aumento abstrata ("aumenta-se
de um terço"), que só faz sentido sobre a pena de outro crime e é modelada à parte, em
`data/modificadores.json`; a regra de ação penal; a excludente de ilicitude; a nota de
referência. Já esteve tudo isso no catálogo, distorcendo as estatísticas de alcance, e a
história de como saiu está contada no [Catálogo de tipos penais](./catalogo-tipos-penais.md#tem_pena_privativa--e-por-que-o-catálogo-só-tem-tipos-penais).

Quantos diplomas e quantos tipos o catálogo cobre hoje, e quanto de cada um já foi
conferido, está em [Completude](./completude.md) — número vivo não mora em prosa.

## Três compromissos

**Descrever, não avaliar.** O catálogo registra o que a lei liga a cada tipo: a pena, a
espécie de ação penal, a hediondez, o que cabe e o que não cabe em termos de substituição,
suspensão, progressão, prescrição. Não diz se isso é bom ou ruim. A palavra que escolhemos
para esse conjunto de consequências, *atributo*, foi escolhida por ser neutra, e o
[Manifesto](/projeto/manifesto-atributo) explica a escolha.

**Dizer o que se sabe e calar o que não se sabe.** Nenhum campo é preenchido por
plausibilidade. Quando a lei não decide pelo tipo — quando a classificação depende do que
aconteceu no caso —, o registro não escolhe: fica no valor seguro e escreve a hipótese ao
lado. É para isso que existem os campos condicionais, e eles são o coração do método:

- `hediondo_condicao`: o homicídio simples só é hediondo se praticado em atividade típica
  de grupo de extermínio. `hediondo` fica em "Não"; a hipótese fica em texto.
- `acao_condicao`: o exercício arbitrário das próprias razões só é de ação privada se não
  houver violência. `acao` fica na regra; a exceção fica em texto.
- `violencia_condicao`: sequestrar não pressupõe violência, porque a privação da liberdade
  pode ser obtida por fraude. Aqui o motor vai além: calcula os atributos nas duas hipóteses
  e mostra as duas.

Três outros campos têm a mesma função em outra dimensão. `hediondo_nota` registra
divergência de **jurisprudência ou de doutrina**, não circunstância do caso: o tipo não
muda conforme o que aconteceu, muda conforme quem julga. `vigencia_ate`, sempre com
`vigencia_nota`, registra a data em que o dispositivo deixou de vigorar sem tirá-lo do
catálogo, porque fato anterior continua regido por ele. E `pena_por_remissao` diz de onde
a moldura vem quando o tipo não comina uma — o art. 304 do Código Penal pune o uso de
documento falso com "a pena cominada à falsificação", e qual é ela depende de qual
falsificação foi usada; o catálogo não a inventa.

Ler só o campo principal e ignorar a condição é ler metade do registro. Quem consome os
dados precisa saber disso, e [Dados abertos](./dados-abertos.md) repete o aviso.

**A fonte é o texto compilado.** Uma lei penal quase nunca nasce sozinha: altera outra. Por
isso a fonte do catálogo não é o texto de cada lei no dia em que foi publicada, e sim o
**texto compilado** do `planalto.gov.br`, que traz a redação em vigor e, ao lado de cada
dispositivo, a nota de quem o incluiu, alterou ou revogou. Cada registro diz contra qual
página foi conferido e quando. Desde outubro de 2026, os robôs perguntam também a outras
fontes oficiais — o registro do Senado e a compilação da Câmara — se o próprio compilado
está em dia; elas apontam onde olhar e nunca escrevem no catálogo. Como isso é feito, toda
semana, está em [Os robôs](./os-robos.md).

## Quatro camadas de dado

O que a tela mostra passa por quatro camadas, e saber em qual delas um dado nasce diz o
que ele vale e onde se corrige.

| Camada | O que é | Quem produz | Onde está descrita |
| --- | --- | --- | --- |
| **Fonte** | Os campos redigidos à mão, um registro por tipo penal, em `data/crimes.json` | Pessoas, conferindo contra o compilado | [Catálogo de tipos penais](./catalogo-tipos-penais.md) |
| **Derivado** | Os campos calculados a partir da fonte — rótulos de pena, menor potencial ofensivo, contravenção, hediondez pela tabela curada, duplicatas | `scripts/transform_data.py`, a cada build | [Dados abertos](./dados-abertos.md#derivados--recalculados-a-cada-build-não-edite) |
| **Conferência** | A trilha de auditoria de cada registro: contra qual página, quando, com que resultado | Os robôs, toda segunda-feira | [Os robôs](./os-robos.md) |
| **Cálculo** | O veredito de cada atributo sobre cada tipo, num cenário dado | O motor de atributos, em tempo real na tela | [Atributos penais](./atributos-penais.md) |

A separação entre fonte e derivado é a que mais importa para quem contribui: quem edita o
derivado perde a edição na próxima geração. A separação entre derivado e cálculo é a que
mais importa para quem consome: o derivado é um arquivo publicado e estável; o cálculo
depende do cenário e muda quando o cenário muda.

:::note[Multa é uma dimensão independente]
No direito penal brasileiro a multa é, na maioria dos casos, **cumulada** com a pena
privativa ("reclusão de 1 a 4 anos, **e multa**"). Por isso ela é modelada como dimensão
independente (`tem_multa`, `multa_regime`), e não como alternativa a reclusão ou detenção.
Consequência prática: filtrar por "Reclusão" retorna também os tipos com reclusão e multa;
para ver só os que têm multa, combine os dois filtros.
:::

## Cálculo dos atributos

Cada atributo é avaliado por uma **função pura** sobre um *cenário*: a pena em abstrato, a
pena concreta e as características do caso que a lei manda considerar — reincidência,
violência ou grave ameaça, hediondez, resultado morte, data do fato. A função devolve, para
cada atributo, **cabível**, **condicional** ou **incabível**, com o fundamento legal e o
limiar que decidiu.

Dois traços do cálculo decorrem do método:

- **Os patamares são dados, não código.** Frações, prazos e tetos ficam em
  `data/atributos.json`, cada um com o dispositivo, a lei que lhe deu a redação e o valor
  anterior quando o número mudou. É isso que permite alterar um patamar na tela e ver o
  alcance sobre o catálogo mudar — e é isso que permite a
  [simulação legislativa](/simulacao).
- **A data do fato escolhe a lei.** Quando um dispositivo teve duas redações em vigor no
  mesmo ano, o motor aplica a que regia o fato, e a retroatividade da lei mais benéfica é
  apurada por situação, não em bloco. O caso concreto é o art. 112 da LEP, tratado em
  [Progressão de regime](./progressao-de-regime.md).

Quando o direito não tem resposta única — duas leituras sustentáveis de um mesmo inciso,
uma ADI pendente —, o motor não escolhe: devolve *condicional* e escreve as leituras. A
implementação é para fins de pesquisa, simplifica controvérsias doutrinárias e
jurisprudenciais, e não constitui aconselhamento jurídico. A lista dos atributos, com o
critério de cada um, está em [Atributos penais](./atributos-penais.md).
