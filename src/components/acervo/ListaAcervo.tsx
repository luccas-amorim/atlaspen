// A lista do acervo histórico — "o que saiu de vigência"
// (Atributos, acervo e eixo temporal.dc.html, 4b; Linha do tempo e tela
// inicial.dc.html, 5a).
//
// A mesma anatomia do catálogo vigente — lista filtrável e ficha por registro —,
// mas base separada: nada daqui entra em estatística de direito vigente. Aceita
// o recorte por artigo (/acervo?artigo=cp-121, o link da aba histórico da ficha
// do tipo) e, dentro da linha do tempo, o recorte por ano.

import {useEffect, useState} from 'react';
import {caminho} from '../../site/url';
import {normalizar} from '../tipos/filtros';
import {
  ROTULO_CATEGORIA,
  anoDaSaida,
  avisoDoTextoInteiro,
  passosDoRegistro,
  rotuloDaFonte,
  type CategoriaAcervo,
  type RegistroAcervo,
} from './tipos';
import s from './acervo.module.css';

interface Props {
  registros: RegistroAcervo[];
  /** Recorte por ano, vindo da linha do tempo. */
  ano?: number | null;
  /** Lê e grava os filtros na URL (na página /acervo). */
  naUrl?: boolean;
}

const CATEGORIAS: CategoriaAcervo[] = ['revogado', 'nao_recepcionado', 'vetado', 'vigencia_encerrada'];

function doAno(r: RegistroAcervo, ano: number): boolean {
  return (
    r.normas.some((n) => anoDaSaida(r, n) === ano) ||
    (r.publicacao !== null && Number(r.publicacao.data.slice(0, 4)) === ano)
  );
}

export default function ListaAcervo({registros, ano = null, naUrl = false}: Props) {
  const [q, setQ] = useState('');
  const [categoria, setCategoria] = useState<CategoriaAcervo | ''>('');
  const [artigo, setArtigo] = useState('');
  const [aberto, setAberto] = useState<string | null>(null);
  const [montado, setMontado] = useState(false);

  useEffect(() => {
    if (naUrl) {
      const p = new URLSearchParams(window.location.search);
      setQ(p.get('q') ?? '');
      const c = p.get('categoria') as CategoriaAcervo | null;
      if (c && CATEGORIAS.includes(c)) setCategoria(c);
      setArtigo(p.get('artigo') ?? '');
      const alvo = window.location.hash.slice(1);
      if (alvo && registros.some((r) => r.id === alvo)) setAberto(alvo);
    }
    setMontado(true);
  }, [naUrl, registros]);

  useEffect(() => {
    if (!naUrl || !montado) return;
    // Parte da URL atual: o ?ano= é da linha do tempo, e não se perde aqui.
    const p = new URLSearchParams(window.location.search);
    for (const [chave, valor] of [['q', q.trim()], ['categoria', categoria], ['artigo', artigo]] as const) {
      if (valor) p.set(chave, valor);
      else p.delete(chave);
    }
    const s2 = p.toString();
    const novo = window.location.pathname + (s2 ? `?${s2}` : '') + window.location.hash;
    if (novo !== window.location.pathname + window.location.search + window.location.hash) {
      window.history.replaceState(null, '', novo);
    }
  }, [q, categoria, artigo, naUrl, montado]);

  const base = registros.filter(
    (r) =>
      (ano === null || doAno(r, ano)) &&
      (!artigo || r.artigos.includes(artigo)) &&
      (!q.trim() ||
        normalizar(`${r.nome} ${r.dispositivo} ${r.oQueHouve} ${r.normas.map((n) => n.norma).join(' ')}`).includes(
          normalizar(q.trim()),
        )),
  );
  const visiveis = base.filter((r) => !categoria || r.categoria === categoria);
  const contagem = (c: CategoriaAcervo) => base.filter((r) => r.categoria === c).length;

  return (
    <div className={s.lista}>
      <div className={s.buscaAcervo}>
        <label className="sr-only" htmlFor={`busca-acervo${ano ?? ''}`}>
          Buscar no acervo
        </label>
        <input
          id={`busca-acervo${ano ?? ''}`}
          type="search"
          placeholder="Buscar por dispositivo, crime ou norma revogadora…"
          value={q}
          onChange={(ev) => setQ(ev.target.value)}
        />
        <span className={s.contagem} aria-live="polite">
          {visiveis.length} de {registros.length} registros
        </span>
      </div>
      <div className={s.chips} role="group" aria-label="Categoria">
        <button type="button" aria-pressed={categoria === ''} className={`${s.chip} ${categoria === '' ? s.chipAtivo : ''}`} onClick={() => setCategoria('')}>
          tudo <span className="num">{base.length}</span>
        </button>
        {CATEGORIAS.map((c) => (
          <button
            key={c}
            type="button"
            aria-pressed={categoria === c}
            className={`${s.chip} ${categoria === c ? s.chipAtivo : ''}`}
            onClick={() => setCategoria(categoria === c ? '' : c)}
          >
            {ROTULO_CATEGORIA[c]} <span className="num">{contagem(c)}</span>
          </button>
        ))}
      </div>

      {artigo && (
        <p className={s.recorte}>
          Recorte no artigo <code>{artigo}</code>, vindo da ficha do tipo penal.{' '}
          <button type="button" className={s.botaoLink} onClick={() => setArtigo('')}>
            ver o acervo inteiro
          </button>
        </p>
      )}

      {visiveis.length === 0 ? (
        <p className={s.vazio}>
          {artigo
            ? 'Nenhum registro do acervo neste artigo. O acervo reúne o que saiu de vigência; as redações anteriores de um artigo ainda vigente ficam na aba histórico da ficha do tipo.'
            : ano !== null
              ? 'Nenhum registro do acervo neste ano.'
              : 'Nenhum registro responde a essa busca.'}
        </p>
      ) : (
        <ul className={s.registros}>
          {visiveis.map((r) => {
            const estaAberto = aberto === r.id;
            return (
              <li key={r.id} id={r.id} className={`${s.registro} ${estaAberto ? s.registroAberto : ''}`}>
                <button
                  type="button"
                  className={s.cabecaRegistro}
                  aria-expanded={estaAberto}
                  aria-controls={`corpo-${r.id}`}
                  onClick={() => setAberto(estaAberto ? null : r.id)}
                >
                  <span className={s.dispositivo}>{r.dispositivo}</span>
                  <span className={s.nome}>{r.nome}</span>
                  <span className={`${s.tag} ${s[`tag_${r.categoria}`]}`}>{ROTULO_CATEGORIA[r.categoria]}</span>
                  <span className={s.seta} aria-hidden="true">
                    ›
                  </span>
                </button>
                {estaAberto && (
                  <div className={s.corpoRegistro} id={`corpo-${r.id}`}>
                    <div className={s.colunaTexto}>
                      <span className="rotulo">O que houve</span>
                      <p>{r.oQueHouve}</p>
                      <span className="rotulo">Texto original</span>
                      {r.textoOriginal ? (
                        <blockquote className={s.textoOriginal}>{r.textoOriginal}</blockquote>
                      ) : r.tipo === 'diploma' ? (
                        <p className={s.ausente}>{avisoDoTextoInteiro(r.fonteTexto)}</p>
                      ) : (
                        <p className={s.ausente}>
                          Ainda não transcrito. Entra quando o registro for conferido contra o texto compilado; até lá,
                          a ficha diz o que se sabe e declara o que falta.
                        </p>
                      )}
                    </div>
                    <div className={s.colunaTempo}>
                      <span className="rotulo">Linha do tempo {r.tipo === 'diploma' ? 'do diploma' : 'do dispositivo'}</span>
                      <ol className={s.passos}>
                        {passosDoRegistro(r).map((p, i) => (
                          <li key={i}>
                            <span className={`${s.quando} num`}>{p.quando}</span>
                            <span className={s.pontoPasso} aria-hidden="true" />
                            <span className={s.fatoPasso}>
                              <span>{p.fato}</span>
                              <span className={s.normaPasso}>{p.norma}</span>
                            </span>
                          </li>
                        ))}
                      </ol>
                      <span className={s.linksRegistro}>
                        <a href={caminho(`/acervo/${r.id}`)}>ficha do registro →</a>
                        {r.fonteUrl && (
                          <a href={r.fonteUrl} rel="noopener" target="_blank">
                            {rotuloDaFonte(r.fonteTexto)}
                          </a>
                        )}
                      </span>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
