# F0 — Decisões do spike (29/07/2026)

Registro do spike que abriu o conferidor: experimentos executados ao vivo contra
o Planalto em 29/07/2026, com as evidências citadas abaixo. Fica aqui porque
explica **por que** o fetcher é como é — inclusive uma conclusão que se provou
errada e foi corrigida. O funcionamento do pipeline está em
`scripts/robos/README.md`.

## 1. Estratégia de fetch — **HTTP simples basta** (corrigido na F1)

> ⚠️ **Correção (30/07/2026).** A conclusão original desta seção — "o CDN serve
> cópias arcaicas, Playwright é obrigatório" — **estava errada**, e a causa foi
> um erro meu de decodificação, não o Planalto. Registro mantido porque o erro
> é instrutivo.

O que de fato acontece:

| Experimento | Resultado |
|---|---|
| `curl` **sem** User-Agent | **Recusado** (resposta vazia) — UA de navegador é obrigatório. |
| `curl` com UA — CP, CPM, 9.605, 8.137 | Página **atual** (15.384/14.688/15.355/LC 224 presentes). |
| `curl` com UA — **Lei 11.340** | Parecia **pré-2018** (sem 24-A)… porque eu a decodifiquei como cp1252. Ela vem em **UTF-16 LE com BOM**. Decodificada certo, tem 24-A, 13.641, 14.994 e 15.383 — **está atual**. |
| **F1: as 62 fontes** via `urllib` + UA + detecção de charset | **62/62 íntegras**, todas com a sentinela presente. |

Conclusões (agora com as 62 fontes como evidência, não 5):

- **Fetcher usa HTTP puro da biblioteca padrão** (`urllib`), sem Playwright e
  sem dependência externa. Mais simples, mais rápido e sem browser na CI.
- **UA de navegador é obrigatório** (sem ele, conexão recusada).
- **Sentinela por fonte continua obrigatória** — e provou seu valor: foi ela que
  expôs tanto o erro de encoding quanto uma URL errada, em vez de deixar o
  conferidor comparar contra texto corrompido.

**Lição de método:** "página parece desatualizada" é sintoma ambíguo — antes de
culpar a fonte, verificar a decodificação. Um `decode()` errado corrompe em
silêncio e imita perfeitamente conteúdo velho.

## 2. Encoding — **heterogêneo; detectar sempre** (decidido)

O acervo mistura codificações e **não declara nenhuma**: sem `<meta charset>` e
sem charset no `Content-Type`. Medido nas 62 fontes: **61 windows-1252 e 1
UTF-16 LE com BOM** (Lei 11.340). Ordem de detecção implementada em
`scripts/robos/nucleo/baixar.py`: **BOM** → `meta charset` → UTF-8 → cp1252.

Duas armadilhas concretas encontradas:
1. UTF-16 **sem** detecção de BOM vira mojibake que passa por texto antigo;
2. o UTF-16 do Planalto vem com **um byte solto no fim** (quebra o decode
   estrito com "truncated data") — descartar o byte ímpar final.

Os snapshots são gravados **normalizados em UTF-8**, para que o resto do
pipeline (F2+) nunca mais lide com codificação.

## 3. Estrutura HTML (levantamento no CP compilado atual)

1. **Anotações são links estruturados** — ex.:
   `<a href="../_Ato2023-2026/2026/Lei/L15384.htm#art3">(Incluído pela Lei nº
   15.384, de 2026)</a>`. O `href` entrega a URL da lei alteradora **e a âncora
   do artigo** — insumo direto para o checador de vigência (5.6) sem resolver
   URL por conta própria.
2. **Artigo totalmente revogado tem o corpo REMOVIDO**: resta
   `Art. 217 - (Revogado pela Lei nº 11.106, de 2005)` (link). Detecção de
   `situacao=revogado`: anotação de revogação imediatamente após o cabeçalho do
   artigo, sem preceito/pena. Simplifica o parser.
3. **Dispositivo alterado mantém a redação antiga em texto plano** (sem
   riscado), seguida da nova com "(Redação dada…)". `<strike>` existe mas é
   raro/legado (6 ocorrências no CP inteiro, envolvendo cabeçalhos de capítulo
   revogado). Confirma a regra do plano (5.3-1): **a versão vigente é a de
   anotação mais recente** — nunca confiar em riscado.
4. Layout é HTML de Word (MSO): `<font>`, `&nbsp;` de indentação, `<p>` com
   estilos inline. Parsear por parágrafo extraindo texto + links; não esperar
   marcação semântica.

## 4. LexML — **descartado como verificação automática** (decidido)

- Página URN (`lexml.gov.br/urn/...lei:1989-07-11;7802`): 200 OK, mas **sem os
  metadados de revogação** no HTML estático (não cita a Lei 14.785).
- API SRU: respondida por **challenge anti-bot do Senado** ao curl.

A detecção de revogação total (armadilha dos agrotóxicos) fica com: (a) banner
no topo do snapshot; (b) **o watcher do DOU (5.11/F7)** — a lei revogadora nova
casa tanto a citação do diploma quanto o vocabulário penal, cobrindo o caso
dali em diante. O componente `revogacao.py` da F4 perde a perna LexML.

## 5. Ajustes decorrentes no plano

- F1: **sem dependências externas** — `urllib` da biblioteca padrão. Playwright
  descartado (ver correção da seção 1).
- F4: critério de aceite passa a ser o caso 7.802 detectado **por banner** (e o
  caso futuro coberto pelo watcher da F7); some a menção a LexML.
- Fixture obrigatória da F2: a Lei 11.340 (**UTF-16**) e uma cp1252, para travar
  a detecção de charset em teste.

## 6. Achado colateral da F1 — links quebrados no `transform_data`

O mapa `PLANALTO` que existia em `scripts/transform_data.py` apontava para
`…compilado.htm` em cinco diplomas; **quatro respondem 404 hoje** (11.343,
9.605, 12.850 e 8.137 — só o 10.826 sobrevive). Como esses links iam para o
relatório de qualidade, estavam quebrados em silêncio. O mapa foi substituído
pela leitura de `data/fontes.json`, cujas URLs são verificadas a cada rodada
do `baixar.py` — a duplicação sumiu e o link volta a ser confiável.

## Adendo de 14/11/2026 — o que o fetcher faz quando é recusado

O spike supôs um Planalto que responde a quem se apresenta como navegador. Desde
31/10/2026 o firewall da Presidência recusa os runners do GitHub — primeiro com a
página "Acesso Negado!" (814 bytes, HTTP 200), depois, em 14/11/2026, com outra página
sem a marca do bloqueio e HTTP 429 nas demais. O `baixar.py` passou a reconhecer as
três formas (a página de bloqueio, o 403/429 e a resposta com menos de 2.000 bytes sem
a sentinela), a dizer na linha da falha o tamanho e o título do que veio, e a encerrar
a rodada depois de três recusas seguidas. O intervalo de 1,2 s e o agente de navegador
continuam os do spike: a recusa é por endereço de origem, e de uma máquina doméstica
as 79 fontes baixaram íntegras no mesmo dia.
