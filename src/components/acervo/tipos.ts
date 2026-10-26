// O acervo histórico — tipos e regras puras, sem dado.
//
// Separado do leitor de build (src/site/acervo-servidor.ts), que carrega os
// JSON: as ilhas importam daqui e não arrastam dado para o navegador.

/**
 * `vigencia_encerrada`: o tipo de lei temporária cujo prazo a própria lei fixou
 * (a Copa de 2014, as Olimpíadas de 2016). Não é revogação — ninguém o tirou de
 * vigência —, e a data dele é o último dia que a lei deu (decisão de 26/10/2026).
 */
export type CategoriaAcervo = 'revogado' | 'nao_recepcionado' | 'vetado' | 'vigencia_encerrada';

export interface NormaDeSaida {
  norma: string;
  /** O ano da norma (lido da própria designação), e não o da perda de vigência. */
  ano: number | null;
  alcance?: string;
}

export interface RegistroAcervo {
  id: string;
  tipo: 'dispositivo' | 'diploma';
  nome: string;
  dispositivo: string;
  categoria: CategoriaAcervo;
  oQueHouve: string;
  normas: NormaDeSaida[];
  retirado: {versao: string; nota: string} | null;
  artigos: string[];
  diploma: {id: string; nome: string; norma: string} | null;
  fonteUrl: string | null;
  /** De onde vem o texto, quando não é o compilado do Planalto ("normas.leg.br"). */
  fonteTexto: string | null;
  /** Para os diplomas: a data da própria lei, lida de data/diplomas.json. */
  publicacao: {data: string; norma: string} | null;
  dataRevogacao: string | null;
  textoOriginal: string | null;
}

/**
 * O rótulo do link da fonte. O texto é o compilado do Planalto, salvo a norma
 * que o Planalto não tem: aí é o do normas.leg.br, que a própria API marca sem
 * valor legal oficial — e a tela diz isso (decisão de 26/10/2026).
 */
export function rotuloDaFonte(fonteTexto: string | null): string {
  return fonteTexto === 'normas.leg.br'
    ? 'texto no normas.leg.br, sem valor legal oficial'
    : 'texto compilado no Planalto';
}

/** O aviso do diploma inteiro, cujo texto não cabe na ficha: diz onde ele está. */
export function avisoDoTextoInteiro(fonteTexto: string | null): string {
  return fonteTexto === 'normas.leg.br'
    ? 'Diploma inteiro: o texto está no normas.leg.br, citado nesta ficha — o Planalto não tem a norma, e a cópia do Congresso não tem valor legal oficial.'
    : 'Diploma inteiro: o texto está na fonte oficial, citada nesta ficha.';
}

export const ROTULO_CATEGORIA: Record<CategoriaAcervo, string> = {
  revogado: 'revogado',
  nao_recepcionado: 'não recepcionado',
  vetado: 'vetado',
  vigencia_encerrada: 'vigência encerrada',
};

/**
 * O ano em que o registro saiu de vigência, para a linha do tempo e o recorte
 * por ano: o da norma que o tirou (lido da designação dela), salvo na vigência
 * encerrada, em que a norma é a própria lei e o ano é o do fim do prazo.
 */
export function anoDaSaida(r: RegistroAcervo, n: NormaDeSaida): number | null {
  if (r.categoria === 'vigencia_encerrada' && r.dataRevogacao) return Number(r.dataRevogacao.slice(0, 4));
  return n.ano;
}

export interface Marco {
  data: string;
  ano: number;
  tipo: 'constituicao' | 'codigo';
  rotulo: string;
  eixo: string;
  norma: string;
  nota?: string;
}

export interface EventoDoAno {
  ano: number;
  categoria: string;
  /** saida: revogação; excecao: veto ou não recepção; marco; lei: alteração; publicacao. */
  tom: 'saida' | 'excecao' | 'marco' | 'lei' | 'publicacao';
  titulo: string;
  norma: string;
  rota?: string;
}

export interface PassoRegistro {
  quando: string;
  fato: string;
  norma: string;
}

const dataCurta = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;

/**
 * A vida do registro, no que a fonte diz: a publicação (dos diplomas), a norma
 * que o tirou de vigência, a saída do catálogo. O que não se sabe — a data de
 * criação de um dispositivo, a data exata da revogação — não entra.
 */
export function passosDoRegistro(r: RegistroAcervo): PassoRegistro[] {
  const passos: PassoRegistro[] = [];
  if (r.publicacao) passos.push({quando: dataCurta(r.publicacao.data), fato: 'Publicado', norma: r.publicacao.norma});
  for (const n of r.normas) {
    const fato =
      r.categoria === 'vetado'
        ? 'Vetado na sanção — nunca vigorou'
        : r.categoria === 'nao_recepcionado'
          ? 'Declarado não recepcionado pela Constituição de 1988'
          : r.categoria === 'vigencia_encerrada'
            ? 'Fim da vigência que a própria lei fixou'
            : // Só "revogado": revogação não é abolitio criminis. A conduta pode ter
            // seguido punível noutro tipo (o ECA, art. 233, foi para a Lei de
            // Tortura), e isso o registro diz em "o que houve", não o passo.
            `Revogado${n.alcance ? ` (${n.alcance})` : ''}`;
    passos.push({
      quando: r.dataRevogacao ? dataCurta(r.dataRevogacao) : n.ano ? String(n.ano) : 's/ data',
      fato,
      norma: n.norma,
    });
  }
  if (r.retirado) {
    passos.push({quando: r.retirado.versao, fato: 'Retirado do catálogo vigente', norma: r.retirado.nota});
  }
  return passos;
}
