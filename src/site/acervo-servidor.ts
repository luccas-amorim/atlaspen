// O acervo histórico e a linha do tempo, em tempo de build.
//
// Duas fontes, somadas e nunca misturadas com o catálogo vigente:
//   - data/acervo.json: os dispositivos que saíram de vigência;
//   - data/diplomas.json: os diplomas inteiros revogados ou não recepcionados.
// E o eixo: data/marcos.json (constituições e códigos) e o histórico
// legislativo dos dispositivos citados pelos atributos.
//
// O que a fonte não diz, a tela não diz: data da revogação e texto original
// ficam ausentes até serem conferidos contra o Planalto. Conferidos em
// 18/09/2026: todos os dispositivos têm os dois; os diplomas inteiros têm a
// data, e o texto deles é a própria fonte oficial — salvo os que o Planalto não
// tem, cujo texto é o do normas.leg.br (`fonte_texto`), sem valor legal oficial,
// e a tela diz isso (decisão de 26/10/2026).

import acervo from '../../data/acervo.json';
import marcosBrutos from '../../data/marcos.json';
import historico from '../../data/historico-legislativo.json';
import {DIPLOMAS} from './diplomas-servidor';
import {ROTULO_CATEGORIA, anoDaSaida} from '../components/acervo/tipos';
import type {CategoriaAcervo, EventoDoAno, Marco, NormaDeSaida, RegistroAcervo} from '../components/acervo/tipos';

export type {CategoriaAcervo, EventoDoAno, Marco, NormaDeSaida, RegistroAcervo};
export {ROTULO_CATEGORIA};

/** O começo da linha do tempo: a Independência. */
export const INICIO_DA_LINHA = 1822;

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];

/** "Lei nº 7.802, de 11 de julho de 1989" → "1989-07-11". */
function dataDaNorma(norma: string): string | null {
  const m = /de (\d{1,2})º? de ([a-zç]+) de (\d{4})/i.exec(norma);
  if (!m) return null;
  const mes = MESES.indexOf(m[2].toLowerCase());
  return mes < 0 ? null : `${m[3]}-${String(mes + 1).padStart(2, '0')}-${m[1].padStart(2, '0')}`;
}

/** O ano de quatro dígitos na designação da norma: "Lei nº 14.785/2023" → 2023. */
function anoDaNorma(norma: string): number | null {
  const m = /(?:\/|,\s*|\()((?:18|19|20)\d{2})\b/.exec(norma);
  return m ? Number(m[1]) : null;
}

interface RegistroFonte {
  id: string;
  dispositivo: string;
  nome: string;
  diploma: string;
  artigos: string[];
  categoria: CategoriaAcervo;
  o_que_houve: string;
  normas: NormaDeSaida[];
  retirado: {versao: string; nota: string} | null;
  data_revogacao: string | null;
  texto_original: string | null;
}

let cache: RegistroAcervo[] | null = null;

export function registrosDoAcervo(): RegistroAcervo[] {
  if (cache) return cache;
  const porId = new Map(DIPLOMAS.map((d) => [d.id, d]));
  const dispositivos: RegistroAcervo[] = (acervo as unknown as {registros: RegistroFonte[]}).registros.map((r) => {
    const d = porId.get(r.diploma);
    return {
      id: r.id,
      tipo: 'dispositivo',
      nome: r.nome,
      dispositivo: r.dispositivo,
      categoria: r.categoria,
      oQueHouve: r.o_que_houve,
      normas: r.normas,
      retirado: r.retirado,
      artigos: r.artigos,
      diploma: d ? {id: d.id, nome: d.nome, norma: d.norma} : null,
      fonteUrl: d?.fonte_url ?? null,
      fonteTexto: d?.fonte_texto ?? null,
      publicacao: null,
      dataRevogacao: r.data_revogacao,
      textoOriginal: r.texto_original,
    };
  });
  const diplomas: RegistroAcervo[] = DIPLOMAS.filter((d) => d.situacao !== 'vigente').map((d) => {
    const norma = d.norma_revogadora ?? '';
    const pub = dataDaNorma(d.norma);
    return {
      id: d.id,
      tipo: 'diploma',
      nome: d.nome,
      dispositivo: `${d.norma.replace(/, de .*$/, '')} (diploma inteiro)`,
      categoria: d.situacao === 'nao_recepcionado' ? 'nao_recepcionado' : 'revogado',
      oQueHouve: `${d.situacao === 'nao_recepcionado' ? 'Não recepcionado' : 'Revogado'} — ${norma}.${
        d.data_revogacao_nota ? ` ${d.data_revogacao_nota}` : ''
      }`,
      normas: [{norma, ano: anoDaNorma(norma)}],
      retirado: null,
      artigos: [d.id],
      diploma: {id: d.id, nome: d.nome, norma: d.norma},
      fonteUrl: d.fonte_url ?? null,
      fonteTexto: d.fonte_texto ?? null,
      publicacao: pub ? {data: pub, norma: d.norma} : null,
      dataRevogacao: d.data_revogacao ?? null,
      // O texto de um diploma inteiro não cabe na ficha: o link da fonte cumpre esse papel.
      textoOriginal: null,
    };
  });
  cache = [...dispositivos, ...diplomas];
  return cache;
}

// ── A linha do tempo ─────────────────────────────────────────────────────

export const MARCOS: Marco[] = (marcosBrutos as unknown as {marcos: Omit<Marco, 'ano'>[]}).marcos.map((m) => ({
  ...m,
  ano: Number(m.data.slice(0, 4)),
}));

interface EventoHistorico {
  dispositivo: string;
  evento: string;
  norma: string | null;
  ano?: number;
}

/** "juizados-9099|art. 61, caput" → "Lei 9.099/95, art. 61, caput", pelo nome do diploma quando se sabe. */
function dispositivoLegivel(chave: string): string {
  const [, resto = chave] = chave.split('|');
  return resto;
}

export function eventosDaLinha(): EventoDoAno[] {
  const eventos: EventoDoAno[] = [];
  for (const m of MARCOS) {
    eventos.push({
      ano: m.ano,
      categoria: m.tipo === 'constituicao' ? 'CONSTITUIÇÃO' : 'CÓDIGO',
      tom: 'marco',
      titulo: m.rotulo,
      norma: m.nota ? `${m.norma} — ${m.nota}` : m.norma,
    });
  }
  for (const r of registrosDoAcervo()) {
    if (r.publicacao) {
      eventos.push({
        ano: Number(r.publicacao.data.slice(0, 4)),
        categoria: 'PUBLICAÇÃO',
        tom: 'publicacao',
        titulo: r.nome,
        norma: r.publicacao.norma,
        rota: `/acervo/${r.id}`,
      });
    }
    for (const n of r.normas) {
      const ano = anoDaSaida(r, n);
      if (ano === null) continue;
      eventos.push({
        ano,
        categoria: ROTULO_CATEGORIA[r.categoria].toUpperCase(),
        tom: r.categoria === 'revogado' || r.categoria === 'vigencia_encerrada' ? 'saida' : 'excecao',
        titulo: `${r.nome}${n.alcance ? ` (${n.alcance})` : ''}`,
        norma: `${r.dispositivo} · ${n.norma}`,
        rota: `/acervo/${r.id}`,
      });
    }
  }
  // O histórico legislativo dos dispositivos que os atributos citam, uma linha
  // por lei e por ano: 68 eventos de 2019 são uma lei só, o Pacote Anticrime.
  const porLei = new Map<string, {ano: number; norma: string; dispositivos: string[]}>();
  for (const e of (historico as unknown as {eventos: EventoHistorico[]}).eventos) {
    if (!e.ano || !e.norma || e.norma === 'original') continue;
    const k = `${e.ano}|${e.norma}`;
    if (!porLei.has(k)) porLei.set(k, {ano: e.ano, norma: e.norma, dispositivos: []});
    porLei.get(k)!.dispositivos.push(dispositivoLegivel(e.dispositivo));
  }
  for (const g of porLei.values()) {
    const unicos = [...new Set(g.dispositivos)];
    eventos.push({
      ano: g.ano,
      categoria: 'ALTERAÇÃO',
      tom: 'lei',
      titulo: `${g.norma}: ${unicos.length} ${unicos.length === 1 ? 'dispositivo citado' : 'dispositivos citados'} pelos atributos penais`,
      norma: unicos.slice(0, 4).join(' · ') + (unicos.length > 4 ? ` · e mais ${unicos.length - 4}` : ''),
      rota: '/atributos',
    });
  }
  return eventos.sort((a, b) => a.ano - b.ano);
}
