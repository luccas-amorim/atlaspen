// Os diplomas do catálogo, em tempo de build (data/diplomas.json).
//
// O campo `lei` de cada tipo penal é um RÓTULO ("CP", "CP (atualiz.)", "Lei
// 14.811/24"), e mais de um rótulo aponta para o mesmo diploma. O inventário
// guarda a correspondência em `rotulos_catalogo`; é por ela que a ficha diz
// "Código Penal" na trilha, e não o rótulo cru.

import diplomas from '../../data/diplomas.json';

export interface Diploma {
  id: string;
  nome: string;
  norma: string;
  situacao: string;
  fonte_url?: string;
  /** De onde vem o texto quando não é o compilado do Planalto ("normas.leg.br"). */
  fonte_texto?: string;
  rotulos_catalogo?: string[];
  norma_revogadora?: string;
  /** Perda de vigência dos dispositivos penais do diploma (AAAA-MM-DD). */
  data_revogacao?: string | null;
  /** Vacatio, revogação escalonada ou não recepção. */
  data_revogacao_nota?: string;
  preceitos_esperados?: number;
  tipos_catalogados?: number;
}

export const DIPLOMAS: Diploma[] = (diplomas as unknown as {diplomas: Diploma[]}).diplomas;

const PORROTULO = new Map<string, Diploma>();
for (const d of DIPLOMAS) for (const r of d.rotulos_catalogo ?? []) PORROTULO.set(r, d);

export function diplomaDoRotulo(rotulo: string): Diploma | undefined {
  return PORROTULO.get(rotulo);
}
