# Proteção da `main` e das tags

A proteção do repositório é **versionada aqui**, e não só clicada na interface web. O
arquivo é a fonte; o GitHub é o derivado. Mexeu pela web? Traga a mudança para cá, senão a
próxima execução do [`aplicar.sh`](aplicar.sh) a desfaz em silêncio.

Os dois arquivos são a **cópia fiel do que está no ar**, lida da API em 24/09/2026 —
não uma proposta. Antes de editar qualquer um, rode `aplicar.sh --listar` e confira.

| arquivo | alvo | o que impõe |
|---|---|---|
| [`protecao-main.json`](protecao-main.json) | a branch padrão | `deletion`, `non_fast_forward`, PR com aprovação e code owner, CI verde |
| [`tags-release.json`](tags-release.json) | `refs/tags/v*` | `creation`, `update`, `deletion` — versão publicada não se reescreve |

## Por que isso não trava o mantenedor

O `pull_request` exige **1 aprovação** e **revisão do code owner**
([`../CODEOWNERS`](../CODEOWNERS)), e o GitHub não deixa ninguém aprovar o próprio PR. Num
repositório de uma pessoa só, isso trancaria tudo. O que destrava são os dois
`bypass_actors`:

- **`RepositoryRole 5`**, o papel de administrador. É o mantenedor. Sem ele, o dono do
  projeto precisaria pedir revisão a alguém que talvez ainda não conheça o código.
- **`Integration 4435955`**, o app de automação. Sem ele, o `regen-data`, o `release` e o
  carimbo mensal do conferidor param de empurrar para a `main` — e param em silêncio, com
  um erro de permissão no log de um workflow que ninguém abre.

Quem **não** tem bypass é todo o resto. Na prática, hoje: qualquer pessoa que não seja o
mantenedor só chega à `main` por pull request revisado.

## O que muda quando entrar um colaborador

Nada precisa ser criado — as regras já estão lá. O que muda é o **bypass**, e é uma
decisão, não uma tarefa:

- manter o bypass de admin significa que o mantenedor continua mergeando sozinho, e a
  exigência de revisão vale só para o time;
- retirá-lo significa que ninguém merge sem revisão de outra pessoa, o mantenedor
  inclusive. É o passo a dar quando houver uma segunda pessoa capaz de revisar o direito
  penal do catálogo, e não antes.

Também vale ligar `dismiss_stale_reviews_on_push` (hoje `false`): com mais de uma pessoa
mexendo, aprovação que sobrevive a um push novo aprova o que ninguém leu.

## O que forks não alcançam

Um fork **não escreve no repositório de origem**. Não é permissão que se negue — é coisa
que o GitHub não oferece. Quem tem cópia do projeto só chega à `main` por pull request. Pela
mesma razão, ruleset nenhum alcança branch de fork: as regras daqui valem para as branches
DESTE repositório.

O que um fork consegue, e por isso importa: rodar o `ci.yml`, que dispara em
`pull_request`. Isso é seguro porque `pull_request` roda o workflow **da base**, com token
somente-leitura e sem acesso a segredo. **Nunca troque esse gatilho por
`pull_request_target`** fazendo checkout do código do PR: essa combinação executa código de
terceiro com o token e os segredos do repositório de origem, e é o furo clássico das
Actions.

## Aplicar

```bash
./.github/rulesets/aplicar.sh --listar                    # o que está no ar
./.github/rulesets/aplicar.sh --ensaio protecao-main.json # mostra e não envia
./.github/rulesets/aplicar.sh protecao-main.json          # cria ou atualiza pelo nome
```

O script casa pelo `name`, então é repetível: rodar duas vezes atualiza em vez de duplicar.
O repositório sai do remoto do próprio clone, e não de uma constante — ele ainda se chama
`sispenas` e passa a `atlaspen` no lançamento.

Para uma exceção pontual, ponha o ruleset em `"evaluate"` ou `"disabled"` pela web, faça o
que precisa e volte a `"active"` rodando o `aplicar.sh`.

## Fora daqui, mas da mesma família

- **`delete_branch_on_merge`**, ligado em 24/09/2026: o GitHub apaga a branch no instante do
  merge do PR. É configuração de repositório, não ruleset.
  `gh api --method PATCH repos/<dono>/<nome> -F delete_branch_on_merge=true`
- **`environment: automacao`**, a trava server-side dos segredos do app: com a política de
  branch restrita à `main`, o GitHub recusa entregar a chave a um job que rode em qualquer
  outra branch. Vive em Settings ▸ Environments.
- **A faxina de branches**, em [`../workflows/branches.yml`](../workflows/branches.yml).
