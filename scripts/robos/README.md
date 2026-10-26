# O conferidor

Toda segunda-feira, 05:00 de Brasília, o repositório se pergunta se o catálogo
ainda corresponde à lei. Baixa os textos compilados dos diplomas de
`data/fontes.json`, estrutura cada dispositivo, lê as molduras penais, compara
com `static/data/crimes.json` e olha o DOU da semana em busca de lei penal nova.

O resultado sai em dois canais: **uma issue** com tudo que precisa de gente e,
quando há correção inequívoca, **um PR** aberto pelo próprio robô.

É determinístico de ponta a ponta — sem IA, sem inferência. Onde não há leitura
segura, o achado vira pergunta na issue em vez de virar dado.

Desde 25/10/2026 há uma **segunda leitura**: o Senado (API de Dados Abertos) e o
normas.leg.br dizem o que mudou em cada diploma e como a Câmara compila o mesmo
texto; desde a mesma data, o Banco Nacional de Precedentes do CNJ diz o que o STF e o
STJ decidiram na semana. Elas apontam e nunca escrevem — o plano e as decisões estão em
`.superpowers/planos/2026-10-25-fontes-abertas-e-acervo.md`.

## As fontes (`fontes/`)

Toda requisição HTTP dos robôs passa por aqui. A decodificação, não: cada fonte
decodifica o que é seu.

| Arquivo | O que faz |
|---|---|
| `rede.py` | Cabeçalhos, novas tentativas, espera, intervalo mínimo, e a separação entre "não existe" (código HTTP declarado ausente → `None`) e "a rede falhou" (`FalhaDeRede`). Adaptado do ctresb/leis (MIT, aviso em `LICENSE-ctresb-leis.txt`). |
| `senado.py` | A ficha de uma norma (por tipo/número/ano, URN ou código), com as normas posteriores que a tocaram — da união de `vides` e `disps`, porque as duas não chegam sempre juntas — e as anteriores que ela revogou; a lista de leis do ano; os vetos do ano. Traduz a notação do Senado para a chave do histórico. |
| `normas.py` | A ficha JSON-LD do normas.leg.br e o texto de cada versão (`Original`, `Current`). |
| `ctresb.py` | Os commits do ctresb/leis por caminho, pela API do GitHub. Só observação. |
| `cnj.py` | Os precedentes do STF e do STJ no Banco Nacional de Precedentes do CNJ (POST com filtro JSON; os tipos de cada tribunal em `CONSULTAS`): os atualizados desde uma data — que só funciona como `dd/mm/aaaa` — e um precedente por número, com a situação ("Cancelado", "Revisado"…) e o texto sem HTML. Oficial e incompleto; do STM, vazio. |

## Os módulos

| Arquivo | O que faz |
|---|---|
| `baixar.py` | Fetch dos compilados, sobre `fontes/rede.py`. Detecta codificação (BOM → meta → UTF-8 → cp1252) e valida a **sentinela** de cada fonte: a página é gravada em `.html.part` e só é promovida a `<data>.html` quando a sentinela passa — snapshot no caminho canônico significa "conferido", por construção, e o differ nunca compara com texto velho ou truncado. |
| `parsear.py` | HTML → dispositivos (caput, §§, pena, situação, anotação). Fatia o HTML cru: a árvore do Word malformado desloca as fronteiras de parágrafo. |
| `../pena_parser.py` | Lê a moldura. **Compartilhado com `transform_data.py`**, para que catálogo e conferidor leiam a mesma pena do mesmo jeito. |
| `conferir.py` | O differ. Classifica cada achado e escreve DOIS relatórios: `crawler/relatorios/AAAA-MM-DD.md`, completo, id por id, que vai no artifact; e `-resumo.md`, que vai no corpo da issue — lá os limites declarados de cobertura saem como contagem, porque o corpo tem teto de 65.536 caracteres e o despejo empurrava para fora justamente o que pede ação. Ambos abrem dizendo contra que branch e commit a rodada correu. Sai com 3 quando há achados. |
| `derivadas.py` | Desde 28/09/2026, recalcula as linhas de **pena derivada** (aumento, diminuição, dobro, metade de outra moldura): a base é o registro que o `c/c` declara, ou o caput do mesmo artigo — e, se a base não é registro, a moldura que a lei escreve nela, seguindo "na mesma pena" de um salto; a fração é a do texto da lei (`nucleo/fracao.py`, compartilhado com o Proponente). Confere → conta como conferido; diverge → achado `DIVERGENTE-derivada`, com a moldura esperada, que o Proponente corrige como qualquer outra; o que a regra não decide sai como *pede juízo*, com o motivo, e fica no balde `pena_derivada`. Não escreve no catálogo. |
| `vigencia.py` | Vacatio legis e produção de efeitos diferida: nunca propor mudança que ainda não vigora. |
| `revogacao.py` | Revogação total de diploma (banner no topo da página). |
| `corrigir.py` | Correção mecânica de linha existente: moldura e espécie de pena. |
| `propor.py` (sentinelas) | Desde 28/09/2026, troca a **sentinela** de uma fonte quando o compilado já anota lei mais nova que ela ("Incluído pela Lei nº 15.517, de 2026"): o número novo está na própria página. Só sentinela que é número de lei ordinária; a de conteúdo (nomen juris, para diploma sem emenda) fica. "Vide" não conta. |
| `propor.py` (modificadores) | Desde 28/09/2026, propõe **modificador** para o MODIFICADOR-AUSENTE cujo texto declara o alcance — "na hipótese do § 10", "a pena prevista no § 2º-A", ou "neste artigo" em artigo de linha única no catálogo. Fração e direção vêm do texto; o alvo tem de existir no catálogo; no CP, marca `ignora_embutida` quando não há linha derivada. O que não declara alcance continua pergunta na issue. Não escreve nota. |
| `criar.py` | Linha nova. **Não roda no automático** — ver "o que o robô não faz". |
| `propor.py` | Escolhe o diploma da rodada, aplica e monta o corpo do PR. Quando a mudança vem de lei recente (redação dada, ou dispositivo incluído, por lei deste ano ou do anterior, lido da anotação do compilado), escreve a nota — declarando o `alcance` (`tipo`, `atributo` ou os dois) e dizendo em português a direção da mudança — e sobe o patch da versão; correção de dado não vira nota. |
| `auditar.py` | Audita os campos que a conferência de penas não alcança: hediondez (contra `data/hediondos.json`), ação penal, causas de aumento ausentes e nomes — inclusive o nome que descreve MELHOR outro artigo do mesmo diploma, ponto cego da conferência de molduras. |
| `conferir_violencia.py`, `conferir_acao_penal.py` | Os derivadores de `violencia`/`grave_ameaca` e de `acao`, por regra escrita (`scripts/violencia.py`, `scripts/acao_penal.py`). Toda resposta cita o trecho da lei que a decidiu e carrega `fundamento_verificado`: **sem lastro, a derivação não vale** — trecho que o texto não tem zera a resposta, que vai para "pede juízo", e o relatório conta quantas foram zeradas. Não escrevem no catálogo. |
| `dou_watcher.py` | Filtro semanal da Seção 1 do DOU, para achar lei penal **nova e autônoma**. Só lei ordinária e lei complementar, pela reserva legal — MP, lei delegada, decreto-lei e emenda não criam tipo penal. Baixa o texto INTEGRAL de cada uma — não há mais pré-filtro por vocabulário — e tria em três níveis pelo preceito secundário, que inclui a pena por remissão ("nas mesmas penas", "metade da pena"). O descartado sai nomeado, não some, e o integral fica no JSON da rodada para permitir retriagem quando o critério mudar. |
| `leis_do_ano.py` | A defesa contra o falso NEGATIVO. Uma vez por mês, confronta a lista de leis sancionadas do ano (no Planalto, que é a FONTE) com o que o watcher examinou. O que sobra é a lista de leis que ninguém olhou. Não classifica: só aponta. Se a lista não puder ser lida, não afirma nada — reportar zero sem ter lido seria o silêncio que ele existe para quebrar. |
| `cotejador/frescor.py` | O compilado anota as leis recentes que o Senado registra para o diploma? A que falta vira pergunta, com prioridade para a que toca registro do catálogo; a superada por lei posterior no mesmo dispositivo sai em lista à parte. Lê, pela `urn` de `fontes.json`, a ficha do Senado. |
| `cotejador/textos.py` | A moldura de cada dispositivo no Planalto contra a da compilação da Câmara (normas.leg.br), com o mesmo `parsear` e o mesmo `pena_parser`. |
| `cotejador/vetos.py` | Os vetos do ano a matérias que citam diploma vigiado, e quais ainda tramitam. Só informa. |
| `cotejador/ctresb.py` | O que mudou na semana nos `scripts/` do ctresb/leis, na jurisprudência do STF e do STJ que ele reúne e nos arquivos dos nossos diplomas. Só informa. |
| `relator/decisoes.py` | O Relator: os precedentes do STF e do STJ atualizados na semana que tocam diploma vigiado — pelo ato impugnado codificado (controle concentrado) ou pela citação, pelo nome ou pela sigla no texto (tema e súmula) —, com a natureza como pista (a situação da súmula e do tema primeiro, o texto depois), os registros do catálogo e os atributos penais tocados. Súmula penal que muda de alcance sem citar diploma também entra. Cada tribunal é lido à parte. Sai com 3 quando há o que ler, 2 quando o CNJ não respondeu. Não escreve no catálogo. |
| `cotejador/historico.py` | Sob demanda: `data/historico-legislativo.json` contra o registro do Senado, nos dois sentidos. |
| `acervo/candidatos.py` | Sob demanda: os dispositivos revogados dos compilados e os diplomas revogados no todo que o acervo ainda não tem, cada um com o nível de prova de que era crime (pena no compilado, pena no original, pede juízo). **Não escreve no acervo.** |
| `excecoes.json` | O que já foi julgado e decidido na conferência de PENAS. Sem isso o relatório repetiria para sempre os mesmos achados. |
| `cotejador/excecoes-cotejo.json` | O mesmo, para o frescor do Cotejador: a lei que o compilado não anota porque não deu redação nova (remissão, suspensão temporária), julgada contra o texto da lei. Lei que deu redação nova e falta no compilado nunca vira exceção. A que deixa de casar sai, e a issue avisa. |
| `excecoes-auditoria.json` | O mesmo, para a auditoria de classificação. Arquivo próprio porque as chaves são outras: ora o id do registro, ora o dispositivo do compilado. |
| `cobertura-limites.json` | Quantos registros o conferidor aceita **não** garantir, por motivo. Crescer é regressão e vira achado; encolher vira convite a apertar. É a trava contra a falha que mais dói aqui — a silenciosa: registro que sai da conferência não aparece como divergente, aparece como nada. |
| `../verificar_documentacao.py` | Saúde da prosa: documento vence por prazo ou porque algo de que ele fala mudou depois da última conferência. |
| `tempo.py` | A data de Brasília. O runner roda em UTC, e sem isso a rodada das 21h se datava de amanhã. |

## Rodar à mão

```bash
python scripts/robos/nucleo/baixar.py --todas          # ou --fonte cp
python scripts/robos/vigia/conferir.py                # relatório de tudo
python scripts/robos/vigia/conferir.py --carimbar     # + trilha em data/conferencia.json
python scripts/robos/vigia/conferir.py --atualizar-limites   # regrava a trava de cobertura
python scripts/robos/proponente/propor.py                  # o PR que sairia (não escreve)
python scripts/robos/sentinela/dou_watcher.py --dias 8
python scripts/robos/recenseador/leis_do_ano.py             # o que o watcher nao viu
python scripts/robos/cotejador/frescor.py                    # o compilado anota o que o Senado registra?
python scripts/robos/cotejador/textos.py --fonte cp          # moldura do Planalto x da Câmara
python scripts/robos/cotejador/vetos.py                      # vetos do ano que tocam diplomas vigiados
python scripts/robos/cotejador/ctresb.py                     # o que mudou no ctresb/leis (GITHUB_TOKEN ajuda)
python scripts/robos/cotejador/historico.py --fonte lep      # historico-legislativo.json x Senado
python scripts/robos/acervo/candidatos.py                    # candidatos ao acervo histórico
python -m pytest scripts/robos/tests            # sem rede, contra fixtures
```

O workflow também roda sob demanda: aba **Actions** → "Conferidor semanal" →
**Run workflow**, com opção de não abrir PR e de incluir linhas novas.

## O que o robô faz e o que não faz

**Faz**, sozinho, direto na `main`: carimba a trilha de auditoria
(`data/conferencia.json` → `fonte`, `conferido_em` e `conferido_resultado` no derivado).
É registro do que a máquina fez, não proposta de mudança de dado.

**Faz**, sozinho, em PR: corrigir moldura ou espécie de pena de linha que já
existe, quando o compilado diz outra coisa; trocar a sentinela de uma fonte pela lei
mais nova que a página anota; e cadastrar o modificador cujo dispositivo declara
fração e alcance ("na hipótese do § 10") — as duas últimas desde 28/09/2026, depois
que a rodada da Lei 15.517 mostrou que eram leitura de texto e ficavam para gente.
Um diploma por rodada (as sentinelas vão todas juntas, de qualquer fonte), um PR
aberto por vez, evidência por mudança. Se alguma mudança vem de lei recente, o PR escreve a nota
(uma por lei e por direção da mudança, que é como ele as agrupa) e fecha uma versão,
em `0.0.x` até o lançamento; se tudo é correção de dado, não escreve nota nem sobe versão,
e o corpo do PR diz por quê.

**Faz**, em PR que PEDE JUÍZO: as mudanças de hediondez e ação penal, com o fundamento ao lado, e a entrada de `data/fontes.json` para lei nova que pareça criar tipo penal. Só sai quando não há correção de pena pendente — uma coisa por rodada.

**Não faz**: criar nem remover linha. Criar exige decidir se o dispositivo é
crime autônomo, causa de aumento ou nada; remover exige decidir o destino da URL
pública. `criar.py` existe e é útil, mas rodado por gente — a primeira leva
automática dele (v1.3.0) trouxe 29 registros que não eram tipos penais vigentes,
e foi preciso retirá-los na v1.4.0.

## As armadilhas que já custaram caro

Cada uma tem teste e fixture; nenhuma volta em silêncio.

1. **Texto citado.** O compilado transcreve, embaixo do artigo alterador, a
   redação dada à lei alterada — e congelada na data da alteração. A Lei 8.137
   "contém" o art. 172 do CP; a Lei 12.850 "contém" o art. 288. Duas formas de
   detectar: o texto do caput ("passa a vigorar…") e o número fora de sequência
   ("Art. 24, Art. 288, Art. 25").
2. **Espécie que não é pena.** Preceito que começa por "Pena - multa" é multa,
   mesmo que fale em suspensão ou fechamento depois do ponto e vírgula.
3. **Revogação que mantém o texto.** A LCP não apaga o corpo do artigo revogado:
   anota a revogação ao lado.
4. **Espécie alternativa.** "reclusão ou detenção, de um a três anos" é uma
   moldura com duas espécies, não duas molduras.
5. **Rótulo pela lei criadora.** Artigos do CP aparecem com `lei="Lei 14.811/24"`.
   O vínculo diploma → rótulos vem de `fontes.json`, nunca do campo `lei` cru.
6. **Comparar com o DERIVADO.** A moldura que a aplicação usa é
   `pena_*_meses`, do derivado — os campos crus da fonte podem estar velhos.
7. **Codificação.** O acervo do Planalto mistura cp1252 e UTF-16 com BOM.
   "Página parece desatualizada" quase sempre é erro de decodificação.
8. **`Art . 190`**, com espaço antes do ponto, é como a Lei 6.766 escreve do
   art. 37 em diante.
9. **Sufixo de letra.** Vem colado ao número, pode repetir-se (`359-M-B`) e pode
   vir depois do ordinal (`2º-A`). Sem as duas formas, o `2º-A` da Lei 7.716
   (injúria racial) virava corpo do art. 2º, que está vetado, e o `359-M-B` do
   CP virava corpo do golpe de Estado. Em contrapartida, `Art. 13 - O resultado`
   **não** tem sufixo: ali o hífen é pontuação e o `O` é artigo definido — foi
   assim que nasceram artigos inexistentes como `Art. 13-O` e `Art. 100-A`. A
   regra que separa os dois casos é o espaço em volta do hífen, e ela precisa
   valer igual em `parsear.py` e na `chave()` de `conferir.py`: os dois lados
   têm de reduzir ao MESMO identificador, senão o registro existe e não é
   conferido.

## Acrescentar um diploma

Uma entrada em `data/fontes.json` (`id`, `rotulos`, `url` do compilado, `urn`
LexML — conferida contra o nome e a ementa da ficha do Senado, porque URN errada
aponta para outra norma sem quebrar nada —, e `sentinela`, uma string que prova
que a página está fresca). O conferidor passa
a vigiá-lo na rodada seguinte, e o watcher do DOU passa a reconhecer citações a
ele. Todo rótulo distinto de `data/crimes.json` precisa constar de exatamente um
diploma.
