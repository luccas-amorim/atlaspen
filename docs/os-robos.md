---
title: Os robôs
description: Como o AtlasPen descobre que a lei mudou — o que cada robô vigia, com que critério, e o que nenhum deles alcança.
---

# Os robôs

Um catálogo de direito penal envelhece sozinho. A lei muda toda semana, e a
defasagem não avisa: um registro errado tem a mesma aparência de um registro
certo. A resposta do projeto a isso são **rotinas automáticas** que rodam toda
segunda-feira, às 5h de Brasília, cada uma vigiando uma coisa diferente. Hoje são
oito, e cada uma tem nome próprio — o log diz qual falhou sem que ninguém precise
abrir a execução.

Esta página existe para que você possa **discordar dos critérios**. Todos eles
são escolhas, várias são discutíveis, e quase todas já mudaram pelo menos uma vez
por causa de um erro que passou. Se um critério lhe parecer estreito demais ou
largo demais, [abra uma issue](https://github.com/luccas-amorim/atlaspen/issues) — é
o tipo de retorno que mais serve ao catálogo.

:::note[Determinístico, sem IA]
Nenhum dos oito usa modelo de linguagem. São expressões regulares e comparação
de texto, lidas contra o texto **compilado** oficial do `planalto.gov.br`. O
Cotejador lê também o Senado e o normas.leg.br; o Relator, o Banco Nacional de
Precedentes do CNJ; o Curador, o repositório ctresb/leis — mas só para perguntar: nada que vem de lá escreve no catálogo. Onde não há certeza, o resultado é uma **pergunta
para leitura humana**, nunca uma alteração automática do dado.
:::

## O que cada um vigia

| Robô | Pergunta que responde | Onde procura |
|---|---|---|
| **Vigia** | A pena publicada é a que a lei comina hoje? | O texto compilado de cada diploma de `data/fontes.json` |
| **Sentinela** | Nasceu lei penal que ainda não vigiamos? | A Seção 1 do Diário Oficial da União |
| **Auditor** | Os campos que a pena não alcança estão certos? | Hediondez, ação penal, causas de aumento e nomes |
| **Arquivista** | A prosa ainda descreve o sistema? | A documentação, contra os arquivos de que ela fala |
| **Recenseador** | Existe lei penal que ninguém leu? | Todas as leis do ano, uma a uma (mensal) |
| **Cotejador** | O compilado do Planalto está em dia? | O registro do Senado e a compilação da Câmara |
| **Relator** | O STF ou o STJ decidiram algo sobre a lei que vigiamos? | O Banco Nacional de Precedentes do CNJ |
| **Curador** | Existe lei penal antiga que o projeto nunca leu? | Toda a legislação federal desde 1889, no ctresb/leis, confirmada no Planalto (mensal) |

Sentinela, Arquivista e Relator correm em paralelo com o Vigia; Auditor e Cotejador esperam
por ele, porque leem as páginas que ele baixou. O Recenseador e o Curador rodam uma
vez por mês, na primeira semana. Se algum tiver o que dizer, nasce **uma issue por rodada**. Se
todos se calarem, a rodada deixa só o carimbo de que a conferência aconteceu.

:::caution[Robô que quebra não se cala]
Cada robô responde com um de dois códigos: nada a dizer, ou achados. Qualquer outro
— uma exceção, uma fonte ilegível, um job que nem chegou ao passo — quer dizer que
a pergunta da semana **ficou sem resposta**, e isso também abre a issue, com o robô
nomeado. Até 25/10/2026 a triagem só olhava os achados: o Arquivista quebrou toda
semana desde agosto, a rodada de auditoria do Proponente também, e as rodadas de 12
e 19 de outubro terminaram verdes, sem issue, com dois robôs caídos.
:::

A issue da semana **substitui a da semana passada**, que é fechada como superada — mas só
a que ninguém comentou. A conferência é sem estado: ela recalcula tudo a cada rodada, então
achado que continua valendo reaparece sozinho na issue nova. O que não reaparece é o que
uma pessoa escreveu. Issue com comentário deixou de ser a foto da semana e virou conversa:
fica aberta, e só se fecha quando a discussão tiver destino.

Na **sexta-feira anterior**, às 23h, um ensaio baixa os mesmos compilados e joga fora. Não
é para adiantar trabalho — a segunda baixa os dela e sempre lê o texto do dia. É para
descobrir com o fim de semana pela frente que uma fonte saiu do ar ou mudou de forma:
quando isso acontece, o Vigia cai e leva o Auditor com ele; Sentinela e Arquivista
seguem, porque não dependem do que ele baixou.

---

## Vigia — a moldura contra o compilado

Baixa a página compilada de cada diploma de `data/fontes.json`, estrutura dispositivo por
dispositivo, lê as molduras de pena e compara com o que o catálogo publica. Os diplomas
de referência — a Lei dos Crimes Hediondos, a LEP, o CPP, a Lei 9.099/95 e a CF — não
têm tipo penal no catálogo: são baixados porque fundamentam a hediondez e os atributos.

**O que ele acusa:** moldura ou espécie de pena divergente; dispositivo que a lei
comina e o catálogo não tem; registro cujo dispositivo não foi localizado; e, desde
28/09/2026, linha de **pena derivada** cuja conta não fecha.

**Pena derivada.** Cento e sessenta linhas do catálogo não têm moldura escrita na
lei: são aumento, diminuição, dobro ou metade de outra moldura ("na hipótese do
§ 10, a pena é aumentada de um terço"). Até 28/09/2026 elas saíam da conferência
como limite declarado — contadas, nunca conferidas —, e foi debaixo desse número que
o incêndio majorado publicou por meses a pena do caput sem o aumento, e a corrupção
passiva majorada, a pena simples. Agora o Vigia refaz a conta: a base é o registro
que o próprio catálogo aponta (o `c/c` do artigo, ou o caput do mesmo artigo) e a
fração é a do texto da lei. O que a regra não decide — base em outro artigo que o
registro não declara, texto sem fração legível, o dobro que chega ao teto do CPM
onde a lei comina morte — sai como *pede juízo*, com o motivo escrito, e não como
número. "Na mesma pena incorre" é seguido de um salto: ao caput, ao parágrafo citado ou ao
artigo anterior com moldura. Na primeira rodada, 154 das 160 fecharam a conta de
primeira, seis pediram juízo e quatro estavam erradas; decididos os casos de juízo,
sobra um — o art. 141, III do Código Penal, que majora três artigos de uma vez.

**O que ele não faz:** criar nem remover registro. Criar exige decidir se o
dispositivo é crime autônomo, causa de aumento ou nada — e essa decisão é humana.
A primeira leva automática de criação trouxe 29 registros que não eram tipos
penais vigentes, e foi preciso retirá-los na versão seguinte.

### A trava de cobertura

É a peça mais importante do Vigia, e a menos óbvia. Ele conta **quantos registros
não consegue garantir**, separados por motivo, e guarda um teto para cada um.
Passar do teto é regressão e vira achado.

A razão é o modo de falhar que mais dói aqui, que é o silencioso: quando o Vigia
lê um registro e a pena não bate, sai um achado — você vê. Mas quando o registro
**sai da conferência**, ele não aparece como divergente; aparece como nada. E
silêncio não é aprovação.

A trava nasceu de um caso concreto: três incisos do art. 151 do Código Penal
publicaram por anos seis vezes a pena que a lei comina, e nenhuma rodada disse
nada — porque um dispositivo cuja pena está em outro dispositivo nunca tem pena
escrita para conferir.

**Motivos pelos quais um registro fica fora da conferência**, todos declarados:

| Motivo | O que significa |
|---|---|
| `pena_derivada` | A lei manda calcular sobre uma base ("aumenta-se de um terço") e a conta não fecha sozinha: base em outro artigo que o registro não declara, ou sem moldura legível. Desde 28/09/2026 as demais são recalculadas e contam como conferidas |
| `pena_importada` | A lei manda aplicar a pena de outro dispositivo |
| `sancao_nao_privativa` | O tipo não comina prisão (multa, ou outra sanção) |
| `sem_preceito_proprio` | O dispositivo não comina pena: é norma explicativa |
| `ilegivel` | **A lei escreveu a pena e o leitor não conseguiu ler.** É lacuna a fechar, não número aceito |
| `nao_localizado` | O dispositivo do registro não foi achado no compilado. **O teto é zero** |

### Quando o catálogo já diz que a pena é de outro artigo

Alguns tipos não cominam moldura própria: o art. 304 do Código Penal pune o uso
de documento falso com "a pena cominada à falsificação". Outros derivam de outro
artigo por um fator — os crimes de tempo de guerra do Código Penal Militar. Nesses
casos o Vigia não compara nada, porque o próprio registro já declarou de onde a
pena vem. Ele conta o registro entre os que não garante, com o motivo ao lado.

---

## Sentinela — a lei penal que ainda não existe para nós

O Vigia relê o que já conhece. Ele é cego para uma coisa só: **lei penal nova e
autônoma**, publicada num diploma que ainda não está na lista. O Sentinela cobre
exatamente esse ponto cego.

### Os critérios, na ordem em que se aplicam

**1. Só lei ordinária e lei complementar.** A Seção 1 publica cerca de 330 atos
por dia, e mais de 90% são portaria e despacho. Pelo **princípio da reserva
legal** (art. 5º, XXXIX, da Constituição; art. 1º do Código Penal), só há duas
espécies capazes de criar tipo penal, e o Sentinela olha apenas essas duas.

:::note[Por que medida provisória não entra]
Não é economia de requisição: é direito. A Constituição veda medida provisória
sobre direito penal (art. 62, §1º, I, "b"), e MP não gera tipo — vigiá-la seria
vigiar o que não pode existir. Pela mesma razão saem a **lei delegada** (a
delegação não alcança direitos individuais, art. 68, §1º, II), o **decreto-lei**
(espécie extinta em 1988: nenhum novo será publicado) e a **emenda
constitucional** (os arts. 5º, XLI a XLIII, são mandados de criminalização,
dirigidos ao legislador ordinário — não criam crime).
:::

**2. Texto integral, sempre.** Os poucos atos que sobram são baixados por
inteiro. Não há filtro por palavra-chave antes da leitura — havia, com treze
termos, e ele foi removido: poupava vinte segundos por quinzena e, em troca,
decidia sem ler o que merecia leitura. Uma lei cuja ementa dissesse "altera o
Decreto-Lei nº 2.848 para dispor sobre a conduta de X" não tinha nenhum dos treze
termos e nem chegava a ser aberta.

**3. O corte é o preceito secundário.** O que separa lei penal de lei que *fala*
de pena é a cominação: `Pena –`, `reclusão, de`, `detenção, de`, `prisão simples,
de`. Um ato que fale de pena sem cominar nenhuma não cria nem altera crime.

Mas há tipo penal que não escreve nada disso, e por isso o teste também reconhece
a **pena por remissão** — "nas mesmas penas", "a pena cominada à falsificação",
"metade da pena", "no dobro da pena cominada para o tempo de paz" — e a pena
cominada fora da fórmula, como o "será submetido às seguintes penas" do art. 28
da Lei de Drogas. São ao menos nove registros do próprio catálogo redigidos
assim.

**4. Rede de segurança pela ementa.** Quando a página do ato não abre, não há
texto onde procurar. Aí vale a ementa, e ela reconhece tanto a lei autônoma
("institui o crime de") quanto a **alteradora**, que é a forma dominante da
legislação penal brasileira e tem redação padronizada pela LC 95/98: "para
tipificar", "para agravar a pena", "para tornar hediondo", "acrescenta o art.".

### Três níveis, e o descartado não some

| Nível | Quando | O que significa |
|---|---|---|
| **novo** | Comina pena e não cita diploma que já vigiamos | O ponto cego real: tipo penal em página que ninguém acompanha |
| **monitorado** | Comina pena, ou revoga dispositivo, e cita diploma vigiado | O Vigia veria na rodada seguinte; o ganho aqui é a antecedência |
| **descartado** | O resto | Sai **nomeado**, em uma linha, com o motivo |

O descartado sair nomeado é deliberado: três segundos de leitura, e a decisão do
filtro fica auditável. Um corte que apaga o que cortou não pode ser conferido.

Pela mesma razão, o **dia que não abre sai nomeado**. Se a listagem de um dia do DOU
não responde, o Sentinela registra o dia e a seção que ficaram sem leitura e segue
pelos outros; o relatório abre dizendo que a varredura está incompleta. Até
25/10/2026 uma listagem lenta derrubava o robô inteiro, e a semana toda ficava sem
resposta por causa de um dia.

---

## Recenseador — a lei que ninguém leu

O Vigia é completo sobre o que conhece. O Sentinela cobre o que nasce. Fica ainda
uma terceira pergunta, e é a mais desconfortável: **e o que já existia e nunca foi
lido?**

O sistema sabe quantos alarmes falsos gera — o descartado do Sentinela sai nomeado
toda semana. Do inverso não sabia nada. Uma lei penal publicada que o filtro semanal
não pegasse não deixaria rastro em lugar nenhum, e esse é o erro que custa meses de
catálogo desatualizado justamente porque **não faz barulho**.

Uma vez por mês, o Recenseador **baixa todas as leis do ano, uma a uma**, e testa
cada uma contra o mesmo critério do Sentinela — o preceito secundário. As que cominam
pena e não estão entre os diplomas vigiados viram lista de leitura, curta, com a
ementa de cada uma ao lado.

O portal de legislação do Planalto está atrás de proteção anti-bot, e nenhum quadro
por ano responde. Mas a página de cada lei responde, e a numeração das leis é
sequencial e nacional — então a enumeração é feita por sondagem, do primeiro ao
último número do ano, com o corte de ano vindo do cabeçalho que a própria lei
declara. Custa alguns minutos, uma vez por mês.

Desde 25/10/2026 há uma **segunda lista**: a das leis do ano na API de Dados Abertos
do Senado. Ela não substitui a sondagem e não decide nada — o texto lido continua
sendo o do Planalto —, mas diz por onde começar e fecha as lacunas de numeração em
que a sondagem pararia. O relatório diz quais das duas listas foram lidas. Na
primeira rodada com as duas, elas terminaram na mesma lei (a 15.526, de 29/09/2026),
e a sondagem achou uma que o Senado ainda não listava.

:::note[Ele aponta, não conclui]
Cominar pena **não é** criar tipo penal novo: a lei pode estar apenas alterando um
diploma que já acompanhamos, ou repetindo preceito. O Recenseador diz que a lei
existe e que ninguém a leu — quem decide se ela entra é gente. E, se não conseguir
ler as leis, **não afirma nada**: reportar "nenhuma ficou de fora" sem ter lido a
fonte seria produzir exatamente o silêncio que ele existe para quebrar. Até
25/10/2026 o relatório dizia isso e o robô, mesmo assim, saía com o código de
"nada a relatar"; e conexão perdida contava como número vazio, encerrando a
varredura como se o ano tivesse acabado. Agora varredura incompleta tem código
próprio e vira aviso na issue.
:::

---

## Curador — a lei que ninguém leu, desde 1889

O Recenseador varre o ano corrente; a legislação penal brasileira tem quase dois
séculos. Existe tipo em lei esparsa antiga que o catálogo nunca viu, e existe tipo
revogado sem que ninguém percebesse. O Curador lê **toda lei ordinária, decreto-lei e
lei complementar desde 1889** e aponta as que cominam pena e que o projeto não
conhece — nem em `data/fontes.json`, nem no inventário de diplomas, nem no acervo.

**O ctresb aponta, o Planalto confirma.** Baixar 30 mil páginas do Planalto levaria
mais de dez horas, e o endereço de uma lei antiga muda conforme a época. Por isso a
triagem roda no repositório [ctresb/leis](https://github.com/ctresb/leis), que tem a
legislação federal convertida para Markdown, e só a lei em que ele acha pena é aberta
no Planalto. Lá, a página só vale se o cabeçalho declara o mesmo número e o mesmo ano:
a Lei 4.242 existe em 1921 e em 1963, e o endereço que responde é o da de 1963.

**A pena própria, não a citada.** Quase toda lei que altera o Código Penal traz
"Pena –" dentro do texto que dá a ele, entre aspas. Essa pena é de um diploma que o
Vigia já lê, e o Curador a descarta. A lei antiga que escreve "incorrerá na pena de
prisão cellular" também conta, mas só antes de 1941: o critério do Sentinela e do
Recenseador não reconhece essa redação, e não deve — "pena de multa" também é sanção
administrativa moderna.

**O que o Planalto diz vira um estado.** Pena de prisão vigente: candidata a
`data/fontes.json`, com aviso quando a lei é anterior ao Código Penal de 1940, que
pode tê-la revogado tacitamente sem que a página diga. Revogada, ou só com a pena
riscada: candidata ao acervo. Sem página no Planalto: pede juízo. Só multa ou sanção
administrativa: lista curta, de baixa prioridade. A lei que altera um diploma que o
projeto já vigia sai à parte, porque a pena dela é, quase sempre, a do texto que dá a ele.

Na varredura única, em 26/10/2026, o Curador triou **28.994** normas e apontou **209**
com pena própria que o projeto não conhecia. No Planalto, 59 tinham pena de prisão
vigente, 40 estavam revogadas, 1 só com a pena riscada, 35 sem prisão, 14 sem pena, e
60 não tinham página. Entre as de pena vigente estavam a Lei 7.853/89 (crimes contra a
pessoa com deficiência), a Lei 10.300/01 (minas terrestres) e a Lei Complementar
105/01 (sigilo bancário). O estado fica em `data/curadoria.json`: todo mês, o Curador
relê só os anos que o ctresb mudou e reconfere no Planalto o que venceu 180 dias.

:::caution[O que o ctresb não tem, o Curador não triou]
Contra a contagem do Senado, ano a ano, o ctresb tem quase tudo: 16.379 das 16.427
leis ordinárias, 12.376 dos 12.378 decretos-lei. Mas não tem nenhum dos **8.193
decretos** dos governos provisórios (1889–1891 e 1930–1934), que tinham força de
lei — o Código Penal de 1890 é o Decreto 847. É a lacuna que o relatório declara toda
vez, com os números.
:::

---

## Cotejador — a segunda leitura

O Vigia confere o catálogo contra o compilado do Planalto. Ninguém conferia o
**compilado**: se o Planalto demora a incorporar uma lei, o Vigia compara o catálogo
com texto velho e diz que está tudo certo. O Cotejador pergunta a outras fontes
oficiais, e só pergunta — nada que vem delas escreve no catálogo.

**O compilado anota as leis que o Senado registra?** A API de Dados Abertos do Senado
diz, norma por norma, que leis posteriores mudaram cada dispositivo. O Cotejador lê as
alterações recentes de cada diploma vigiado e procura cada lei na página que o Vigia
baixou — o Planalto anota toda lei que muda o texto ("Redação dada pela Lei nº …").
A que não aparece vira pergunta, com prioridade para a que toca registro do catálogo.

**A moldura do Planalto é a da Câmara?** O normas.leg.br, do Congresso, serve a
compilação vigente que a Câmara mantém — outra equipe compilando o mesmo texto legal.
O Cotejador lê a pena de cada dispositivo nas duas, com o mesmo leitor que o catálogo
usa, e acusa onde discordam.

**Vetos que ainda podem cair.** Veto derrubado muda o texto meses depois da sanção.
O Cotejador lista os vetos do ano a leis que mexem em diploma vigiado e diz quais
ainda tramitam. Só informa.

:::caution[O Senado também erra]
A classificação do Senado é catalogada à mão, e erra: a Lei 11.106/2005 revogou os
arts. 217, 219 a 222 e 240 do Código Penal, e o Senado registra as seis como
"alteração". E o compilado anota a redação que vale: quando outra lei reescreve o
mesmo dispositivo, a anotação da anterior pode sumir — a Lei 15.229/2025 incluiu
o art. 171, §5º, III, do Código Penal, a Lei 15.397/2026 reescreveu o artigo, e a
página cita só a segunda. Esse caso não abre issue: sai numa lista à parte, de
leis provavelmente superadas.
:::

Na primeira rodada, em 25/10/2026, 52 dos 68 diplomas conferiram, 9 não tinham
alteração registrada no Senado e 7 tinham lei que a página não cita.

O Cotejador lê também, por curiosidade técnica, o repositório público
[ctresb/leis](https://github.com/ctresb/leis), que converte a legislação brasileira
para Markdown: o que mudou no código dele e nos arquivos dos nossos diplomas. É de
terceiro, operado por agentes, e nunca é fonte de dado; parte da rede comum dos robôs
veio de lá. Desde 25/10/2026 lê também os commits na jurisprudência do STF e do STJ
que ele reúne: pista para o Relator, nunca decisão lida.

---

## Relator — o que o STF e o STJ decidiram na semana

A decisão de tribunal muda o catálogo com a força de uma lei, e não passa pelo Diário
Oficial da União. O Relator lê, toda semana, no
[Banco Nacional de Precedentes](https://pangeabnp.pdpj.jus.br) do CNJ, os precedentes
atualizados nos últimos oito dias e separa os que tocam um diploma vigiado:

- do **STF**, o controle concentrado (ADI, ADPF, ADC, ADO), os temas de repercussão
  geral, as súmulas e as súmulas vinculantes;
- do **STJ**, as súmulas, os temas dos recursos repetitivos e os incidentes de
  assunção de competência. A controvérsia, que é só a proposta de afetar um tema, fica
  de fora.

**Como ele sabe que a decisão toca a lei.** No controle concentrado, o CNJ codifica o
ato impugnado: `LEG-FED DEL-002848 ANO-1940 ART-00331` é o art. 331 do Código Penal. No
tema e na súmula não há código, e o diploma sai do texto — pela citação ("Decreto-lei
3.688/1941"), pelo nome ("Lei de Contravenções Penais") ou pela sigla com que o STJ
escreve ("art. 155, § 4º, do CP") —, e o artigo, do "art. N" que vem logo antes. O
artigo leva ao registro do catálogo e também ao **atributo penal**: cada atributo
declara o dispositivo em que se apoia, e a remição é o art. 126 da Lei de Execução
Penal.

**O que pede leitura.** Na súmula e no tema, a situação que o CNJ registra fala
primeiro: súmula cancelada, superada ou alterada, e tese revisada. Tema cancelado não
conta — é afetação desfeita, sem tese. Depois, a decisão cujo texto fala em não
recepção, inconstitucionalidade ou interpretação conforme, e a que toca registro do
catálogo ou atributo, seja qual for. A natureza é pista lida do texto, não
classificação: a ementa da ADPF 338, que julgou constitucional o aumento do art. 141,
II, do Código Penal, cita a inconstitucionalidade que foi pedida e sai marcada por ela.
Por isso o Relator aponta, e quem assina lê o acórdão.

**A súmula que não cita a lei.** "No crime de roubo, a intimidação feita com arma de
brinquedo autoriza o aumento da pena" — a Súmula 174 do STJ, que o banco registra como cancelada — não
nomeia diploma nem artigo. Súmula ou tese que muda de alcance e fala de crime, pena ou
punibilidade pede leitura mesmo sem diploma identificado.

:::caution[Oficial, e incompleto]
O banco do CNJ é a fonte oficial dos precedentes qualificados, e não tem tudo. Medido em
25/10/2026: da ADPF 130 (Lei de Imprensa) ele guarda só a cautelar de 2008, não o mérito
de 2009; a ADPF 291 (Código Penal Militar, art. 235) não está lá. O silêncio dele não
prova nada.
:::

Na primeira rodada, em 25/10/2026, a semana trouxe 14 precedentes do STF e nenhum sobre
lei vigiada. Lido também o STJ, a mesma semana trouxe 23 precedentes dele, e o Tema 1270
dos repetitivos — a remição proporcional da pena pela aprovação parcial no Enem — tocou o
atributo remição, que não fala do Enem. Na janela de um ano, 50 tocavam diploma vigiado, e o Tema 113 — o art. 25
da Lei de Contravenções Penais, não recepcionado — apontou o registro 766, que já
trazia a vigência encerrada em 05/10/1988 e já estava no acervo. A ADI 7555, que esta página dava como o exemplo
da lacuna que nenhum robô via, está no banco, e o Relator a aponta com os registros do
Código Penal Militar que ela atingiu.

---

## Auditor — os campos que a pena não alcança

A pena não é o único dado que decide a vida de alguém. Hediondez muda a fração de
progressão e veda o livramento; a espécie de ação penal decide se o processo
começa. O Auditor vigia o que o Vigia não vê.

**Hediondez.** Comparação contra uma tabela curada, mais um alarme quando o texto
do rol muda: o Auditor guarda uma **digital do art. 1º da Lei 8.072/90** e a
confere a cada rodada. Foi ela que, em agosto de 2026, avisou que a Lei
15.487/2026 tinha reescrito o inciso que trata do Estatuto da Criança e do
Adolescente — de duas hipóteses para catorze. O alarme não diz o que mudou: diz
que mudou, e manda reler antes de confiar em qualquer outro achado da semana.

**Ação penal.** A regra é a pública incondicionada (art. 100 do CP), e a exceção
está escrita no próprio diploma, em fórmulas reconhecíveis ("somente se procede
mediante representação").

**Causas de aumento e diminuição.** Lista o que a lei tem e o catálogo de
modificadores não. Não propõe modelagem: definir sobre quais tipos o aumento
incide não se lê do dispositivo isolado — salvo quando o próprio dispositivo o
declara ("na hipótese do § 10"), e aí é o Proponente, abaixo, que o cadastra.
Desde 28/09/2026 a leitura alcança também "a pena aumenta-se de", "as penas
aumentam-se de" e "pena reduzida de": trinta dispositivos vigentes passaram
anos sem serem acusados porque a fórmula era outra.

**Nome do tipo.** Duas perguntas, em direções opostas: o rótulo conversa com o
próprio dispositivo? E há outro artigo do mesmo diploma com quem ele converse
*mais*? A segunda é o ponto cego da conferência de penas, e já custou caro — o
art. 313 do Código Eleitoral publicou por meses a pena do art. 348, de onde o
nome tinha vindo. Quando dois artigos vizinhos cominam a mesma pena, a troca de
nome é invisível para o Vigia.

:::caution[Falso positivo é esperado aqui]
A heurística é de palavras em comum, e artigos de um mesmo capítulo descrevem
condutas parecidas. Ela serve para leitura, nunca para troca automática. O nome
doutrinário costuma não compartilhar vocabulário com a descrição legal —
"corrupção passiva desportiva" não tem palavra em comum com "solicitar ou aceitar
vantagem", e nem por isso está errado.
:::

**Lastro.** Toda resposta do Auditor sobre violência, grave ameaça ou ação penal cita o
trecho da lei que a decidiu — e confere que o trecho existe no texto lido. Sem lastro, a
derivação não vale: a resposta é zerada, vai para a lista do que pede juízo, e o relatório
diz quantas foram zeradas. Uma regra que citasse o que a lei não tem passaria por leitura;
zerá-la à vista é o que separa comparação de texto de palpite.

### Achado e limite declarado não são a mesma coisa

O Auditor imprime, de propósito, aquilo que **não** garante: registro fora do seu
alcance, hediondez que depende do caso concreto, achado já julgado em rodada
anterior, pendência cuja ação prevista é "nenhuma". Isso aparece no relatório —
um limite que ninguém vê é indistinguível de um achado que nunca apareceu — mas
não conta como trabalho a fazer, e não abre issue.

A distinção é prática: uma issue que chega toda segunda-feira sem nada dentro
ensina a não abrir a issue. E é justamente ela o único lugar onde o achado real
apareceria.

---

## Arquivista — a prosa envelhece como o dado

Um documento que descreve o sistema errado é tão ruim quanto um registro errado,
e envelhece sem avisar. O Arquivista acusa um documento em dois casos: quando
vence o prazo, e quando **um arquivo de que ele fala muda depois da última vez
que alguém o leu**.

Editar conta como ler — a data efetiva é a mais recente entre a conferência
declarada e o último commit do próprio arquivo. Assim só há escrituração manual
quando alguém relê e **não** encontra o que corrigir.

Prazo é relógio; dependência é sinal. A convenção que manda a pena vir de
`pena_min`/`pena_max` ficou meses documentada ao contrário do que o transformador
fazia, e o prazo do documento nem havia corrido.

As datas vêm do histórico do repositório, e **sem histórico ele não afirma nada**. Na
primeira rodada em que voltou a funcionar, em 25/10/2026, a cópia sem histórico da CI
fazia todo arquivo parecer editado naquele dia — e editar conta como ler: os 18
documentos saíram "em dia", com três vencidos. O job passou a baixar o histórico
inteiro, e numa cópia sem histórico o Arquivista se declara sem resposta.

---

## Proponente — o que vira PR sem esperar gente

O Proponente não vigia nada: transforma em **pull request** o que os robôs leram
sem precisar de juízo, e deixa para a issue o que precisa. A régua é uma só —
**leitura de texto, não interpretação** — e hoje ela alcança três coisas:

- **Moldura ou espécie de pena** de um registro que já existe, quando o compilado
  diz outra coisa. É o caso original, e o mais frequente. Um diploma por PR.
- **Sentinela defasada.** A sentinela de uma fonte é a string que prova que a página
  baixada está fresca — em geral, o número da lei mais recente que o compilado
  anota ("Incluído pela Lei nº 15.517, de 2026"). Quando a página passa a anotar lei
  mais nova que a sentinela, o número novo está escrito na própria página, e o
  Proponente o copia. Só troca sentinela que já é número de lei ordinária; a de
  conteúdo — o nome de um tipo, para diploma que ainda não tem emenda — fica. "Vide
  Lei nº …" não conta, porque remissão não prova atualização.
- **Modificador de escopo declarado.** Das causas de aumento e diminuição que o
  Auditor acusa, o Proponente cadastra as que dizem no próprio texto sobre o que
  incidem: "na hipótese do § 10", "a pena prevista no § 2º-A", ou "as penas
  cominadas neste artigo" num artigo que tem uma moldura só no catálogo. Fração e
  direção também vêm do texto. O que não declara alcance continua na issue, como
  pergunta.

Quando alguma dessas mudanças vem de lei recente — redação dada ou dispositivo
incluído por lei deste ano ou do anterior, lido da anotação do compilado —, o PR
escreve a nota de atualização e sobe a versão. Modificador não gera nota: a nota
da lei sai com as linhas. As duas leituras novas entraram em 28/09/2026, quando a
rodada da Lei 15.517/2026 mostrou que tanto a sentinela quanto os §§ 11 e 12 do
art. 155 do Código Penal eram leitura direta e tinham ficado para gente.

**O que ele não faz**, e por decisão: criar ou remover registro (a primeira leva
automática de criação trouxe 29 registros que não eram tipos penais), decidir
hediondez ou espécie de ação penal sem propor, e modelar aumento cujo alcance a
lei não declara. O merge continua sendo de gente.

## Onde cada um mora no código

Cada robô é um sistema próprio, em diretório próprio com o nome dele. O que fica no
**núcleo** é o que dois ou mais precisam aplicar de forma **idêntica** — e essa é a
única razão para algo morar lá.

```
scripts/robos/
  nucleo/        tempo · baixar · parsear · dispositivo · preceito · vigencia · revogacao
  vigia/         conferir · cobertura-limites · excecoes
  sentinela/     dou_watcher
  recenseador/   leis_do_ano
  auditor/       auditar · excecoes-auditoria
  arquivista/    verificar_documentacao
  cotejador/     frescor · textos · vetos · ctresb · historico
  relator/       decisoes
  curador/       triagem · varrer · confirmar · curar
  fontes/        rede · senado · normas · ctresb · cnj      (o transporte: toda requisição passa por aqui)
  proponente/    propor · corrigir · criar        (não é robô: é quem abre o PR — ver acima)
```

Duas peças do núcleo merecem explicação, porque a tentação de duplicá-las é grande e
o custo de ceder já foi pago:

- **`dispositivo`** guarda a normalização que transforma "Art. 121, §2º, I" no
  identificador com que os robôs se entendem. O Vigia confere a moldura contra o
  dispositivo que o registro diz ser, e o Auditor pergunta se o nome conversa com esse
  mesmo dispositivo. Se cada um tiver a sua cópia, os dois divergem em silêncio — e o
  registro passa a existir para um e não para o outro. Foi assim que nasceram artigos
  inexistentes como `Art. 13-O`.
- **`preceito`** guarda o critério que separa lei que cria crime de lei que fala de
  pena. O Sentinela aplica-o ao Diário Oficial da semana; o Recenseador, a todas as
  leis do ano. Comparar os dois resultados só faz sentido se o critério for um só:
  com duas cópias, uma divergência não distinguiria "a lei mudou" de "os filtros
  discordam".

---

## O que nenhum deles alcança

Declarar o limite vale mais que fingir cobertura.

**Decisão de tribunal, fora do que o CNJ guarda.** Uma ADI que declara
inconstitucionalidade não é ato normativo do Diário Oficial, Seção 1 — é publicada no
Diário da Justiça. E altera o catálogo com a mesma força de uma lei revogadora: a ADI
7555 tornou inconstitucional o §3º do art. 232 do Código Penal Militar e deslocou o
estupro de vulnerável praticado por militar para o art. 217-A do Código Penal. O
Relator vê o STF e o STJ no que o banco do CNJ tem, e o banco não tem tudo. Continua
sem robô o **STM**, que é quem julga os registros do Código Penal Militar — hoje o
segundo maior diploma do catálogo (ver [Completude](./completude.md)) — e de quem o banco
do CNJ não guarda nenhum precedente. E continua sem robô a jurisprudência que não é
precedente qualificado: o acórdão comum, que só a pesquisa de cada tribunal alcança.
Está no [README](https://github.com/luccas-amorim/atlaspen/blob/main/README.md#o-que-falta).

**O decreto com força de lei dos governos provisórios.** O Curador lê a lei antiga
que o ctresb/leis tem, e o ctresb não tem os decretos de 1889–1891 e 1930–1934 — o
Código Penal de 1890 é um deles. São 8.193 pelo Senado, e nenhum robô os triou.

**Revogação tácita.** Lei posterior que regula inteiramente a matéria revoga a
anterior sem dizê-lo (LINDB, art. 2º, §1º), e não há sinal textual para isso. A
Lei 7.802/89 foi inteiramente revogada pela Lei 14.785/2023, e a página da lei
antiga, quando o caso foi descoberto, não anunciava isso em lugar nenhum — em
26/10/2026 já anuncia. Depois da LC 107/2001, que exige cláusula
de revogação expressa, o caso virou defeito de técnica legislativa em vez de
regra — mas continua invisível a um robô, e por isso é limite declarado, não
problema perseguido.

**Lei estadual e municipal.** Não existem em matéria penal: a competência é
privativa da União (art. 22, I, da Constituição). Por isso a Seção 1 basta.

**O juízo jurídico.** Nenhum deles decide se um dispositivo é crime
autônomo, se a hediondez alcança um tipo militar por identidade, ou se um nome
está errado. Eles apontam. Quem decide assina.
