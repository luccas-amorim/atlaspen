# Instruções para agentes de IA — AtlasPen

Ferramenta aberta de pesquisa de tipos penais e atributos penais. **Acuidade jurídica é o valor
central**: um dado errado publicado é pior que um dado ausente. Nada entra no catálogo sem
conferência contra o **texto compilado** oficial do `planalto.gov.br`.

Este arquivo é lido pelo Codex e demais agentes pelo nome; o Claude Code o lê via
`CLAUDE.md`, que só o importa. Regra nova entra **aqui**. Os próximos passos possíveis do
projeto estão na seção "O que falta" do `README.md`.

## Versão e notas: o feed já registra, a Release espera a v1.0.0

Decisões de 10/09/2026 e de 14/09/2026:

- Até o lançamento oficial, a **v1.0.0**, o projeto anda em **`0.0.x`**. O `release.yml`
  não publica Release nem tag enquanto a versão for `0.x`.
- **O feed de notas já funciona em `0.0.x`** e publica **exclusivamente** alterações de
  LEI que criem, modifiquem ou extingam tipos penais ou atributos penais. Correção de dado
  do catálogo (o erro antigo que a conferência achou) **não** vira nota.
- Cada entrada (`src/data/changelog/entries/<ano>/<id>.ts`, um arquivo por mudança; passo
  a passo em `src/data/changelog/create-changelog-entry.md`) declara só o **alcance**:
  `tipo`, `atributo`, ou os dois. **Simplificado em 24/09/2026**: antes eram uma natureza
  em latim e seis áreas, e as duas classificações custavam mais a quem escreve do que
  entregavam a quem lê. A direção da mudança — mais severa, mais branda, deixou de ser
  crime — continua no feed, dita em português no `summary` e no `body`, onde cabe a
  ressalva que um rótulo não comporta. A distinção em latim sobrevive na SIMULAÇÃO
  (`src/lib/simulacao/tipos.ts`), onde é resultado e não etiqueta. O
  `scripts/validar-changelog.mjs` reprova alcance fora do contrato e versão que não existe.
- O PR que traz nota sobe o patch em `package.json` e no lockfile. O Proponente faz isso
  sozinho quando a rodada tem alteração de lei recente: redação dada, ou dispositivo
  incluído, por lei deste ano ou do anterior, lido da anotação do compilado.

**Depois da v1.0.0**, cada versão volta a publicar também a Release no GitHub, a partir das
mesmas entradas. A versão segue a regra de `docs/dados-abertos.md` (Estabilidade e
versionamento), e o merge na `main` dispara o `release.yml`, que cria a tag. **Nunca faça
`git push origin vX.Y.Z` manual.**

## Convenções do catálogo

Estão em `CONTRIBUTING.md` (C1–C8) e são **impostas pela CI**. As que quebram em silêncio se
ignoradas:

- `data/crimes.json` é a **fonte**; `static/data/crimes.json` é **derivado** por
  `scripts/transform_data.py` — teste sempre contra o derivado.
- `id` é **append-only**: é a URL pública (`?tipo=N`). Nunca reatribua nem renumere. A
  numeração foi reiniciada DUAS vezes, as duas por decisão explícita do dono do projeto
  — v1.4.0 (protótipo) e v2.0.0 (fim da revisão da base). Fora disso, id retirado entra
  em `data/ids-aposentados.json` e `--estrito` reprova reaproveitamento — inclusive o
  caso silencioso de remover o topo da numeração e o `max + 1` devolver um número já
  usado. Reiniciar exige remapear TUDO que é indexado por id: `data/conferencia.json`,
  as tabelas `CORRECOES_*` de `scripts/catalogo/tabelas.py`, os `ids` das exceções da auditoria e
  os links `?tipo=N` das notas já publicadas.
- **Glossário.** *Atributo penal* é o instituto (transação, progressão, prescrição…);
  *parâmetro*, o patamar, a fração ou a vedação editável de um atributo; *campo*, o
  campo do registro de tipo penal. "Benefício" só onde é a palavra da lei ou de
  súmula. Ver o `CONTRIBUTING.md`.
- `resultado_morte` deriva do **nome** do tipo, nunca do `obs`.
- O campo `artigo` tem **grafia canônica** (`Art. 121, §2º, I`; `§` colado ao número;
  inciso em maiúsculas; alínea em minúscula), validada pelo `--estrito` com a régua de
  `scripts/dispositivo_canonico.py`. `§ 2º` com espaço escondeu um erro jurídico por
  meses porque a regra que o excluía do rol de hediondos nunca casou.
- Editar `.md` com Python/`sed` no Windows introduz **CRLF** (quebra os admonitions
  `:::note[...]`); use `write_bytes` ou confira o EOL.
- Admonitions: `:::note[Título]`, não `:::note Título` — é a sintaxe que
  `src/site/markdown/admonicoes.ts` lê.
- **Correção que resolve issue diz `Closes #N`** — no corpo do PR, ou no do
  commit quando não houver PR. Sem isso a issue sobrevive ao próprio conserto:
  a #27 ficou onze dias aberta depois de resolvida por inteiro, porque o commit
  que a resolveu não a citou. O robô abre; fechar é de quem conserta.
- **`docs/` é o que vai ao ar, e nada mais** (decisão de 24/09/2026). A árvore
  espelha a do site: `docs/*.md` é o grupo *Documentação* de `/projeto`,
  `docs/textos/*.md` é o grupo *Textos*. Documento que existe só no
  repositório NÃO entra em `docs/`: o pré-registro da auditoria é o
  `AUDITORIA.md` da raiz, ao lado do `TRIAGEM.md`, e os planos e specs do
  desenvolvimento ficam em `.superpowers/`. Documento novo em
  `docs/` precisa entrar em `data/documentacao.json` e na lista
  `DOCUMENTOS_DO_PROJETO`, senão fica no repositório sem página, que foi como
  `docs/acervo-historico.md` passou meses sendo gerado sem que nada o lesse.

## Verificação antes de concluir

```
python scripts/transform_data.py --estrito --max-contradicoes=0
python scripts/validar_modificadores.py
python scripts/validar_atributos.py
python scripts/robos/arquivista/verificar_documentacao.py
python -m pytest scripts/robos/tests
node scripts/validar-changelog.mjs
npm run atributos && npm run typecheck && npm run mortos && npm run verificar && npm run equivalencia && npm run build
```

A CI trava em `--max-contradicoes=0` e exige o derivado sincronizado com a fonte. Trava
também no **congelamento dos vereditos** (`npm run equivalencia`), cuja impressão digital
cobre o catálogo inteiro — inclusive o `obs`, que o motor não lê: mudou dado em
`data/crimes.json`, e nenhum veredito mudou, regrave com `npm run equivalencia -- --gravar`
e confira que o diff de `scripts/equivalencia/atributos.json` é só o `crimes_sha256`. Em
25/10/2026 um `obs` mudado sem isso deixou a `main` vermelha. Extraia
PDFs de leis com `pdftotext -layout -enc UTF-8` (o poppler não renderiza página aqui).

Mexeu no conferidor ou nos dados que ele lê? Rode também
`python scripts/robos/auditor/auditar.py` e `python scripts/robos/vigia/conferir.py`, que não
falham o build mas dizem o que ficou aberto.

Mexeu em `violencia`, `grave_ameaca` ou `acao`? Rode os dois derivadores, que comparam o
campo publicado com o texto do dispositivo e abrem três listas — confere, diverge e pede
juízo:

```
python scripts/robos/auditor/conferir_violencia.py --md crawler/relatorios/violencia-e-grave-ameaca.md
python scripts/robos/auditor/conferir_acao_penal.py --md crawler/relatorios/acao-penal.md
```

Eles NÃO escrevem no catálogo. O que a regra não decide sai marcado como juízo, e juízo é da
pessoa que assina.

## O que NÃO entra no catálogo, e onde entra

- **`scripts/robos/auditor/excecoes-auditoria.json`** — o achado da auditoria que já foi julgado
  e não precisa voltar. Casa por tipo de achado MAIS um alvo, nunca por tipo sozinho, e
  declara motivo e data. Nos derivadores de violência e ação penal, o alvo é `campo` mais
  `ids`: o estupro de vulnerável tem juízo tomado sobre `violencia` (decisão 4, grau B) e
  nada decidido sobre `grave_ameaca`, e exceção por id sozinho calaria o que ninguém julgou.
  Divergência real nunca vira exceção: vira correção no dado. Exceção é juízo TOMADO, com
  pendência declarada — e sai no dia em que a pendência fechar.
- **Fonte secundária aponta, não escreve** (decisão de 25/10/2026). O Senado (API de
  Dados Abertos), o normas.leg.br e o ctresb/leis são lidos pelo Cotejador
  (`scripts/robos/cotejador/`), o Banco Nacional de Precedentes do CNJ pelo Relator
  (`scripts/robos/relator/`), e todos pelo gerador de candidatos do acervo
  (`scripts/robos/acervo/candidatos.py`), e nunca escrevem no catálogo, no acervo nem
  em `data/fontes.json`: o que dizem vira pergunta na issue ou linha de relatório. O
  Senado classifica mal — registra como "Alteração" as revogações que a Lei
  11.106/2005 fez no CP —, e por isso nem a revogação que ele afirma entra sem o
  compilado. Plano e decisões em `.superpowers/planos/2026-10-25-fontes-abertas-e-acervo.md`.
- **A questão jurídica em aberto não vira dado.** Havia um `REVISAO-PENDENTE.md` na raiz
  para isso; ele saiu na v2.0.0, quando a revisão da base fechou as perguntas que ele
  guardava. Se a próxima aparecer, o lugar dela é o mesmo de sempre: **o registro diz o
  que se sabe e cala o que não se sabe** — moldura condicional, `hediondo_condicao`,
  `acao_condicao`, `pena_por_remissao`, `vigencia_ate` — e a discussão vai para a issue,
  não para o campo. Nunca preencha lacuna com plausibilidade.

Trabalhe em branch própria, commits pequenos e descritivos; **não faça push nem abra PR sem
o usuário pedir**.
