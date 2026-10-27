# AtlasPen

<sub>O nome vem de Atlas, o Titã que sustenta o céu. [Por quê?](MITO.md)</sub>

**Atlas Penal Brasileiro dos Tipos, Atributos e Impacto Legislativo.** Uma base aberta com
**todos os tipos penais brasileiros em vigor** e os institutos que a lei liga a cada um —
ANPP, transação, substituição, progressão, livramento, prescrição e os demais —, com motor
de cálculo e simulação de alteração legislativa.

Todo tipo penal em vigor, de cada diploma que os comina — o número vivo, diploma a
diploma, está em [Completude](https://atlaspen.com.br/projeto/completude) —,
conferido contra o texto compilado do `planalto.gov.br`. Astro + React + TypeScript sobre
JSON versionado. Sem servidor, sem banco: tudo o que a ferramenta sabe é arquivo de texto
que você pode ler, conferir e corrigir por pull request.

> **Em pesquisa.** Os cálculos simplificam controvérsias doutrinárias e jurisprudenciais.
> **Não constituem aconselhamento jurídico.** O que o catálogo não sabe, ele diz que não
> sabe: nenhum campo é preenchido por plausibilidade.

---

## Para quem usa os dados

Os dados são abertos e estáveis. Você não precisa clonar nada.

| endereço | o que é |
|---|---|
| [`/data/crimes.json`](https://atlaspen.com.br/data/crimes.json) | o catálogo completo, um objeto por tipo penal |
| [`/data/atributos.json`](https://atlaspen.com.br/data/atributos.json) | os 22 atributos, com parâmetros, fundamento e o alcance sobre o catálogo |
| [`/data/qualidade.json`](https://atlaspen.com.br/data/qualidade.json) | o relatório de qualidade de cada geração |
| [`/data/changelog.json`](https://atlaspen.com.br/data/changelog.json) | o que mudou na lei, entrada a entrada |
| [`/data/atlaspen-base.xlsx`](https://atlaspen.com.br/data/atlaspen-base.xlsx) | a base inteira em planilha, assinada e datada: Leia-me, Tipos penais, Atributos e a matriz de alcance |

O contrato dos campos, a política de versionamento e a forma de citar estão em
[Dados abertos](https://atlaspen.com.br/projeto/dados-abertos). A planilha
também se baixa da própria lista de [tipos penais](https://atlaspen.com.br/tipos)
e do rodapé de qualquer página.

**Três coisas que evitam erro de leitura:**

- **`id` é a URL pública e nunca é reatribuído.** Um id que sai do catálogo vai para
  `data/ids-aposentados.json` e não volta a ser usado. A numeração foi reiniciada duas
  vezes, em 31/07 e 06/08/2026, por decisão registrada: id anterior a essas datas se refere
  a outro crime.
- **Pena em meses**, sempre, no campo canônico (`pena_min_meses`, `pena_max_meses`). Os
  rótulos legíveis vêm à parte.
- **Campo condicional não é campo vazio.** Quando a lei não decide pelo tipo —
  `hediondo_condicao`, `acao_condicao`, `violencia_condicao` —, o campo principal fica no
  valor seguro e a hipótese fica escrita ao lado, em texto. Ler só o campo principal e
  ignorar a condição é ler metade.

## O que a ferramenta faz

- **Tipos penais** (`/tipos`) — busca por nome, artigo, lei ou observações, com filtros
  combinados: modalidade de pena, hediondez, elemento subjetivo, violência e grave ameaça,
  ação penal, menor potencial ofensivo. Cada tipo tem ficha própria (`/tipos/{id}`), com a
  pena cominada, a pena concreta e o histórico do dispositivo.
- **Atributos penais** (`/atributos`) — cada instituto com ficha própria, **parâmetros
  editáveis** (mexa na fração da progressão e veja o alcance mudar) e o alcance sobre o
  catálogo em duas unidades: dispositivos e cenários.
- **Simulação legislativa** (`/simulacao`) — criar, modificar ou extinguir um tipo ou um
  atributo, em pacote, e medir o que entra, o que sai e o que não se move. O link é a
  hipótese; a nota sai em PDF, markdown e CSV.
- **Acervo histórico** (`/acervo`) — os tipos que saíram de vigência, com a linha do tempo
  da lei penal desde 1822.

## Arquitetura

### O caminho de um dado

```
texto compilado do Planalto          data/*.json              static/data/*.json
 (crawler/snapshots/, 48 MB,   ──▶    a FONTE, editável  ──▶   o DERIVADO, consumido
  fora do versionamento)              à mão e por PR            pelo site e pela API
                                           │
                                           └── scripts/transform_data.py
                                               (a linha de comando do pacote
                                                scripts/catalogo/: tabelas curadas,
                                                validações, derivações, duplicatas)
```

A separação **fonte × derivado** é a regra que mais quebra em silêncio se ignorada: quem
edita o derivado perde a edição na próxima geração, e quem testa contra a fonte testa o que
ninguém consome. O derivado é commitado, e a CI exige que esteja sincronizado.

| arquivo-fonte | o que guarda |
|---|---|
| `data/crimes.json` | o catálogo: um registro por tipo penal |
| `data/atributos.json` | os 22 atributos penais, com os parâmetros da lei e as redações de cada um |
| `data/historico-legislativo.json` | a vida de cada dispositivo: criação, alteração, revogação, com data de publicação e de vigência |
| `data/hediondos.json` | o rol do art. 1º da Lei 8.072/90 transcrito, contra o qual a hediondez de cada tipo é auditada |
| `data/modificadores.json` | agravantes, atenuantes e causas de aumento e diminuição que deslocam a moldura |
| `data/fontes.json` | os diplomas monitorados, com a URL do compilado, a URN LexML que os liga ao Senado e ao normas.leg.br, e a *sentinela* que prova o frescor da página |
| `data/avisos.json` | ADI em curso, tese de repercussão geral, divergência entre tribunais — com a data em que a fonte foi consultada |
| `data/conferencia.json` | a trilha: o que foi conferido contra o texto da lei, quando e por quem |
| `data/ids-aposentados.json` | os ids que já foram URL pública e saíram do catálogo |
| `data/acervo.json`, `data/marcos.json` | o acervo histórico e a linha do tempo da lei penal |
| `data/documentacao.json` | de que arquivos cada documento depende — é o que o Arquivista vigia |

### O motor de atributos

`src/lib/atributos/` recebe um **cenário** (pena, reincidência, violência, hediondez, data do
fato) e devolve, para cada atributo, **cabível / condicional / incabível**, com o fundamento
legal e o limiar que decidiu. As funções de avaliação ficam em `avaliadores/`, um módulo por
categoria — processual, aplicação da pena, execução —, e o que dois módulos precisam
aplicar de forma idêntica (a vedação do livramento pelo art. 112 da LEP, o art. 90-A da Lei
9.099/95) fica em `comum.ts`.

O cálculo é uma função pura por atributo e **lê os parâmetros dos dados** em vez de
constantes — é o que permite editar a fração da progressão na tela e ver o alcance mudar.
`src/lib/simulacao/` roda o mesmo motor sobre uma cópia do catálogo em memória: é assim que
a simulação mede o impacto de uma lei que ainda não existe.

**A data do fato escolhe a lei.** O art. 112 da LEP mudou duas vezes em 2026, em datas
diferentes — os hediondos em 25/03 e os comuns em 08/05 —, e um fato de abril cai na tabela
nova de uns e na antiga de outros. Os marcos ficam em `src/lib/tempo.ts`.

### Os robôs

Programas determinísticos, **sem inteligência artificial**, que leem a lei e comparam com o
catálogo. Nenhum deles escreve no catálogo: abrem issue ou imprimem relatório, e quem
decide assina. Documentação própria em [`scripts/robos/README.md`](scripts/robos/README.md)
e, para quem lê o site, em [Os robôs](https://atlaspen.com.br/projeto/os-robos).

| robô | o que faz |
|---|---|
| **Vigia** | confere a moldura de pena de cada registro contra o texto compilado |
| **Auditor** | confere hediondez, ação penal, violência e grave ameaça contra as regras escritas — e só aceita derivação cujo fundamento tenha lastro no texto lido |
| **Sentinela** | tria o Diário Oficial da semana atrás de lei que cria ou altera tipo penal |
| **Recenseador** | varre todas as leis do ano, para que nada passe entre uma semana e outra |
| **Arquivista** | acusa documento cuja dependência mudou depois da última releitura |
| **Cotejador** | pergunta a uma segunda fonte se o próprio compilado está em dia: as leis que o Senado registra, a moldura da compilação da Câmara, os vetos que ainda podem cair. Só pergunta |

O **Proponente** (`scripts/robos/proponente/`) não é robô: é quem transforma o que é
leitura direta em PR, com a nota de atualização quando a mudança vem de lei recente. O PR
é proposta, e merge é decisão de gente.

### O que impede o erro de entrar

A acuidade jurídica não se sustenta em cuidado: sustenta-se em trava. As que falham o build:

- **`transform_data.py --estrito`** — vocabulário fechado de cada campo, `id` append-only,
  hediondez afirmada sem regra que a produza, condição declarada ao lado de afirmação
  categórica, elemento subjetivo incompatível com a tentativa, e a **grafia canônica do
  dispositivo**: `§ 2º` com espaço já escondeu um erro jurídico por meses, porque a regra
  que excluía a forma culposa do art. 273 do CP do rol de hediondos nunca casou.
- **`hediondez.carregar()`** — recusa regra que não diga onde termina. Uma expressão sem
  âncora de fim fez `V` casar `VI`, `VII` e `VIII`, e quatro formas do roubo afirmaram
  hediondez que o rol não dá.
- **`npm run verificar`** — seis baterias, entre elas os casos-padrão em que a resposta
  correta está escrita à mão, com o dispositivo que a fundamenta.
- **`npm run equivalencia`** — congelamento de 22 atributos × todos os tipos com pena
  privativa × 4 cenários. Mudança de veredito só passa se for regravada de propósito, e o
  commit diz por quê.
- **`pytest scripts/robos/tests`** — centenas de testes, e cada um guarda um caso que já
  deu errado. Entre eles: o snapshot do Planalto só ocupa o caminho canônico depois de
  passar pela sentinela, e a derivação de violência ou ação penal cujo fundamento cite um
  trecho que o texto não tem é zerada.
- **`npm run mortos`** — `knip` varre arquivo que ninguém importa, exportação sem uso e
  dependência não listada. As exceções, com motivo, estão em `knip.jsonc`.

## Rodando o projeto

```bash
npm install
npm run dev          # servidor local com hot-reload
npm run build        # build de produção
npm run preview      # testar o build localmente
```

Regenerar os dados derivados, depois de editar a fonte:

```bash
python scripts/transform_data.py --estrito --max-contradicoes=0
npm run atributos    # grava static/data/atributos.json
```

A bateria completa de verificação, na ordem, está no [`AGENTS.md`](AGENTS.md) — o mesmo
arquivo que orienta agentes de IA que trabalham no repositório. Rode-a inteira antes de
abrir PR.

## Como contribuir

As convenções do catálogo (C1 a C8), o glossário e o passo a passo estão em
[`CONTRIBUTING.md`](CONTRIBUTING.md). O essencial:

1. **Nada entra sem conferência contra o texto compilado oficial** do `planalto.gov.br`. Um
   dado errado publicado é pior que um dado ausente.
2. **Nunca preencha lacuna com plausibilidade.** Se a lei não decide, o registro diz que não
   decide — é para isso que existem os campos de condição.
3. **Trabalhe em branch própria**, com commits pequenos que expliquem o *porquê*, não o *o
   quê*. O diff já diz o quê.
4. **Correção de dado não vira nota de atualização.** O feed publica alteração de LEI; erro
   antigo que a conferência achou é conserto, e o corpo do PR diz o motivo.

Achou um erro no catálogo e não quer mexer em código?
[Abra uma issue](https://github.com/luccas-amorim/atlaspen/issues) com o dispositivo e o que o
texto da lei diz. É contribuição das mais úteis.

## O que falta

### Módulos

Cada um com plano, financiamento e pessoas próprias. A ordem é de exequibilidade.

| | o que é |
|---|---|
| **Extinção da punibilidade pelo pagamento** | Os arts. 168-A e 337-A do CP extinguem a punibilidade de quem paga o tributo, e a LC 225/2026 tirou dessa regra o devedor contumaz inscrito no Cadin. O catálogo registra a alteração no histórico legislativo, mas o instituto **não é atributo modelado**: o motor só o conhece de raspão, no perdão judicial. Enquanto não for, alteração de lei sobre ele não vira nota de atualização — e é por isso que a LC 225 não tem entrada no feed. |
| **Quantas vezes cada registro mudou** | Um contador de atualizações por tipo e por atributo, para medir a instabilidade de cada área da lei penal. |
| **22 atributos mapeados e não integrados** | Estão levantados e fora do catálogo. Os fáceis entram juntos; a **prescrição completa** é empreitada do porte de um mestrado — as regras não são simples e há modulação no tempo. |
| **A cadeia completa do histórico** | Hoje cada tipo diz a *última* lei que lhe deu texto. O módulo completa: todas as redações, em ordem, para responder "o que este artigo dizia em 2014?". É o que falta para a data do fato escolher também o TEXTO, e não só o cálculo. |
| **Acervo histórico** | O que já foi crime no Brasil: revogados, alterados e não recepcionados. A pergunta "o que deixou de ser crime, e quando?" não tem hoje ferramenta que a responda de forma estruturada. |
| **Robô dos tribunais** | Desde 25/10/2026 o **Relator** (`scripts/robos/relator/`) lê toda semana, no Banco Nacional de Precedentes do CNJ, os precedentes do STF (ADI, ADPF, ADC, ADO, repercussão geral, súmulas e súmulas vinculantes) e do STJ (súmulas, repetitivos e IAC), e aponta os que tocam diploma vigiado, registro do catálogo ou atributo penal. Falta o resto: o STM (que julga os registros do CPM, e de quem o banco não tem nada), o acórdão comum e o que o banco do CNJ não guarda. Metade do caminho já existe fora daqui: o `decidendo-ghoul`, lido em 24/09/2026, traz um cliente da API pública do CNJ (DataJud) com paginação por `search_after` e cache por página, e um leitor dos espelhos do STJ que resolve o formato hostil do campo `jurisprudenciaCitada`. Quando a frente abrir, começar dali. A ressalva, que é dele: o STF bloqueia acesso automatizado por WAF, e o DataJud não tem texto, só metadados — para ADI, o DataJud por número CNJ; para súmula e precedente, os espelhos do STJ. |
| **Curador** | Desde 26/10/2026 o **Curador** (`scripts/robos/curador/`) lê, no ctresb/leis, toda lei ordinária, decreto-lei e lei complementar desde 1889, aponta as que cominam pena e que o projeto não conhece, e o Planalto confirma; o estado fica em `data/curadoria.json`. A varredura única apontou 209 — 59 com pena de prisão vigente, 40 revogadas —, e foram lidas até 26/10/2026: oito tipos entraram no catálogo, os diplomas revogados entraram no acervo, inclusive os que só o normas.leg.br guarda, e o que pede juízo virou issue com o rótulo `questão jurídica`. Em 26/10/2026 o `curador/lexml.py --decretos` leu no normas.leg.br os 8.193 decretos com força de lei dos governos provisórios (1889–1891, 1930–1934), que o ctresb não tem: 45 trazem pena privativa no texto, 15 entraram no acervo em 27/10/2026, e os uniformes militares de 1931 e a Lei do Serviço Militar de 1933 viraram issue. Os outros que seguem no estado são, em geral, regulamentos com pena disciplinar ou atos que só mencionam a pena. Seguem em aberto as penas de transição da Lei de Introdução do CP (DL 3.914/1941, arts. 2º a 6º) e um decreto de 1932 que não respondeu na varredura. |
| **Usabilidade, processo penal, plataforma de pesquisa** | Ganhos de uso, extensão ao que rege os atributos na prática, e exportação para pesquisa empírica. |

### Dívida técnica

Não há dívida técnica declarada em aberto. As oito que este README carregava foram
fechadas em 25/09/2026 (o histórico do repositório conta cada uma); a próxima que aparecer
vira issue com o rótulo `dívida técnica`, e volta a ser listada aqui só se ficar meses sem
dono — porque dívida não declarada vira surpresa.

## Documentação

Publicada no próprio site, em [`/projeto`](https://atlaspen.com.br/projeto).
Os documentos: Metodologia (os princípios), Catálogo de tipos penais (construção e travas),
Atributos penais, Progressão de regime (o art. 112 da LEP, o dispositivo mais instável do
catálogo), Completude (gerada), Dados abertos (o dicionário de campos, o único lugar em que
cada campo é definido) e Os robôs. Os textos: a História do projeto, Autoria e créditos e o
Manifesto pelo termo "atributo".

A árvore de `docs/` **espelha a do site**, e `docs/` é, sem exceção, o que vai ao ar:
`docs/*.md` é o grupo *Documentação* da barra lateral, `docs/textos/` é o grupo *Textos*.
O que existe só no repositório fica fora dele: os documentos de operação ficam na raiz
([`AGENTS.md`](AGENTS.md), [`TRIAGEM.md`](TRIAGEM.md), [`AUDITORIA.md`](AUDITORIA.md)) e os
planos e specs do desenvolvimento em `.superpowers/`, que é diretório de ferramenta, como
`.github/`.

## Autoria

O AtlasPen é desenvolvido pela **Equipe AtlasPen**. Quem faz o quê — desenvolvimento,
pesquisa e colaboração acadêmica — está em
[Autoria e créditos](https://atlaspen.com.br/projeto/creditos).

O projeto tem como **antecedente de pesquisa** o SISPENAS, concebido em 2008 pelas
professoras **Maíra Rocha Machado** e **Marta Rodriguez de Assis Machado** (Direito GV/FGV),
em pesquisa vinculada a edital da Secretaria de Assuntos Legislativos do Ministério da
Justiça. A intuição de cruzar tipos e atributos penais, e de medir o efeito de uma mudança
legislativa sobre o conjunto, vem de lá:

> MACHADO, Maíra Rocha; MACHADO, Marta Rodriguez de Assis (coord.). **SISPENAS: Sistema de
> Consulta sobre Crimes, Penas e Alternativas à Prisão**. Revista Jurídica, Brasília, v. 10,
> n. 90, ed. esp., p. 1-26, abr./maio 2008. (Íntegra em
> [`static/artigos/`](./static/artigos/machado-machado-2008-sispenas-rev-juridica-90.pdf).)

O AtlasPen é obra nova, escrita para a lei vigente. A história completa está em
[O projeto](https://atlaspen.com.br/projeto).

## Licença

Duas licenças, uma para cada coisa:

- **Código:** [Apache 2.0](./LICENSE).
- **Dados e textos:** [CC BY 4.0](./LICENSE-CC-BY-4.0). Isso abrange a base (`data/`,
  `static/data/` e a planilha), a documentação do site (`docs/`) e as notas de atualização.

As duas permitem usar, copiar, modificar e redistribuir, inclusive comercialmente, e as
duas pedem o mesmo: dar crédito a *AtlasPen, da Equipe AtlasPen*, indicar a fonte e
sinalizar as mudanças que fizer. No código, o crédito está no [`NOTICE`](./NOTICE), que a
Apache 2.0 manda manter (seção 4).

Citar o AtlasPen como fonte é livre, e é o que as duas licenças pedem. O que elas não dão é
o direito de apresentar o nome ou o símbolo do AtlasPen como seus, nem de sugerir que o
projeto apoia ou endossa um trabalho de terceiros. A marca está em processo de registro no
INPI. O que não está sob nenhuma das duas licenças, o artigo de 2008 e os textos de lei,
está listado no `NOTICE`.

A forma de citar em trabalho acadêmico está em
[Dados abertos](https://atlaspen.com.br/projeto/dados-abertos#como-citar), e o
`CITATION.cff` traz a mesma informação em formato que o GitHub e os gerenciadores de
referência leem.
