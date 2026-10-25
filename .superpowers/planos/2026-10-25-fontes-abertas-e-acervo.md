# Fontes abertas, o Cotejador e o acervo — plano

25/10/2026. Decisões tomadas no mesmo dia (fim do documento); nada implementado ainda.

## Por que agora

Três coisas apareceram juntas:

1. **A API de Dados Abertos do Senado** registra, norma por norma, quem alterou qual
   dispositivo, e lista as leis de cada ano. É JSON e é oficial.
2. **A API pública do normas.leg.br** (LexML, Congresso) serve o texto **original** de
   cada norma ao lado do vigente, sob CC BY 4.0.
3. **O repositório `ctresb/leis`** mostra como se monta uma coleta em escala com essas
   duas fontes, e traz código reaproveitável.

Juntas, elas dão ao conferidor o que ele não tem: uma **segunda leitura independente**
do Planalto. Hoje, se o Planalto atrasa ou erra, ninguém percebe.

## O que foi medido (25/10/2026)

| Fonte | Achado | Consequência |
|---|---|---|
| Senado, `legislacao/LEI/7210/1984` | a última alteração registrada da LEP é a Lei 15.410, igual à nossa sentinela | dá para cotejar frescor por diploma |
| Senado, `legislacao/lista?tipo=LEI&ano=2026` | 204 leis, da 15.322 à 15.526 (29/09); nenhuma depois disso | ou não houve lei, ou o Senado anda semanas atrás: **soma** ao Planalto, não o substitui |
| Senado, CP | a Lei 11.106/2005 revogou os arts. 217, 219 a 222 e 240, e o Senado classifica as seis como **"Alteração"** | a classificação do Senado não decide nada; ela aponta onde olhar |
| Senado, CP e LCP | não registra revogação dos arts. 185, 279 e 281 do CP nem dos arts. 27 e 69 da LCP, que o compilado mostra | o Senado não é completo para mudanças antigas |
| Nossos snapshots do Planalto | 431 dispositivos marcados como revogados nos 68 diplomas (CP 37, LCP 9), contando os não penais | **o maior ganho para o acervo está no dado que já temos**; ele tem 14 registros |
| normas.leg.br, CP | versões `Original` (DOU de 31/12/1940) e `Current`; sem intermediárias | serve o texto original; não serve para a história de patamares |
| normas.leg.br × `data/acervo.json` | art. 240, §2º: nós temos "dentro de 1 (um) mês", o original de 1940 diz "dentro de um mês" | é o tipo de divergência que só uma segunda fonte levanta; quem decide é o DOU |
| `ctresb/leis` | 10 dias de vida, operado por agentes de IA, só a redação vigente, MIT | fonte de **código e de ideias**, não de dado |

## Princípios

1. **O compilado do Planalto continua sendo a única fonte que escreve no catálogo.**
   Senado, normas.leg.br e ctresb **apontam**: abrem aviso, pergunta ou PR que pede
   juízo. É a regra do `AGENTS.md` estendida às fontes novas, e o motivo é o que a
   medição mostrou: o Senado errou a classificação de seis revogações do CP.
2. **Evoluir, não reescrever.** São 16 mil linhas e 19 arquivos de teste, com
   fixture para cada armadilha que já custou caro (texto citado, sufixo de letra,
   codificação). Uma reescrita joga fora essa memória. A mudança é de **arquitetura**:
   uma camada de fontes com a mesma interface, por baixo dos robôs que já existem.
3. **Copiar do ctresb com critério.** O código é MIT: compatível com a nossa Apache-2.0,
   desde que o aviso de copyright vá junto do trecho copiado. Nunca copiar o
   `errors="replace"` da decodificação: ele corrompe em silêncio, que é exatamente o
   que o `baixar.py` existe para impedir.
4. **Cada fonte nova entra com fixture e teste sem rede**, como as atuais.

## A arquitetura

```
scripts/robos/
  fontes/                 NOVO: um adaptador por fonte
    rede.py               limite de taxa, novas tentativas, gzip, cache (de ctresb/comum.py)
    planalto.py           o atual nucleo/baixar.py: sentinela, .part, decodificação estrita
    senado.py             legislacao/{tipo}/{n}/{ano}, legislacao/lista, legislacao/urn
    normas.py             normas.leg.br: versão Original e Current por URN
    dou.py                a coleta que hoje mora dentro do dou_watcher
    ctresb.py             leitura do repositório, com SHA fixado
  cotejador/              NOVO robô: compara fontes, nunca escreve
    frescor.py            sentinela × última alteração no Senado
    textos.py             moldura no Planalto × moldura no normas.leg.br
    historico.py          historico-legislativo.json × registros do Senado
  nucleo/                 fica: parsear, historico, vigencia, revogacao, fracao...
  vigia/ auditor/ proponente/ sentinela/ recenseador/ arquivista/   ficam
  acervo/                 NOVO: gera os candidatos do acervo a partir do compilado
```

**O que muda em cada módulo existente:**

| Módulo | Hoje | Depois |
|---|---|---|
| `nucleo/baixar.py` | baixa do Planalto com urllib próprio | vira `fontes/planalto.py`, sobre `rede.py`; o comportamento não muda |
| `recenseador/leis_do_ano.py` | lê só a lista do Planalto, e em agosto não conseguiu | junta a lista do Planalto com a do Senado e diz qual leu |
| `sentinela/dou_watcher.py` | coleta e triagem juntas | a coleta sai para `fontes/dou.py`; a triagem ganha, de graça, a lista de diplomas que cada lei nova altera |
| `inventario_diplomas.py` | 974 linhas, com download próprio | passa a usar `fontes/planalto.py` |
| `data/fontes.json` | `id`, `url`, `sentinela`, `rotulos` | ganha `urn` (LexML): a chave única para o Senado e o normas.leg.br |

Nada é removido na primeira leva.

## As fases

Cada fase fecha com a verificação completa do `AGENTS.md` verde e um PR próprio.

### F0. Decisões (de quem assina)

Fechada em 25/10/2026: ver "Decisões", no fim.

### F1. A camada de rede

- `fontes/rede.py`: `Limitador` e `Rede` adaptados de `ctresb/scripts/comum.py`, com
  o aviso MIT; cache gzip em `crawler/cache/`, fora do git.
- Migrar `baixar.py`, `leis_do_ano.py`, `dou_watcher.py` e `inventario_diplomas.py`
  para ela. A decodificação continua a nossa.
- **Pronto quando:** os testes atuais passam sem nenhuma mudança e o ensaio de sexta
  baixa os 68 compilados como antes.
- Tamanho: médio. Risco: baixo, se nenhum teste for editado para passar.

### F2. Os clientes do Senado e do normas.leg.br

- `fontes/senado.py`: detalhe por tipo, número e ano ou por URN; lista por ano.
  Devolve dataclasses, não o JSON cru.
- **Tradutor de notação**: `Art. 66, caput, Inciso 5, Alínea j` → `Art. 66, V, j`,
  com a régua de `dispositivo_canonico.py`. Os testes saem da LEP e do CP.
- `fontes/normas.py`: as versões de uma URN e o texto de cada uma, pelo
  `/api/public/binario/`.
- Campo `urn` nos 68 diplomas de `data/fontes.json`, validado pelo `--estrito`
  (formato, e um diploma por URN).
- Fixtures: `senado-lep.json`, `senado-cp.json`, `senado-lista-2026.json`,
  `normas-cp-versoes.json`.
- **Pronto quando:** `pytest` cobre a tradução de toda notação que aparece nos
  registros da LEP e do CP.
- Tamanho: médio.

### F3. O Cotejador: frescor

- Para cada diploma: a última "Declaração de Alteração Permanente" no Senado,
  ignorando legislação correlata e itens vetados, contra a `sentinela`.
- Três saídas, na issue de segunda:
  - **confere**;
  - **o Senado está à frente**: o compilado talvez esteja atrasado. Prioridade alta
    quando o dispositivo alterado está no catálogo;
  - **o Planalto está à frente**: normal, registra e segue.
- Roda também no ensaio de sexta, que hoje só testa o download.
- **Pronto quando:** a rodada de segunda traz a seção, e uma fixture com o Senado à
  frente gera o aviso.
- Tamanho: pequeno. É a fase de maior valor por linha escrita.

### F4. O Recenseador com duas listas

- Junta a lista do Planalto com a do Senado. O relatório diz quais listas leu; com
  nenhuma lida, continua sem afirmar nada.
- Para cada lei do ano, os registros do Senado dizem que diplomas ela altera. Lei
  que altera um diploma de `fontes.json` sobe para o topo da triagem do watcher.
- **Pronto quando:** com o Planalto fora do ar (fixture), o relatório sai da lista
  do Senado e diz isso.
- Tamanho: pequeno.

### F5. O acervo a partir do compilado

O ganho mais visível. Você decidiu que **registro sem texto já serve**; o
`_meta` do `acervo.json` já admite `texto_original: null` e `data_revogacao: null`.

- `acervo/candidatos.py` percorre os snapshots com `parsear` e `historico` e lista
  todo dispositivo com anotação de revogação: diploma, artigo, norma revogadora, ano.
- **Era tipo penal?** É a pergunta que a máquina não responde sozinha. Proposta:
  - **candidato forte**: o texto riscado, que o Planalto costuma manter, tem
    preceito secundário (`Pena`). A detecção de riscado vem do `html2md.py` do ctresb
    (`exclude_struck`, `line-through`), e o mesmo riscado vira `texto_original`;
  - **pede juízo**: revogado sem texto riscado, ou riscado sem pena (parte geral,
    causa de aumento, norma processual);
  - **descartado, mas nomeado**: dispositivo de diploma não penal (Lei 4.595, Lei
    4.117…) fora do intervalo penal que o `inventario_diplomas.py` já delimita.
- Segunda leitura: os registros do Senado e o texto original do normas.leg.br,
  sempre como aviso. A divergência do art. 240 entra aqui como o primeiro caso.
- Saída: `crawler/relatorios/acervo-candidatos.md` e **um PR que pede juízo** por
  diploma, como o Proponente faz com a hediondez. O `id` segue `<diploma>-<artigo>`,
  append-only, como o resto do acervo.
- Os diplomas penais **revogados inteiros**, que não estão em `fontes.json`, como a
  Lei 6.368/1976 (drogas) e a Lei 7.170/1983 (segurança nacional), entram por
  `data/diplomas.json`. Estão no escopo da F5 (decisão 3): o inventário deles é
  parte da fase, e o Senado (`legislacao/lista`) e o campo `revogada` do
  normas.leg.br servem para levantar os candidatos.
- **Não recepcionados**: o Senado tem itens de "Declaração de Recepção" e de
  "Interpretação conforme" (ADPF 496, no CP), e o ctresb tem
  `jurisprudencia/stf/controle-concentrado`. Os dois servem só para levantar
  candidatos; a categoria `nao_recepcionado` exige a decisão do STF lida.
- **Pronto quando:** o relatório lista, para o CP e a LCP, os 14 registros atuais
  mais os candidatos novos, cada um com a anotação do compilado que o justifica.
- Tamanho: grande. O código é médio; o juízo, registro por registro, é o que pesa.

### F6. O Cotejador: textos

- Ler a moldura com o mesmo `pena_parser` no Planalto e no normas.leg.br
  (`Current`) e comparar. Divergência vai para "pede juízo"; nunca corrige.
- O `texto_original` do acervo contra a versão `Original` do normas.leg.br.
- As anotações seguem padrões diferentes ("Incluído pela" no Planalto, "acrescido
  pela" na Câmara), mas a comparação é só do preceito, onde isso não pesa.
- Tamanho: médio. Exige `fontes/normas.py` (F2).

### F7. Acompanhar o ctresb/leis

- `fontes/ctresb.py`, toda semana, pela API do GitHub e sem clonar os 4 GB:
  - os commits em `scripts/`, para saber o que vale aprender;
  - os arquivos dos nossos 68 diplomas, achados pela URN (por exemplo,
    `federal/leis-ordinarias/1984/lei-7210-1984-07-11.md`). Mudou o arquivo de um
    diploma nosso → aviso no Cotejador.
- O último SHA lido fica em `scripts/robos/cotejador/ctresb.json`.
- **Nunca é dependência do build.** O repositório tem dez dias, é operado por
  agentes e pode reescrever o histórico ou sumir. Se a leitura falhar, o
  Cotejador diz que não leu, e só isso.
- Tamanho: pequeno.

### F8. Histórico legislativo e vetos

- `data/historico-legislativo.json` contra os registros do Senado, dispositivo por
  dispositivo: a norma que o compilado anota é a mesma que o Senado registra?
- Vetos: `materia/vetos/{ano}` e `plenario/resultado/veto/dispositivo/{codigo}` para
  saber quando um veto foi **derrubado**, o caso da fixture
  `abuso-art9-veto-derrubado.html`.
- Tamanho: médio.

### Depois (fora deste plano)

- **Radar de tramitação**: os endpoints de `processo` do Senado acompanham projeto
  de lei penal antes de virar lei. Útil para a pesquisa, mas fora da missão de
  conferir o que está vigente.

## A ordem

```
F1 ──► F2 ──┬──► F3 ──► F4
            ├──► F5 ──► F6
            └──► F7      F8 (depois de F2, a qualquer momento)
```

F3 e F4 primeiro (decisão 5): são pequenas e fecham buracos de segurança reais. O
recenseador de agosto não leu a lista, e hoje ninguém percebe atraso do Planalto.
F5 vem logo depois, com o escopo ampliado da decisão 3.

## O que acompanha cada fase

- `docs/os-robos.md`: vai ao site, e o Cotejador entra como sexto robô.
- `scripts/robos/README.md`: os módulos novos na tabela.
- `AGENTS.md`: a regra "fonte secundária aponta, não escreve".
- `docs/textos/creditos.md`: o Senado, o normas.leg.br (CC BY 4.0, quando texto dele
  for publicado) e o ctresb/leis (MIT, pelo código).
- Workflow: o Cotejador entra como job do `conferidor.yml`, depois do `vigia`,
  sem derrubar a rodada se uma fonte secundária falhar.

## Decisões (25/10/2026)

Tomadas pelo dono do projeto.

1. **Princípio 1, confirmado.** Senado, normas.leg.br e ctresb nunca escrevem no
   catálogo nem no acervo: abrem aviso, pergunta ou PR que pede juízo.
2. **"Era tipo penal?"**: candidato forte só quando o texto riscado tem preceito
   secundário (`Pena`). Todo o resto vai para juízo.
3. **Escopo do acervo**: os 68 diplomas de `fontes.json` **e**, já na F5, os
   diplomas penais revogados inteiros (Lei 6.368/1976, Lei 7.170/1983, Lei de
   Imprensa e os que o inventário achar). Isso exige, dentro da F5, um inventário
   desses diplomas e a URL do compilado de cada um em `data/diplomas.json`.
4. **ctresb/leis**: só observar. Nenhum contato com o autor.
5. **Ordem**: F1 → F2 → F3 → F4, e então F5. F6 a F8 depois.
