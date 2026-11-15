# O dia 1º do AtlasPen

Documento interno de operação — não é publicado no site. Responde a uma pergunta:
**o que chega para mim todo mês, e o que cada coisa exige.**

A rodada é **mensal desde 14/11/2026**. Antes era semanal — o ensaio na sexta, a
rodada e a faxina na segunda —, e a triagem de três entregas por semana passou a
pesar mais do que rendia. O que mudou junto, para que nada fique entre uma rodada
e outra: as janelas de leitura do DOU, dos tribunais e do ctresb foram de 8 para 35
dias, e a régua da faxina de branches, de 7 e 14 para 30 e 60 dias. O Dependabot foi
junto em 15/11/2026: abre os PRs de dependência no dia 3 de cada mês, e não mais toda
quarta — as atualizações menores continuam entrando sozinhas com a CI verde.

No **dia 27, 23:00**, um ensaio (`fontes.yml`) baixa os ~80 compilados
exatamente como a rodada os baixará, e joga fora o que deu certo. Não é para deixar texto
pronto — a rodada baixa o dela e sempre opera com o do dia. É para descobrir
quatro dias antes, e não no dia 1º de manhã, que uma fonte saiu do ar ou mudou de forma
e perdeu a sentinela: quando isso acontece, o `vigia` cai e leva com ele os que
dependem das páginas dele (auditor, cotejador, proponente). Falhou, abre issue com
rótulo `fontes`; voltou, ela se fecha sozinha. Desde 25/10/2026 o ensaio também
adianta o cotejo com o Senado, no resumo da execução — sem issue, porque a rodada
faz a mesma pergunta com as páginas dela.
Quando o ensaio falha, as páginas rejeitadas (`.html.part`) ficam sete dias no
artifact `fontes-rejeitadas-N`, e cada linha da falha diz o tamanho e o título do
que veio.

### Quando o Planalto recusa o runner

Desde 31/10/2026 o firewall da Presidência recusa os endereços dos runners do
GitHub: primeiro com a página "Acesso Negado!", depois (14/11/2026) com outra
página e HTTP 429. Nada em `data/fontes.json` conserta isso, e o robô não insiste:
três recusas seguidas encerram o download. Enquanto durar, a rodada do GitHub sai
sem o vigia, o auditor, o cotejador e o proponente, e a issue diz isso em *Robôs que
não terminaram*. Há três saídas, da mais leve à mais pesada:

1. **Rodar a conferência de uma máquina que o Planalto atende** — a sua. São os
   mesmos programas, na mesma ordem do workflow, e o resultado é o mesmo:

   ```bash
   python scripts/robos/nucleo/baixar.py --todas
   python scripts/robos/vigia/conferir.py --carimbar
   python scripts/robos/auditor/auditar.py
   python scripts/robos/cotejador/frescor.py
   python scripts/robos/cotejador/textos.py
   python scripts/robos/proponente/propor.py
   python scripts/transform_data.py --estrito --max-contradicoes=0
   ```

   Os relatórios saem em `crawler/relatorios/`. O carimbo (`data/conferencia.json`
   e o derivado) vai num commit, como o do robô. Foi assim a rodada de 14/11/2026.
2. **Pedir o desbloqueio** a `bloqueio.de.aplicacoes@presidencia.gov.br`, com o
   código que a página de bloqueio mostra. Os runners trocam de endereço a cada
   execução, então o pedido tem de ser por faixa ou por agente, e pode não vingar.
3. **Um runner próprio**, numa máquina dedicada e numa rede que o Planalto atende.
   É a saída escolhida em 15/11/2026, e os workflows já estão prontos para ela: o
   passo a passo está logo abaixo.

### O runner do Planalto

O vigia, a sentinela, o curador e o ensaio das fontes rodam na máquina que a
variável de repositório `RUNNER_PLANALTO` nomear. **Sem a variável, tudo roda no
GitHub, como antes** — ligar e desligar o runner próprio é criar ou apagar a
variável, sem commit.

**A máquina.** Um aparelho só para isso — mini PC ou Raspberry Pi —, com Ubuntu
Server LTS, ligado na internet de casa. Não o computador de trabalho: o runner
executa o que o workflow mandar, e não deve ter ao alcance nada além do próprio
repositório. A carga é desprezível (uns oitenta downloads e poucos minutos de
Python, duas vezes por mês); o que importa é ficar ligada.

**Antes de registrar o runner, a trava.** Repositório público com runner próprio
exige aprovação manual de TODO workflow vindo de fork (hoje a regra só pega quem
contribui pela primeira vez). É configuração de segurança, e quem muda é o
mantenedor, uma vez:

```bash
gh api --method PUT repos/luccas-amorim/atlaspen/actions/permissions/fork-pr-contributor-approval -f approval_policy=all_external_contributors
```

**Instalar.** Na máquina, com um usuário comum criado só para o runner (sem
`sudo`): em *Settings ▸ Actions ▸ Runners ▸ New self-hosted runner* o GitHub dá os
comandos de download e o token, que vale uma hora. Na configuração, o rótulo é o
que interessa:

```bash
./config.sh --url https://github.com/luccas-amorim/atlaspen --token <o token da página> --name planalto-casa --labels planalto
sudo ./svc.sh install <usuário do runner>
sudo ./svc.sh start
```

O serviço sobe sozinho quando a máquina liga, e o runner se atualiza sozinho.

**Ligar.** Com o runner aparecendo como *Idle* na página, crie a variável:

```bash
gh variable set RUNNER_PLANALTO --body planalto
```

e teste com Actions ▸ *Fontes — ensaio da rodada* ▸ **Run workflow**: tem de sair
`79/79 fontes íntegras` (ou quantas forem). Para voltar ao GitHub:
`gh variable delete RUNNER_PLANALTO`.

**O que saber.**

- Job que espera o runner por mais de 24 horas falha. Máquina desligada no dia 27
  ou no dia 1º aparece na issue como robô que não terminou — e, enquanto espera, a
  rodada segura a fila dos outros workflows que escrevem na `main`.
- O curador recebe a chave do app de automação, porque grava o estado na `main`.
  É mais um motivo para a máquina ser dedicada e a trava dos forks estar ligada.
- Os workflows que usam o runner só disparam por agenda ou à mão. Um
  `pull_request` neles abriria a máquina a código de terceiro.
- Se o Planalto passar a recusar também esse endereço, o `baixar.py` para em três
  recusas e diz o que veio, como faz hoje.

A rodada automática acontece **no dia 1º de cada mês, 05:00 de Brasília**
(`.github/workflows/conferidor.yml`), e também sob demanda em Actions ▸ *Conferidor
mensal* ▸ **Run workflow**. Ela produz, no máximo, **três coisas**: um commit, uma issue
e um pull request.

São **nove robôs**, e desde 10/08/2026 cada um é um job com nome próprio — o log diz
qual falhou sem que você precise abrir o passo. Sete conferem, e desses cinco correm
em paralelo: auditor e cotejador esperam, porque leem as páginas que o vigia baixou.
Os dois últimos entregam — a triagem abre a issue, o proponente abre o PR.

| Job | O que vigia | Falha dele derruba a rodada? |
|---|---|---|
| **vigia** | A moldura de cada tipo contra o texto compilado do Planalto | Sim — é o único de que os outros dependem |
| **sentinela** | O DOU do mês (janela de 35 dias), atrás de lei penal nova e autônoma | Não: o in.gov.br fora do ar não pode calar o relatório do catálogo |
| **recenseador** | A cada rodada agendada, todas as leis sancionadas no ano — a defesa contra o falso negativo | Não: roda dentro do job da sentinela |
| **auditor** | Hediondez, ação penal, causas de aumento e nome do tipo | Não |
| **arquivista** | Saúde da prosa: documento vencido ou cuja dependência mudou | Não |
| **cotejador** | A segunda leitura (desde 25/10/2026): o compilado anota as leis que o Senado registra? A moldura do Planalto é a da Câmara? Mais os vetos do ano e o que mudou no ctresb/leis, que só informam | Não: o Senado fora do ar não pode calar a rodada |
| **relator** | O que o STF e o STJ decidiram no mês (janela de 35 dias) sobre diploma vigiado, lido no Banco Nacional de Precedentes do CNJ (desde 25/10/2026) | Não: o CNJ fora do ar entra em "Robôs que não terminaram" |
| **curador** | A cada rodada agendada, a lei penal antiga que o projeto nunca leu, desde 1889: apontada no ctresb/leis, confirmada no Planalto, com o estado gravado em `data/curadoria.json` direto na `main` (desde 26/10/2026) | Não: e sem o app de automação, o estado vai só no artifact |
| **triagem** | Junta os relatórios e abre a issue | — |
| **proponente** | Transforma em PR o que é leitura direta — moldura, sentinela defasada e modificador de escopo declarado —, e escreve a nota quando a lei é recente | Não: só roda se houver o que propor |

Na rodada agendada — e em rodada manual só **na primeira semana do mês** —, a sentinela
roda também a conferência contra a
lista de leis sancionadas do ano. É a defesa contra o falso negativo: ela não diz se
a lei é penal, diz que existe e que o filtro não a examinou. Leitura curta — basta a
ementa —, e o que criar, agravar ou revogar tipo penal vira entrada em
`data/fontes.json`.

A issue **só nasce se algum dos robôs tiver o que dizer — ou se algum não terminou**.
Cada um responde com 0 (nada) ou 3 (achados); qualquer outro código, ou nenhum,
quer dizer que a pergunta dele ficou sem resposta, e a issue abre com a seção
*Robôs que não terminaram*. Até 25/10/2026 a triagem só olhava o 3, e o Arquivista
e a rodada de auditoria do Proponente passaram semanas caídos sem que nada
chegasse: as rodadas de 12 e 19/10 terminaram verdes, sem issue. Silêncio de todos,
com todos terminados, significa catálogo em dia, e nesse caso a rodada deixa apenas
o commit do carimbo.

## 1. Um commit que chega sozinho — nada a fazer

`chore(catalogo): carimbo da conferência mensal`

É a trilha de auditoria: `data/conferencia.json` mais o derivado, registrando **quando
cada tipo penal foi confrontado com a lei** e com que resultado. Vai direto para a `main`
porque não muda dado nenhum — só anota o que a máquina fez. Se este commit **não** aparecer
num mês, a rodada falhou: vale abrir o log em Actions.

## 2. Uma issue — leitura, não ação imediata

Título: `Conferidor: achados de AAAA-MM-DD`, rótulo `conferidor`. A data é a do dia
em que a rodada começou, lida dos próprios relatórios: a rodada que atravessa a
meia-noite não perde, no corpo da issue, os relatórios datados da véspera.

Ela só nasce quando há o que dizer, **é uma só** e **substitui a da rodada
anterior** — mas só a que ninguém comentou. O conferidor é SEM ESTADO: re-deriva
tudo a cada rodada, então achado que continua valendo reaparece sozinho na
issue nova. O que não reaparece é o que uma pessoa escreveu. Issue com
comentário deixou de ser foto da rodada e virou conversa: ela fica aberta,
ganha um ponteiro para a rodada nova, e só se fecha quando a discussão tiver
destino — um commit, uma exceção julgada, ou uma issue própria. Achado de conferidor é foto de um
momento: a issue de 21/09/2026 acusou como ausente um artigo do Código
Eleitoral que já existia numa branch não mergeada, e continuou aberta dias
depois de ter deixado de valer. O que sobreviver de verdade a uma rodada vira
issue própria, com título que diga o quê — não fica esperando dentro da foto.

A primeira linha diz **contra o quê a rodada correu**: branch, commit e o
tamanho do catálogo. Sem isso não há como distinguir "o catálogo não tem" de
"a `main` ainda não recebeu".

O corpo traz o **resumo**; o relatório completo, com id por id, vai no artifact
da execução. Os dois saem do mesmo apuro — `conferir.py` escreve
`AAAA-MM-DD.md` e `AAAA-MM-DD-resumo.md`.

Os blocos, na ordem em que aparecem — o que pede ação primeiro:

| Bloco | O que é | O que costuma exigir |
|---|---|---|
| **Robôs que não terminaram** | Robô que saiu com código que não é 0 nem 3 — exceção, fonte ilegível, job que não chegou ao passo. Desde 25/10/2026 | Abrir o log da execução (o link está no bloco). A pergunta daquele robô ficou sem resposta nesta rodada, e o resto da issue não a cobre |
| **Achados de pena** | Moldura ou espécie de pena divergindo do compilado; dispositivo revogado; dispositivo com pena própria ausente do catálogo; linha de pena derivada cuja conta (base × fração da lei) não fecha — `DIVERGENTE-derivada`, desde 28/09/2026 | Ler o artigo no Planalto. O que for mecânico já veio em PR (item 3); o resto é decisão de modelagem |
| **A lei escreveu a pena e o parser não leu** | Os `ilegivel`: registros em que há moldura no compilado e o `pena_parser` não a extraiu | Ação NOSSA, e o único balde do "sem moldura" que pede alguma. Abrir o dispositivo e ver o que o parser não leu; o número tende a zero. Tem seção própria, no alto, desde 24/09/2026 — antes dividia a tela com 152 registros que estavam certos |
| **Cobertura** | Quantos registros foram conferidos e, por motivo, quantos não têm moldura própria na lei | Nada, em regra: são limites DECLARADOS, a lei não deixou moldura ali. No corpo da issue vêm como contagem; id por id fica no artifact. Se "não localizado" subir, é sinal de rótulo errado no catálogo ou de mudança na página |
| **Auditoria de classificação** | Hediondez, ação penal, causas de aumento ausentes e nomes — inclusive o nome que descreve MELHOR outro artigo do mesmo diploma | Juízo jurídico. Hediondez e ação penal já vêm propostas em PR; aumentos e nomes ficam só aqui. `NOME-DE-OUTRO-ARTIGO` pede reconferência da PENA junto com o nome: quando os dois artigos cominam a mesma moldura, a troca é invisível para a conferência |
| **Já julgado** | Uma linha dizendo quantos achados foram omitidos por decisão anterior | Nada. Se o número subir sem motivo, abrir `scripts/robos/auditor/excecoes-auditoria.json` e conferir se alguma exceção está ampla demais |
| **Saúde da documentação** | Documento que passou da cadência (90 dias) ou de que algum arquivo dependente mudou depois da última conferência | Reler. Se nada mudar, atualizar `conferido_em` em `data/documentacao.json`; se corrigir, o commit já responde |
| **DOU do mês** | Atos normativos da Seção 1 triados em três níveis pelo PRECEITO SECUNDÁRIO — quem fala de pena sem cominar nenhuma não cria crime | Ler só os dois primeiros níveis. **Possível tipo penal em diploma não monitorado** é o ponto cego do conferidor, e o PR da rodada já traz a entrada de `data/fontes.json` para conferir. **Mexe em diploma que já vigiamos** é antecedência: o conferidor veria na rodada seguinte, mas a `sentinela` daquela fonte talvez precise mudar. Os **descartados** ficam nomeados no fim, uma linha cada, para o corte ser auditável |
| **Cotejo com o Senado** | Lei recente que o Senado registra para um diploma vigiado e que a página baixada do Planalto não cita; à parte, as provavelmente superadas por lei posterior no mesmo dispositivo. Desde 25/10/2026 | Abrir o compilado e procurar a lei. Se o Planalto está atrasado, o catálogo pode estar conferido contra texto velho; se o Senado errou, nada a fazer. O que toca registro do catálogo vem primeiro. A lei que não deu redação nova (remissão, suspensão temporária) e por isso não tem o que anotar vira exceção em `scripts/robos/cotejador/excecoes-cotejo.json`, com motivo e data; a exceção que deixa de casar aparece como "sem efeito" e sai |
| **Molduras Planalto × Câmara** | Dispositivo cuja pena difere entre o compilado do Planalto e a compilação da Câmara (normas.leg.br) | Abrir as duas no dispositivo. O catálogo segue o Planalto; a divergência diz que uma das duas está atrasada. Câmara atrasada, lida na lei alteradora, vai para `scripts/robos/cotejador/excecoes-textos.json`; Planalto atrasado continua na issue |
| **Vetos e ctresb/leis** | Vetos do ano a leis que mexem em diploma vigiado (os que ainda tramitam podem cair) e o que mudou no ctresb/leis — no código, nos arquivos dos nossos diplomas e, desde 25/10/2026, na jurisprudência do STF e do STJ | Nada, em regra: só informam, e nunca abrem issue sozinhos |
| **Tribunais** | Precedente do STF ou do STJ atualizado no mês que toca diploma vigiado. Sobe para leitura a súmula cancelada, superada ou alterada, a tese revisada, o que fala em não recepção, inconstitucionalidade ou interpretação conforme, e o que toca registro do catálogo ou atributo penal; o resto fica numa linha. Cada seção mostra até 40; o resto está no JSON do artifact. Desde 25/10/2026 | Ler o acórdão ou o enunciado no portal do tribunal, não o resumo do CNJ: a natureza que o relatório mostra é pista lida do texto. Se a decisão retira o dispositivo, o registro ganha `vigencia_ate` e vai para o acervo; se modula o alcance, a ressalva vai para o `obs` ou para `data/avisos.json`; se toca atributo, o requisito ou a vedação vai para `data/atributos.json`, com a fonte. Nada disso o robô faz |
| **Curador** | Na rodada agendada, as leis antigas confirmadas pela primeira vez no Planalto, e as que mudaram de estado: pena de prisão vigente (desde 1942, e antes, com o aviso da revogação tácita), revogadas, sem página. À parte, em uma linha, as que alteram diploma vigiado e as que só têm multa ou sanção administrativa | Pena vigente: abrir o Planalto e decidir se o diploma entra em `data/fontes.json`. Revogada: candidata ao acervo, conferida no texto riscado. Sem página: procurar o texto em outra fonte oficial. O robô não escreve em nenhum dos três |
| **Leis do ano** | Na rodada agendada, o relatório do Recenseador — antes ele decidia se a issue abria e não entrava no corpo | Ler as ementas. Varredura incompleta (aviso) quer dizer que a janela do falso negativo continua aberta |

**Fechar a issue significa "triado"** — não "resolvido". O que virar tarefa vira commit ou
PR próprio.

## 3. Um pull request — é aqui que você decide

Um por rodada, um aberto por vez, autor `atlaspen-automacao[bot]`, rótulo `conferidor`.
Quando alguma mudança vem de **lei recente**, ele escreve a nota de atualização e sobe o
patch da versão (em `0.0.x` até o lançamento; o merge não publica release antes da v1.0.0).
**Confira o alcance** de cada nota (`tipo` ou `atributo`) e a direção que o título afirma — pena agravada ou abrandada — na seção
"Notas de atualização" do corpo. Correção de dado não vira nota, e o corpo diz o motivo.

Dois tipos, nesta ordem de prioridade:

**a) PR de pena** — `fix(catalogo): N correção(ões) em <diploma>`

Moldura ou espécie de pena de registro que já existe, divergindo do texto compilado. Um
diploma por PR. Cada mudança traz o trecho da lei ao lado. **É leitura de texto, não
juízo**: a revisão aqui é conferir se o trecho citado sustenta o número.

Desde 28/09/2026 o mesmo PR pode trazer duas coisas mais, com a mesma régua. **Sentinelas**:
a fonte cuja página já anota lei mais nova que a sentinela ganha o número novo — confira
que a anotação citada existe na página. **Modificador de escopo declarado**: o dispositivo
que diz "na hipótese do § 10" ou "a pena prevista no § 2º-A" vira modificador com a fração
lida do texto — confira o alcance, que é a única leitura por analogia de redação que a
máquina faz. Sem nota: a nota da lei sai com as linhas. O que não declara alcance continua
na issue, como pergunta. Se a rodada só tiver sentinelas, o PR sai como
`chore(fontes): N sentinela(s) apontam para a lei mais recente do compilado`.

**b) PR de classificação** — `fix(catalogo): N ajuste(s) de hediondez e ação penal`

Só sai quando não há PR de pena pendente. **Este exige juízo jurídico**, e por isso vem
como proposta com o fundamento ao lado:

- **hediondez** — comparação com o rol do art. 1º da Lei 8.072/1990, transcrito em
  `data/hediondos.json`. Onde a lei condiciona a hediondez a circunstância do caso
  (grupo de extermínio, vítima criança, organização direcionada a crime hediondo), **nada
  é proposto** — a lei não decide pelo tipo;
- **ação penal** — fórmulas do próprio artigo ("somente se procede mediante
  representação"). Regra de ação penal que more em artigo de encerramento de capítulo ou
  em outro diploma não é alcançada;
- **fontes novas** — quando o DOU trouxe lei que parece criar tipo penal, a entrada
  proposta para `data/fontes.json` vem junto, para você corrigir em vez de escrever.
  Desde 25/10/2026 ela traz a `urn`, montada da data do título; confira contra a
  ficha do Senado, porque URN errada aponta para outra norma sem quebrar nada.

## O que a máquina NUNCA faz sozinha

- criar registro de tipo penal (a leva automática da v1.3.0 trouxe 29 que não eram crime);
- remover registro (decidir o destino do `id`, que é URL pública);
- transformar dispositivo em modificador, ou o contrário;
- mergear qualquer PR.

## O que fica esperando decisão sua, hoje

Registrado aqui para não se perder entre uma rodada e outra. Ao resolver, tire da lista.

| Pendência | Onde | Por que depende de você |
|---|---|---|
| **Causas de aumento e diminuição** que a lei tem e `modificadores.json` não — 12 já julgadas em `excecoes-auditoria.json`, e 30 novas que a regex ampliada do auditor passou a enxergar em 28/09/2026 ("a pena aumenta-se de", "as penas aumentam-se de", "reduzir a pena de", "as penas poderão ser reduzidas de") | `auditar.py`, seção MODIFICADOR-AUSENTE da issue semanal | Modelar exige decidir o escopo — sobre quais tipos o aumento incide —, e isso não se lê do dispositivo isolado. As duas linhas que estavam acima saíram em 28/09/2026: a hediondez do CPM foi resolvida pela varredura da decisão 29 (o CPM passou a ser auditado inteiro), e o marco legal é a Lei 15.358/2026, em `data/fontes.json` desde setembro |
| **13 nomes suspeitos** | `auditar.py`, em `crawler/relatorios/` | A heurística compara palavras; a decisão de renomear é de conteúdo. Pelo menos seis parecem erro real (o art. 338 do CP está com o nome da sonegação previdenciária, que é o art. 337-A) |
| Auditoria de **`tentativa`** | ainda não existe | Não há fonte textual que a declare: é qualificação doutrinária do tipo, derivada do `elemento`. Precisaria de tabela curada, como a da hediondez. `violencia`, `grave_ameaca` e `acao` deixaram de estar nesta linha em 23/09/2026, quando ganharam derivadores próprios (`conferir_violencia.py` e `conferir_acao_penal.py`), que leem o texto do dispositivo e separam o que confere, o que diverge e o que pede juízo |

## Quando algo falha

| Sintoma | Provável causa | O que fazer |
|---|---|---|
| A rodada falha em "Baixar os textos compilados" | Sentinela ausente: a página veio truncada ou de cache velho | Reexecutar. Se persistir, abrir a URL da fonte no navegador e conferir se o texto mudou de forma |
| A issue vem com muitos "não localizado" | Rótulo do catálogo apontando para dispositivo que não existe, ou mudança na numeração da lei | Conferir os ids listados contra o compilado |
| `ROL-ALTERADO` na auditoria de hediondez | O art. 1º da Lei 8.072 mudou | Reler o artigo, ajustar `data/hediondos.json` e regravar `impressao_do_texto` com o valor que o relatório informa |
| Nenhum PR, mesmo com achados | Não havia correção mecânica, ou já existe PR aberto do robô | Normal. Ver a issue |
