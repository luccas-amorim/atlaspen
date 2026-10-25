---
id: catalogo-tipos-penais
title: Catálogo de tipos penais
description: Como o catálogo é construído — os dois arquivos, as regras que decidem o que entra, e o que a CI impede de regredir.
sidebar_position: 2
---

# Catálogo de tipos penais

O catálogo é a base factual do AtlasPen: é dele que saem as penas cominadas, a hediondez,
a violência e as demais características que alimentam o cálculo dos atributos penais. Esta
página descreve **como ele é construído e como sua qualidade é garantida**. O significado de
cada campo, para quem vai consumir os dados, está em [Dados abertos](./dados-abertos.md); os
princípios que decidem o que ele afirma e o que cala, em [Metodologia](./metodologia.md).

## Os dois arquivos

O catálogo existe em duas formas, e a distinção importa para quem for contribuir:

| Arquivo | Papel | Quem edita |
| --- | --- | --- |
| `data/crimes.json` | **Fonte da verdade.** Campos redigidos à mão. | Pessoas (inclusive pela interface web do GitHub) |
| `static/data/crimes.json` | **Derivado.** Fonte + campos calculados. É o único que a aplicação lê. | `scripts/transform_data.py` |

Nunca edite `static/data/crimes.json`: ele é sobrescrito. O workflow
`.github/workflows/regen-data.yml` observa `data/crimes.json`, roda a transformação e
commita o resultado — não é preciso ter Python instalado para contribuir. Ele regenera
também o derivado dos atributos, cujo alcance depende das penas do catálogo.

```
data/crimes.json  ──►  scripts/transform_data.py  ──►  static/data/crimes.json
   (fonte, à mão)          (deriva + audita)              (consumido pelo site)
                                   │
                                   └──►  static/data/qualidade.json  (relatório)
```

## O que há num registro

Cada registro tem três grupos de campos, e o grupo diz quem responde por ele:

- **Fonte** — o que uma pessoa escreveu conferindo o compilado: dispositivo, nome, moldura
  em meses, espécie de pena, ação penal, hediondez, elemento subjetivo, tentativa, violência
  e grave ameaça, e os campos condicionais que guardam a hipótese quando a lei não decide
  pelo tipo.
- **Derivado** — o que o transformador calcula a cada build: rótulos de pena, menor
  potencial ofensivo, contravenção, multa, hediondez pela tabela curada, remissão de pena,
  duplicatas, vigência.
- **Conferência** — a trilha de auditoria escrita pela rodada semanal: contra qual página
  o registro foi conferido, quando e com que resultado.

O dicionário completo, campo a campo, é a seção
[Para que serve cada campo](./dados-abertos.md#para-que-serve-cada-campo) de Dados abertos.
Três decisões de modelagem, porém, moldaram o catálogo a ponto de merecer explicação aqui.

### `tem_pena_privativa` — e por que o catálogo só tem tipos penais

Até a v1.1.0 (numeração do protótipo; ver
[Estabilidade e versionamento](./dados-abertos.md#estabilidade-e-versionamento)) o catálogo
carregava, além dos tipos penais, **notas de referência e dispositivos sem pena própria**:
`REFERÊNCIA — A LGPD não tipifica crimes`, `CP, Art. 141, I` (causa de aumento),
`CP, Art. 171, §5º` (regra de ação penal), `CP, Art. 128` (excludente de ilicitude). Eram 21
registros com pena zero.

Com pena zero, eles **satisfaziam qualquer teto de pena** e eram contados como "cabíveis"
em transação penal, ANPP e sursis — inflando o alcance desses atributos. A transação
reportava 325 tipos cabíveis; o correto era 303.

Foram removidos, e a regra passou a ser **imposta** pelo transformador: um registro que não
declare pena nem sanção falha o build (convenção C1, no `CONTRIBUTING.md`).

Sobram duas distinções legítimas.

A primeira é o **tipo penal que não comina prisão**. O exemplo mais claro é o art. 28 da
Lei 11.343/06 (porte para consumo), cujas sanções são as do art. 28, I a III — advertência,
prestação de serviços e medida educativa; a maior parte dos demais são contravenções
punidas só com multa, como o art. 32 da LCP (dirigir sem habilitação). São tipos penais,
ficam no catálogo, declaram `sancoes_nao_privativas` ou `tipo_pena: "Multa"` e recebem
`tem_pena_privativa: false`, que os mantém fora das estatísticas de alcance (que se medem
por patamar de pena) sem excluí-los da consulta.

A segunda é o **tipo que não comina moldura própria porque importa a de outro
dispositivo**. O art. 304 do Código Penal pune o uso de documento falso com "a pena
cominada à falsificação", e a moldura depende de qual dos arts. 297 a 302 foi usado — as
faixas vão de detenção de um mês a reclusão de seis anos. Esses registros declaram
`pena_por_remissao`, e o motor os avalia com a moldura de cada dispositivo de origem: o
veredito é o comum às origens, ou "depende" quando elas divergem. Por isso entram nas
estatísticas de alcance (decisão de 19/09/2026). A exceção é a remissão que o catálogo já
desdobra em registros "c/c" — a Lei 2.889/56, arts. 2º e 3º, desdobrada nas alíneas do
art. 1º —: ali os desdobrados contam, e o guarda-chuva não, para o mesmo crime não contar
duas vezes. A alternativa que o catálogo praticava — publicar a moldura de um dos
dispositivos-fonte — afirmava como certa uma pena que depende do caso.

:::note[Majorantes com pena própria são exibidas]
As causas de aumento que constituem um **dispositivo com pena própria** — como o roubo
majorado (art. 157, §2º) — são tipos do catálogo e aparecem normalmente na busca. O que
não entra é a causa de aumento **abstrata**, que só diz "aumenta-se de 1/3" sobre a pena
de *outro* crime, sem patamar próprio (ex.: art. 141, aumento nos crimes contra a honra):
como registro de pena zero, ela distorceria as estatísticas de alcance. Essas majorantes
abstratas são modeladas como **entidade própria**, em `data/modificadores.json`, e
aplicadas na 3ª fase da dosimetria (art. 68, CP).
:::

### `resultado_morte` — por que só o nome do tipo

A regex roda **apenas contra o nome do tipo**, nunca contra `obs`. O campo `obs` costuma
descrever a pena de *outros parágrafos* do mesmo artigo ("se resulta morte, triplica"), o
que produziria falsos positivos em tipos cujo caput não é qualificado pela morte — como o
art. 135 (omissão de socorro), o art. 267 (epidemia dolosa) e o art. 270 (envenenamento).

O campo importa porque o art. 112, VI e VIII, da LEP reserva as frações mais altas de
progressão ao condenado por **crime hediondo com resultado morte**, e o art. 122, §2º, lhe
veda a saída temporária.

### `perdao_judicial_previsto` — por que uma lista curada

Não existe perdão judicial genérico: ele só incide **onde a lei o prevê expressamente** e
**não se estende por analogia**. Por isso o campo não é inferido do elemento culposo, e sim
de uma lista de dispositivos mantida em `PERDAO_JUDICIAL`, em `scripts/catalogo/tabelas.py`. Onde
a lei restringe o perdão à modalidade culposa, a regra exige `elemento == "Culposo"` — o
art. 121, §4º, por exemplo, tem uma 1ª parte culposa e uma 2ª parte dolosa, e só a
primeira o admite.

## Garantias de qualidade

A cada regeneração, o script emite `static/data/qualidade.json` com o estado do catálogo
(e o total de atributos penais, contado de `data/atributos.json`), e a CI o valida antes
de qualquer publicação.

Os números vivos ficam em duas páginas geradas, para não envelhecerem aqui:
[Completude](./completude.md) (quantos tipos, por diploma) e
[`/data/qualidade.json`](pathname:///data/qualidade.json) (o relatório completo, com os `id` de
cada pendência). O que esta página fixa são as **travas** — o que a CI impede de regredir:

| Trava | O que impede |
| --- | --- |
| Contradições internas | Dois registros do mesmo dispositivo com pena ou hediondez divergente. Hoje zero; qualquer uma nova falha o build. |
| Registro sem pena declarada | Todo tipo declara pena ou sanção (C1, C2). |
| `id` reaproveitado | A URL pública nunca aponta para outro crime (C3). |
| Hediondez sem regra | Hediondez afirmada sem entrada na tabela curada reprova. |
| Grafia do dispositivo | O campo `artigo` segue uma forma canônica (`Art. 121, §2º, I`): grafia que a régua não lê reprova, em vez de casar regra nenhuma em silêncio. |
| Derivado dessincronizado | O `static/data/crimes.json` commitado tem de ser o que a fonte produz. |
| URN do diploma | Cada diploma de `data/fontes.json` tem a sua URN LexML, bem formada e de um diploma só. É ela que liga o diploma ao registro do Senado e ao normas.leg.br, que os robôs leem para perguntar se o compilado está em dia; URN errada apontaria para outra norma sem quebrar nada. |
| Divergência com o compilado | Não é trava de build: é achado da rodada semanal, e vira issue. O estado de cada registro está em [`/data/conferencia.json`](pathname:///data/conferencia.json). |

### Contradições: zeradas e travadas

Uma contradição interna ocorreria se dois registros do mesmo dispositivo (`lei + artigo`)
divergissem em pena ou hediondez. **Não há nenhuma** — todas foram conferidas contra o
texto compilado do Planalto. O transformador as classificava em três tipos (`pena`,
`identidade`, `hediondez`) por um **coeficiente de sobreposição** de vocabulário, e esse
classificador segue ativo como guarda: a CI roda
`transform_data.py --estrito --max-contradicoes=0` e **falha se uma nova contradição
entrar**. O catálogo não pode regredir.

### O que a CI garante a cada mudança

- **Só tipos penais** (convenção C1): notas de referência, agravantes e excludentes não
  entram.
- **Toda sanção declarada** (C2) e **`id` append-only** (C3): a URL pública nunca aponta
  para o crime errado.
- **Zero contradições** (C4) e derivado sincronizado com a fonte.
- **Casos-âncora de direito penal** (`npm run verificar`): cada atributo avaliado contra o
  catálogo real, com os invariantes do motor.
- **Casos-padrão do motor** (`scripts/verificar_casos.ts`, no mesmo comando): afirmações
  com tipo real, premissa explícita, veredito esperado e o dispositivo que o sustenta —
  transação, ANPP, sursis, substituição, regime, progressão, livramento, prescrição,
  clemência e execução, nos quatro estados de reincidência. Tipo não encontrado é FALHA, e
  não caso pulado: uma tabela que se desliga sozinha não verifica nada. Foi ela que, em
  19/09/2026, mostrou que o reincidente genérico recebia a fração de progressão do primário.
- **Congelamento dos vereditos** (`npm run equivalencia`): todos os atributos × todos os
  tipos com pena privativa × quatro cenários (página do tipo, busca por atributo,
  reincidente em crime doloso e reincidente específico). Refatorar o motor sem mudar
  resposta nenhuma é o resultado esperado; mudança de veredito só passa se alguém regravar
  o congelamento e disser por quê.
- **Conferência semanal contra o Planalto** (`conferidor.yml`): pena, espécie, existência e
  situação de cada dispositivo, com a cobertura publicada no relatório — ver
  [Os robôs](./os-robos.md).

## Como corrigir um tipo penal

Achou um erro e não quer mexer em código? [Abra uma issue](https://github.com/luccas-amorim/atlaspen/issues)
com o dispositivo e o que o texto da lei diz. É contribuição das mais úteis, e é o caminho
que a maior parte de quem lê direito vai preferir.

Para corrigir diretamente:

1. Edite `data/crimes.json` — direto pela interface do GitHub, se preferir.
2. Abra um Pull Request descrevendo a fonte legal da correção.
3. A CI valida; ao integrar, o `regen-data` regenera o derivado automaticamente.

Correções finas que a heurística não acerta ficam em tabelas explícitas em
`scripts/catalogo/tabelas.py` (`CORRECOES`, `CORRECOES_MORTE`), com o motivo documentado —
assim a exceção sobrevive à próxima regeneração.
