# Como contribuir — AtlasPen

## Visão geral

- **Fonte canônica do catálogo:** `data/crimes.json` (uma entrada por tipo penal).
- **Catálogo consumido pelo site:** `static/data/crimes.json` — **gerado** por
  `scripts/transform_data.py`. Não edite à mão; ele é regenerado a cada mudança da fonte.
- **Campos derivados** (`pena_privativa`, `tem_multa`, `multa_regime`,
  `infracao_menor_potencial`, `pena_min_meses`, `pena_max_meses`, rótulos de exibição)
  são produzidos pelo transformador a partir de `data/crimes.json`.

## Glossário

Quatro termos têm sentido fixo no projeto (decisão de 10/09/2026):

- **Tipo penal** — a unidade do catálogo: o dispositivo que comina moldura de pena própria
  (ver C1).
- **Atributo penal** — o instituto que a lei liga ao tipo e à pena: transação, ANPP,
  substituição, progressão, prescrição… O site os chamava de "benefícios penais".
- **Parâmetro** — o patamar, a fração ou a vedação editável de um atributo: o teto de 2
  anos da transação, os 25% da progressão.
- **Campo** — o campo do registro de tipo penal: `hediondo`, `acao`,
  `perdao_judicial_previsto`.

"Benefício" continua só onde é a palavra da própria lei ou de súmula ("beneficiado", a
Súmula 715 do STF). Trocá-la aí seria adulterar a citação.

## Como o catálogo é atualizado

A carga inicial veio de uma planilha; a manutenção, hoje, é o **conferidor** — um pipeline
determinístico, sem IA, descrito em [`scripts/robos/README.md`](scripts/robos/README.md).

1. **Toda segunda-feira, 05:00 de Brasília**, o workflow `conferidor.yml` baixa o texto
   compilado dos diplomas de `data/fontes.json`, compara pena a pena com o catálogo e olha
   os atos normativos da Seção 1 do Diário Oficial da semana. Desde 25/10/2026 pergunta
   também ao Senado e à compilação da Câmara se o próprio compilado está em dia — só
   pergunta: nada que vem de lá escreve no catálogo.
2. **O que diverge vira issue.** Cada achado é uma pergunta, não uma conclusão.
3. **O que é leitura direta vira PR**, aberto pelo próprio robô (`atlaspen-automacao[bot]`):
   moldura ou espécie de pena de um registro que já existe divergindo do que a lei comina;
   a sentinela de uma fonte, quando o compilado já anota lei mais nova; e o modificador cujo
   dispositivo declara fração e alcance ("na hipótese do § 10") — estes dois desde
   28/09/2026. Um diploma por rodada, um PR aberto por vez, evidência ao lado de cada mudança.
4. **O que exige juízo continua humano:** criar registro, remover registro, decidir se um
   dispositivo é tipo autônomo, causa de aumento ou nada disso. O merge do PR também.

> Em resumo: **a máquina confere e propõe; gente decide e aprova.** Nada entra no catálogo
> sem conferência contra o texto compilado do Planalto.

## Passos de uma atualização (PR)

1. Edite **apenas** `data/crimes.json` (a fonte) — direto na interface do GitHub ou local.
2. Regenere o derivado (duas opções):
   - **Automático (GitHub):** ao abrir/pushar a mudança em `data/crimes.json` na branch
     `main`, o workflow `Regenerar dados derivados` roda o transformador e **commita**
     `static/data/crimes.json` de volta. Não precisa rodar Python localmente.
   - **Local:** `python3 scripts/transform_data.py` e commit do `static/data/crimes.json`.
3. Abra um Pull Request. O CI valida, nesta ordem:
   - `transform_data.py --estrito` — convenções C1, C2, C3 e o teto de contradições (C4);
   - se o derivado commitado corresponde à fonte;
   - `npm run typecheck`;
   - `npm run mortos` — código morto: arquivo que ninguém importa, exportação sem uso,
     dependência não listada (as exceções, com motivo, estão em `knip.jsonc`);
   - `npm run verificar` — invariantes do motor de atributos, casos-âncora de direito penal
     contra o catálogo real e a tabela de casos-padrão (`scripts/verificar_casos.ts`: tipo
     real, premissa explícita, veredito esperado e o dispositivo que o sustenta);
   - `npm run build`.

### Correções finas (multa e afins)

Ajustes que a heurística não acerta devem ir em `CORRECOES`, dentro de
`scripts/catalogo/tabelas.py` (chaveado por `id`), e **não** no JSON gerado.
Exemplo presente: Art. 227 do CP (a multa só incide na hipótese do §3º).

## Versão e notas

> **Até a v1.0.0 a versão anda em `0.0.x`** (decisões de 10/09/2026 e de 14/09/2026). O
> feed de notas já registra as alterações de lei, com a mesma régua de sempre; o que fica
> para o lançamento é a Release no GitHub, que o `release.yml` só publica a partir da
> v1.0.0.

Cada versão publica **duas coisas a partir dos mesmos arquivos**: a nota no site, em
`/notas`, e, depois da v1.0.0, a Release no GitHub. As notas registram **exclusivamente**
alterações de lei que criem, modifiquem ou extingam tipos penais ou atributos penais;
correção de dado do catálogo não vira nota.

1. **Cada alteração dessas vira uma entrada** em
   `src/data/changelog/entries/<ano>/<id>.ts`, um arquivo por mudança, texto puro, com
   `alcance` (`tipo`, `atributo` ou os dois) e `version`. O passo a passo está em
   [`src/data/changelog/create-changelog-entry.md`](src/data/changelog/create-changelog-entry.md).
2. **A versão segue a [regra de versionamento](docs/dados-abertos.md#estabilidade-e-versionamento):**
   correção sobe o último número; funcionalidade nova compatível, o do meio; quebra de
   contrato, o primeiro.
3. **O PR que fecha a versão sobe `version` em `package.json` e no lockfile.** O
   `CITATION.cff` não tem campo de versão: até a v1.0.0 cita-se pela data. Ao mergear
   na `main`, o `release.yml` monta o corpo com as entradas da versão, **cria a tag `vX.Y.Z`
   e publica a Release**. **Não faça `git push` de tag manual.**

## Convenções do catálogo

**Estas regras valem para qualquer origem de atualização — IA, scraper do DOU ou
correção humana.** Várias são impostas por `scripts/transform_data.py`, que **falha o
build** quando violadas; as demais dependem de disciplina de quem escreve.

### C1. O catálogo contém APENAS tipos penais ⛔ imposta

Um registro = um tipo penal. **Não** entram no catálogo:

- notas de referência ("a LGPD não tipifica crimes específicos");
- agravantes e atenuantes (art. 61 a 66, CP);
- causas de aumento e diminuição (art. 141, CP; art. 258, CP);
- excludentes de ilicitude (art. 128, I e II, CP);
- causas de extinção da punibilidade em si (art. 121, §5º — o perdão judicial é
  campo do tipo (`perdao_judicial_previsto`), não um tipo);
- regras de ação penal (art. 171, §5º, CP — isso é o campo `acao`);
- **regras de punibilidade** ("é punível a calúnia contra os mortos", art. 138, §2º;
  "a receptação é punível ainda que desconhecido o autor do crime de que proveio a
  coisa", art. 180, §4º) — não cominam pena;
- **extinção ou redução da punibilidade pela reparação do dano** (art. 312, §3º) — a
  primeira metade é causa extintiva; só a segunda produz moldura, e é ela que vira
  registro;
- **efeitos da condenação** — perda do cargo, inabilitação (art. 92 do CP; DL 201/67,
  art. 1º, §2º). Não é pena, é consequência;
- **regras de presunção** (art. 236 do CPM) — definem elementar, não cominam nada;
- **regras de conversão ou de execução da pena** (art. 9º, parágrafo único, da LCP:
  conversão da multa em prisão simples). Parece moldura e não é — opera na execução,
  não na cominação;
- **definições legais e normas interpretativas** (arts. 22 a 27 do CPM: quem é militar,
  o que é navio);
- **regras de cúmulo** ("aplica-se, além da pena da violência, a do crime contra a
  pessoa" — CPM, arts. 157, §3º e 158, §2º). É concurso material, e quem o modela é a
  tela de concurso, não um registro;
- **cabeça de artigo ou de parágrafo que não comina pena** (art. 400 do CPM; art. 408,
  parágrafo único) — a moldura é do inciso ou da alínea, e o registro é do inciso.

21 registros assim foram removidos na v1.1.0: com pena zero, satisfaziam qualquer teto e
eram contados como "cabíveis" em transação penal, ANPP e sursis, inflando as estatísticas.

#### O teste que decide: comina moldura, ou deriva de uma?

O critério antigo perguntava se o dispositivo descrevia **conduta autônoma** — verbo
nuclear e objeto, prática isolada possível, concurso de crimes com os vizinhos. Ele
errava, porque testava autonomia de conduta quando o que o catálogo indexa é **moldura
de pena**: a lesão corporal seguida de morte não pode ser praticada isoladamente e não
gera concurso com a lesão — e, no entanto, tem moldura própria de 4 a 12 anos e
obviamente precisa de registro. A terceira pergunta ainda era circular: "gera concurso"
é consequência de serem dois tipos, não critério para saber se são.

São dois passos, nesta ordem:

1. **Moldura.** O dispositivo comina ou determina moldura própria — mínimo, máximo e
   espécie? Se sim, **é registro**. Isso cobre de uma vez o caput, a forma qualificada
   pelo resultado, a privilegiada, a culposa e o inciso com pena autônoma.
2. **Derivação.** Se não comina, mas remete a outra moldura ou opera fração sobre ela:
   é registro **derivado**, e vale a regra de **um registro por moldura-base**. Base
   única, um registro; se alcança caput e parágrafos, um por parágrafo alcançado.

Não cominando nem determinando moldura alguma, **não é registro** — é modificador, ou
cai numa das exclusões acima. O teste foi aplicado aos 96 registros criados na v2.0.0 e
não produziu caso ambíguo.

> Causas de aumento/diminuição abstratas são **entidade própria** da dosimetria por fases,
> em `data/modificadores.json` (3ª fase, art. 68 do CP) — não tipos penais.

### C2. Todo tipo declara uma sanção ⛔ imposta

Pena privativa em `pena_min`/`pena_max`, **ou** `sancoes_nao_privativas` quando o tipo não
comina prisão — como o art. 28 da Lei 11.343/06 (porte para consumo):

```json
"sancoes_nao_privativas": [
  {"inciso": "I", "sancao": "Advertência sobre os efeitos das drogas"},
  {"inciso": "II", "sancao": "Prestação de serviços à comunidade"},
  {"inciso": "III", "sancao": "Medida educativa de comparecimento a programa ou curso educativo"}
]
```

**Ou** `pena_por_remissao`, quando o tipo não comina moldura própria porque importa a de
outro dispositivo — o art. 304 do CP pune o uso com "a pena cominada à falsificação":

```json
"pena_por_remissao": {
  "dispositivo_fonte": "CP, arts. 297 a 302",
  "lei_fonte": "CP",
  "artigos_fonte": ["Art. 297", "Art. 298", "Art. 299", "Art. 300", "Art. 301", "Art. 302"],
  "operador": "nenhum",
  "fracao": null
}
```

O `operador` é `nenhum`, `aumento` ou `diminuicao`; os dois últimos exigem `fracao`, e seguem
a dosimetria: `diminuicao` com `1/3` multiplica a moldura de origem por 2/3. `lei_fonte` e
`artigos_fonte` apontam os registros de origem, e toda origem tem de ter moldura. O motor
avalia o tipo com a moldura de cada origem: o veredito é o comum, ou "depende" quando elas
divergem. Quando o catálogo já desdobra a remissão em registros "c/c" (Lei 2.889/56, arts.
2º e 3º), são os desdobrados que contam nas estatísticas, e não o registro de remissão. Quem
declara remissão **não publica moldura própria**: seriam duas respostas para a mesma
pergunta, e o build reprova. A razão de o estado existir é que as duas saídas anteriores
erravam — publicar a moldura de um dos dispositivos-fonte afirma como certa uma pena que
depende do caso, e deixar em branco é indistinguível de campo não preenchido.

Sem nenhum dos três, o build falha — é sinal de que o registro não é tipo penal (C1) ou de
que falta dado.

### C3. `id` é append-only ⛔ imposta

O `id` é a **URL pública** de cada tipo (`/tipos/N`) e o site está publicado.

- Id novo = `max(id em uso, id aposentado) + 1`. Nunca no meio, nunca renumerando.
- Id removido vira **buraco permanente** e entra em `data/ids-aposentados.json`; jamais é
  reatribuído a outro dispositivo — um link antigo passaria a apontar para o crime errado,
  falha silenciosa. Contar só o `max` em uso não basta: remover o topo da numeração faz o
  máximo cair, e o próximo id repetiria um endereço já usado. `--estrito` reprova isso.
- A numeração foi **reiniciada duas vezes**, as duas por decisão explícita do mantenedor:
  na v1.4.0 (1 a 1.412), com o projeto ainda em protótipo, e na v2.0.0 (1 a 1.505), ao
  fim da revisão que fechou a conferência da base. Reiniciar quebra todo link externo e
  obriga a versão a ser MAIOR; quem o fizer precisa remapear na mesma passada **tudo** o
  que é indexado por id — `data/conferencia.json`, as tabelas `CORRECOES_*` de
  `scripts/catalogo/tabelas.py`, os `ids` de `scripts/robos/auditor/excecoes-auditoria.json` e os links
  `?tipo=N` das notas já publicadas. Não é decisão de quem edita o catálogo.

### C4. Um registro por dispositivo

A chave é `lei + artigo`. Repetir o mesmo dispositivo cria uma **duplicata**; se as cópias
divergirem em pena ou hediondez, cria uma **contradição** — o catálogo passa a afirmar
duas penas para o mesmo artigo.

As 42 contradições herdadas foram **todas resolvidas** contra o texto compilado. A CI roda
`--max-contradicoes=0`: o catálogo não pode regredir.

Para distinguir incisos do mesmo parágrafo, use o inciso no `artigo`
(`Art. 121, §2º, I`), nunca dois registros com `Art. 121, §2º`.

### C5. O nome do tipo é dado, não rótulo

`crime` alimenta derivação automática. Em especial, **`resultado_morte` é derivado do
nome** (art. 112, VI e VIII, LEP → frações de 50% e 70%).

- Diga no nome quando o tipo for qualificado pela morte: *"Lesão corporal seguida de
  morte"*, *"Latrocínio"*, *"Extorsão com resultado morte"*.
- **Não** confie no `obs` para isso: ele descreve os demais parágrafos do artigo ("se
  resulta morte, triplica"), e por isso é ignorado nessa derivação — do contrário, o art.
  135 (omissão de socorro) seria marcado indevidamente.

### C6. `hediondo` inclui os equiparados, e a espécie diz qual é qual ⛔ imposta

Tráfico, tortura e terrorismo entram como `hediondo: "Sim"` — é o que aciona as vedações
do art. 5º, XLIII, da CF (graça, indulto, anistia). Exceções consolidadas ficam como
`"Não"`: tráfico privilegiado (art. 33, §4º — STF, HC 118.533) e associação para o
tráfico (art. 35).

**A espécie e o fundamento não se digitam.** `hediondo_especie`
(`natureza | equiparado | nao`) e `hediondo_fundamento` são **derivados** da tabela curada
`data/hediondos.json` por `scripts/hediondez.py`, que o construtor do catálogo e o Auditor
compartilham. Hediondo **por natureza** é o do rol do art. 1º da Lei 8.072/90, que é
taxativo; **equiparado** é a extensão de regime da Constituição, que não torna o crime
hediondo.

Daí uma regra dura: **`hediondo: "Sim"` sem regra na tabela reprova na CI**
(`validar_hediondez`). Para marcar um tipo como hediondo, escreva antes a regra, com o
inciso do rol no `fundamento`. Foi assim que se descobriu, em 19/09/2026, que oito
registros militares afirmavam hediondez sem nada que a sustentasse — e que dois deles não
se sustentavam.

### C7. A faixa de pena vem de `pena_min`/`pena_max` ⛔ imposta

Os dois campos, **em meses**, são a autoridade: é deles que saem a moldura publicada e
todo o cálculo de atributos. O `obs` é descritivo — escreva nele a faixa na unidade
natural ("15 dias a 6 meses", "1-5 anos") para quem lê, mas **ele não define pena**.

Foi o contrário até a v1.2.16, e o preço apareceu: a moldura era extraída do texto do
`obs` por expressão regular, e uma frase secundária mudava a pena publicada — o art. 32,
§1º-A da Lei 9.605 exibia "3 meses a 1 ano" porque o `obs` mencionava a pena antiga.

Regras verificadas a cada build: `pena_min <= pena_max`, e inteiro escrito como inteiro
(`24`, não `24.0`).

**Tipo sem pena mínima.** Nem todo tipo comina os dois extremos. Vários só têm teto —
"reclusão, **até** oito anos" (Lei 6.538/78, arts. 36 a 42). Nesses casos `pena_min` é `0`
e o rótulo sai como "até 8 anos". **Zero na mínima não é "sem pena"**: o tipo é punível,
apenas não tem piso cominado — e, por isso, os atributos que dependem da pena mínima (ANPP,
suspensão condicional do processo) são-lhe os mais favoráveis possíveis. Não preencha a
mínima com um chute.

**Mas antes de escrever `0`, leia a parte geral do diploma.** Vários códigos fecham essa
lacuna por conta própria, e aí o mínimo existe — só não está no preceito:

> **Código Eleitoral, art. 284.** "Sempre que este Código não indicar o grau mínimo,
> entende-se que será ele de quinze dias para a pena de detenção e de um ano para a de
> reclusão."

O **CPM, art. 58**, diz o mesmo (um ano na reclusão, trinta dias na detenção). Por isso os
25 registros do Código Eleitoral cuja lei diz só "reclusão até cinco anos" saem com
`pena_min_meses` 12, e não 0 — e estão certos. Zero fica para quem **não** tem regra de
fechamento, como a Lei 6.538/78. Quem escrever `0` num diploma que tenha art. 284 não está
deixando de chutar: está apagando um mínimo que a lei fixa.

*(Esta ressalva entrou em 24/09/2026. Até então a C7 dava como exemplo de `pena_min = 0`
cinco artigos do Código Eleitoral — 289, 290, 300, 301 e 309 —, que são exatamente os que o
art. 284 alcança, e o art. 32 da LCP, que não tem pena privativa nenhuma. Seguir o texto
antigo estragaria 25 registros corretos.)*

Não confunda com o **tipo sem pena privativa** (C2), que não tem prisão alguma.

### C8. Perdão judicial é lista curada, não inferência

Não existe perdão judicial genérico e ele não se estende por analogia (art. 107, IX, CP).
Um tipo novo que o admita exige entrada em `PERDAO_JUDICIAL`, no
`scripts/transform_data.py`, **com revisão humana** — nenhuma automação deve inferi-lo do
elemento culposo.

---

## Schema de `data/crimes.json`

| campo | tipo | observação |
|-------|------|------------|
| `id` | inteiro único | append-only; é a URL pública (C3) |
| `lei` | texto | diploma (ex.: "CP", "Lei 11.343/06") |
| `artigo` | texto | ex.: "Art. 155, caput"; com inciso quando houver (C4) |
| `crime` | texto | nome do tipo — **alimenta `resultado_morte`** (C5) |
| `pena_min` | inteiro | **em meses**; é a autoridade da moldura (C7) ⛔ imposta |
| `pena_max` | inteiro | **em meses**; é a autoridade da moldura (C7) ⛔ imposta |
| `sancoes_nao_privativas` | lista | só quando não há pena privativa (C2) |
| `pena_por_remissao` | objeto | opcional; `{dispositivo_fonte, lei_fonte, artigos_fonte, operador, fracao}` quando a moldura é a de outro dispositivo (C2). Incompatível com `pena_min`/`pena_max` |
| `tipo_pena` | texto | Reclusão / Detenção / Prisão simples / Multa / Morte / Outras penas / — |
| `acao` | vocabulário fechado | a espécie da ação penal: Pública Incondicionada; Pública Condicionada à Representação; Pública Condicionada à Requisição; Ação Penal Privada; Ação Penal Privada Personalíssima ⛔ imposta |
| `hediondo` | Sim / Não | inclui equiparados; a espécie e o fundamento são derivados da tabela (C6) |
| `hediondo_condicao` | texto | opcional. A hediondez depende de circunstância do CASO; com ela, `hediondo` fica "Não" ⛔ imposta |
| `hediondo_nota` | texto | opcional. Divergência de **jurisprudência ou doutrina** sobre a hediondez. Não é condição do fato: o tipo não muda com o caso, muda com quem julga |
| `acao_condicao` | texto | opcional. A espécie da ação penal depende do caso (art. 182 do CP, art. 161, §3º) |
| `elemento` | vocabulário fechado | Doloso / Culposo / Preterdoloso / **Qualificado pelo resultado**. A régua está no `AGENTS.md`, e ela decide a tentativa (decisões 20 e 31) ⛔ imposta |
| `tentativa` | Sim / Não / — | pressuposto do art. 15 do CP. Preterdoloso e culposo não a admitem; "Qualificado pelo resultado" admite ⛔ imposta |
| `violencia` | Sim / Não / — | violência **dolosa contra pessoa**, como meio ou como núcleo. Contra a coisa não conta (CP, art. 44, I) |
| `grave_ameaca` | Sim / Não / — | a grave ameaça como meio do tipo |
| `violencia_condicao` | texto | opcional. O tipo se consuma SEM violência mas comporta a hipótese violenta — sequestrar pode ser obtido por fraude. Com ela, `violencia` fica "Não", e o motor mostra os atributos nas duas hipóteses ⛔ imposta |
| `vigencia_ate` | data | opcional (AAAA-MM-DD). Desde quando o dispositivo NÃO vigora mais |
| `vigencia_nota` | texto | **obrigatória** com `vigencia_ate`: o que houve e qual dispositivo passa a reger a conduta |
| `obs` | texto | descrição / notas. Escreva nele a faixa na unidade natural ("15 dias a 6 meses", "1-5 anos") para quem lê — mas **ele não define pena** (C7) |

Campos derivados (não escreva à mão): `pena_privativa`, `tem_multa`, `multa_regime`,
`pena_*_meses`, `pena_*_rotulo`, `pena_faixa_rotulo`, `infracao_menor_potencial`,
`tem_pena_privativa`, `resultado_morte`, `perdao_judicial_previsto`, `vigente`,
`chave_dispositivo`, `duplicata*`. Ver [Catálogo de tipos penais](docs/catalogo-tipos-penais.md).

### Unidades de pena (dias / meses / anos)

A moldura canônica é **em meses** (`pena_min_meses`/`pena_max_meses`, contando o mês
como 30 dias — Art. 11 do CP) e sai de `pena_min`/`pena_max`. O transformador lê o
`obs` apenas para saber em que **unidade** a lei escreveu — dias, meses ou anos —, e
com isso monta os rótulos de exibição
(`pena_min_rotulo`/`pena_max_rotulo`/`pena_faixa_rotulo`). Assim "15 dias a 6 meses"
aparece na unidade em que foi cominada e é calculado sem inverter mínimo e máximo.

> Regra de consistência, verificada a cada build: `pena_min_meses <= pena_max_meses`.
> Texto no `obs` que discorde dos dois campos não muda a pena publicada — foi o
> contrário até a v1.2.16, e o preço está contado na C7.

## Desenvolvimento

```bash
npm install
npm run dev         # dev server
npm run typecheck
npm run mortos      # código morto (knip)
npm run verificar   # motor de atributos × catálogo real
npm run build
python3 scripts/transform_data.py   # regenera static/data/crimes.json + qualidade.json
python3 scripts/transform_data.py --estrito --max-contradicoes=0   # como na CI
python3 scripts/validar_atributos.py   # base dos atributos e histórico legislativo
npm run atributos   # regenera static/data/atributos.json (depois do transform)
```
