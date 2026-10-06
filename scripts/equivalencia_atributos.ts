/**
 * Teste de equivalência dos atributos penais (frente 5 do backlog).
 *
 * A migração dos 22 atributos do código para dados só entra se nada mudar. Este
 * script CONGELA o resultado do motor atual e, depois, COMPARA o motor migrado com
 * o congelamento. Para cada atributo e cenário, guarda o status em cada tipo com
 * pena privativa (uma letra por tipo) e uma impressão digital de todos os textos
 * devolvidos (resumo, detalhes, limiar).
 *
 * Dois cenários: o da página do tipo penal (`cenarioFromCrime`) e o padrão da
 * busca por atributo (`cenarioParaCrime` com `cenarioReversoPadrao`). Parâmetros
 * nos valores padrão, que são os da lei vigente.
 *
 * A chave de cada atributo no congelamento é o id numérico que ele recebe na
 * migração — a posição no catálogo, de 1 a 22 —, com o id de hoje ao lado, só
 * para leitura. O congelamento guarda também a impressão digital do catálogo de
 * tipos: se a base de tipos mudar no meio do caminho, a comparação se recusa a
 * rodar, em vez de acusar como regressão do motor o que veio dos dados.
 *
 * Uso, a partir da raiz:
 *   npm run equivalencia -- --gravar   # congela o motor atual
 *   npm run equivalencia               # compara o motor com o congelamento
 */

import * as fs from 'fs';
import * as path from 'path';
import {createHash} from 'crypto';
import type {Cenario, Crime, TipoDoMotor} from '../src/lib/types';
import {avaliarTipo} from '../src/lib/atributos/remissao';
import {CATALOGO, avaliarAtributo, valoresPadrao} from '../src/lib/atributos';
import {
  cenarioParaCrime,
  cenarioReversoPadrao,
  crimesComPenaPrivativa,
} from '../src/lib/atributos/reverso';
import {cenarioFromCrime} from '../src/lib/cenario';

const RAIZ = process.cwd();
const CRIMES = path.join(RAIZ, 'static', 'data', 'crimes.json');
const SAIDA = path.join(RAIZ, 'scripts', 'equivalencia', 'atributos.json');
const LETRA: Record<string, string> = {cabivel: 'C', condicional: 'K', incabivel: 'I'};

const todos: Crime[] = JSON.parse(fs.readFileSync(CRIMES, 'utf-8'));
const crimes = crimesComPenaPrivativa(todos).sort((a, b) => a.id - b.id);
// A trilha de auditoria (types.ts) fica fora da impressão digital: o carimbo
// semanal do conferidor a reescreve em todo registro, entra na main com
// [skip ci] e o motor não a lê. Com ela dentro, a rodada de 05/10/2026 travou
// a CI de todo PR seguinte sem que um só veredito pudesse ter mudado.
// Só no nível do registro: `fonte` também é campo do aviso da norma, e esse conta.
const TRILHA_DE_AUDITORIA = new Set(['fonte', 'conferido_em', 'conferido_resultado']);
const semTrilha = todos.map((c) =>
  Object.fromEntries(Object.entries(c).filter(([k]) => !TRILHA_DE_AUDITORIA.has(k))),
);
// JSON canônico, e não o arquivo cru: o fim de linha muda entre Windows e a CI.
const crimesSha256 = createHash('sha256').update(JSON.stringify(semTrilha)).digest('hex');
const rev = cenarioReversoPadrao();

const CENARIOS: [string, (c: TipoDoMotor) => Cenario][] = [
  ['tipo', (c) => cenarioFromCrime(c)],
  ['reverso', (c) => cenarioParaCrime(c, rev)],
  // Os dois cenários acima são de réu PRIMÁRIO, e por isso o congelamento não
  // via nada do que a reincidência muda: a correção da progressão dos crimes
  // comuns (LEP, art. 112, II e III), em 19/09/2026, passou por ele sem uma
  // diferença sequer. Os dois abaixo fecham essa janela — o doloso pega a
  // reincidência genérica, e o específico, o que a lei reserva a ela.
  ['reincidente-doloso', (c) => ({...cenarioFromCrime(c), reincidencia: 'doloso'})],
  ['reincidente-especifico', (c) => ({...cenarioFromCrime(c), reincidencia: 'especifico'})],
];

interface Cenariado {
  status: string;
  hash: string;
}

function congelar() {
  const atributos: Record<string, {id_atual: string; nome: string} & Record<string, unknown>> = {};
  CATALOGO.forEach((def, i) => {
    const params = valoresPadrao(def);
    const porCenario: Record<string, Cenariado> = {};
    for (const [nome, montar] of CENARIOS) {
      const h = createHash('sha256');
      let status = '';
      for (const c of crimes) {
        const r = avaliarTipo(def, params, c, todos, montar);
        status += LETRA[r.status];
        h.update(JSON.stringify([c.id, r.status, r.resumo, r.detalhes, r.limiar ?? null]));
      }
      porCenario[nome] = {status, hash: h.digest('hex')};
    }
    atributos[String(i + 1)] = {id_atual: String(def.id), nome: def.nome, ...porCenario};
  });
  return {
    _meta: {
      descricao:
        'Congelamento do motor de atributos penais antes da migração para dados ' +
        '(frente 5 do backlog). Gerado e conferido por scripts/equivalencia_atributos.ts.',
      letras: {C: 'cabível', K: 'condicional', I: 'incabível'},
      cenarios: {
        tipo: 'cenarioFromCrime: a página do tipo penal',
        reverso: 'cenarioParaCrime com cenarioReversoPadrao: a busca por atributo',
      },
      parametros: 'valores padrão (lei vigente)',
    },
    crimes_sha256: crimesSha256,
    tipos: crimes.map((c) => c.id),
    atributos,
  };
}

function comparar(): number {
  if (!fs.existsSync(SAIDA)) {
    console.error(`✗ não há congelamento em ${path.relative(RAIZ, SAIDA)}: rode com --gravar`);
    return 2;
  }
  const antigo = JSON.parse(fs.readFileSync(SAIDA, 'utf-8'));
  if (antigo.crimes_sha256 !== crimesSha256) {
    console.error(
      '✗ o catálogo de tipos mudou desde o congelamento. Regrave o congelamento com o ' +
        'motor ANTIGO (o do commit do congelamento) antes de comparar.',
    );
    return 2;
  }
  const novo = congelar();
  const chaves = new Set([...Object.keys(antigo.atributos), ...Object.keys(novo.atributos)]);
  let diferencas = 0;
  for (const k of chaves) {
    const a = antigo.atributos[k];
    const b = novo.atributos[k];
    if (!a || !b) {
      diferencas += 1;
      console.error(`  ✗ atributo ${k}: ${a ? 'sumiu do motor' : 'não existia no congelamento'}`);
      continue;
    }
    for (const [cenario] of CENARIOS) {
      const antes = a[cenario] as Cenariado;
      const depois = b[cenario] as Cenariado;
      if (antes.status !== depois.status) {
        const tipos = antigo.tipos.filter(
          (_: number, i: number) => antes.status[i] !== depois.status[i],
        );
        diferencas += 1;
        console.error(
          `  ✗ atributo ${k} (${a.nome}), cenário ${cenario}: o status mudou em ` +
            `${tipos.length} tipo(s): ${tipos.slice(0, 20).join(', ')}`,
        );
      } else if (antes.hash !== depois.hash) {
        diferencas += 1;
        console.error(
          `  ✗ atributo ${k} (${a.nome}), cenário ${cenario}: o status é o mesmo, mas ` +
            'resumo, detalhes ou limiar mudaram',
        );
      }
    }
  }
  if (diferencas) {
    console.error(`✗ ${diferencas} diferença(s) contra o congelamento`);
    return 1;
  }
  console.log(
    `✓ equivalência: ${chaves.size} atributos × ${novo.tipos.length} tipos × ` +
      `${CENARIOS.length} cenários, nada mudou`,
  );
  return 0;
}

if (process.argv.includes('--gravar')) {
  const dados = congelar();
  fs.mkdirSync(path.dirname(SAIDA), {recursive: true});
  fs.writeFileSync(SAIDA, JSON.stringify(dados, null, 2) + '\n', 'utf-8');
  console.log(
    `congelado: ${Object.keys(dados.atributos).length} atributos × ${dados.tipos.length} ` +
      `tipos × ${CENARIOS.length} cenários -> ${path.relative(RAIZ, SAIDA)}`,
  );
} else {
  process.exit(comparar());
}
