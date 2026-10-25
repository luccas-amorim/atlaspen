# -*- coding: utf-8 -*-
"""Baixa os textos compilados do Planalto (F1 do conferidor).

Lê `data/fontes.json`, busca cada diploma e grava um snapshot **normalizado em
UTF-8** em `crawler/snapshots/<id>/<AAAA-MM-DD>.html`, com `meta.json` ao lado.

Por que normalizar na entrada: o Planalto serve o mesmo acervo em codificações
diferentes — a maioria em windows-1252 **sem** `<meta charset>`, e algumas
páginas (p.ex. a Lei 11.340) em **UTF-16 LE com BOM**. Decodificar errado não
quebra: corrompe em silêncio e faz a página parecer desatualizada (foi o que
gerou o falso "o Planalto serve cópia velha" na F0). A detecção fica aqui, uma
vez só, e todo o resto do pipeline lê UTF-8.

A **sentinela** de cada fonte é a prova de frescor/integridade: uma string que
tem de existir na página (a emenda mais recente já conferida, quando há). Se
faltar, o download é rejeitado em vez de alimentar o conferidor com texto velho
ou truncado.

**Snapshot no caminho canônico significa "conferido", por construção.** A página
é gravada primeiro em `<data>.html.part` e só é promovida a `<data>.html` quando
a sentinela passa. Até 25/09/2026 o arquivo era gravado direto no caminho final,
com o `sentinela_ok` só no `meta.json` — e nenhum consumidor lia o `meta.json`:
o Vigia, os dois auditores e o histórico varrem os `.html` por `glob`. Quem
rodava `baixar.py --todas` à mão recebia código de saída 2, mas o snapshot ruim
já estava no lugar do bom, e a rodada seguinte comparava o catálogo com ele. O
`.part` fica no diretório para diagnóstico e não casa com `*.html`.

Uso:
    python scripts/robos/nucleo/baixar.py --todas
    python scripts/robos/nucleo/baixar.py --fonte cp --fonte cpm
    python scripts/robos/nucleo/baixar.py --listar

Saídas: 0 = tudo certo; 2 = alguma fonte falhou (rede, HTTP ou sentinela).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
# `scripts/robos` para os pacotes dos robôs e do núcleo; `scripts` para o
# `pena_parser`, que é compartilhado com o construtor do catálogo e por isso
# não mora aqui. Os imports do núcleo vêm DEPOIS: rodado como script, o
# `sys.path[0]` é `scripts/robos/nucleo`, e `nucleo` não se resolve sem isto.
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fontes.rede import UA_NAVEGADOR, Rede  # noqa: E402
from nucleo.tempo import hoje  # noqa: E402

FONTES = RAIZ / "data" / "fontes.json"
SNAPSHOTS = RAIZ / "crawler" / "snapshots"

CORTESIA_S = 1.2   # intervalo entre requisições
TENTATIVAS = 3
TIMEOUT_S = 60
# Depois da n-ésima falha, espera de 2n segundos.
REDE = Rede({
    "User-Agent": UA_NAVEGADOR,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}, tentativas=TENTATIVAS, timeout=TIMEOUT_S, espera=lambda n: 2 * n)


def decodificar(bruto: bytes) -> tuple[str, str]:
    """(texto, codificação detectada). BOM > meta charset > windows-1252.

    O cp1252 é o fallback certo: quase todo o acervo antigo do Planalto vem
    nele, sem declarar. Nunca usa 'replace' silencioso na tentativa preferida —
    só no último recurso, para não perder a página inteira por um byte torto.
    """
    if bruto.startswith(b"\xff\xfe") or bruto.startswith(b"\xfe\xff"):
        # O Planalto às vezes acrescenta um byte solto ao fim do UTF-16 (um
        # espaço), o que quebra a decodificação estrita por "truncated data".
        # Descartar o byte ímpar final é seguro: é lixo de borda, não conteúdo.
        corpo = bruto[:-1] if len(bruto) % 2 else bruto
        return corpo.decode("utf-16"), "utf-16"
    if bruto.startswith(b"\xef\xbb\xbf"):
        return bruto.decode("utf-8-sig"), "utf-8-sig"

    cabeca = bruto[:4096].decode("latin-1", errors="replace")
    m = re.search(r'charset=["\']?([\w-]+)', cabeca, re.I)
    if m:
        try:
            return bruto.decode(m.group(1)), m.group(1).lower()
        except (LookupError, UnicodeDecodeError):
            pass
    try:
        return bruto.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return bruto.decode("windows-1252", errors="replace"), "windows-1252"


def normalizar(texto: str) -> str:
    """Texto comparável: entidades de espaço viram espaço, espaços colapsam."""
    t = texto.replace("&nbsp;", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t)


def buscar(url: str) -> bytes:
    """GET com UA de navegador, com repetição e espera progressiva.

    Nenhum código HTTP conta como ausência: a URL vem de `data/fontes.json`, e
    404 ali é página que mudou de lugar, que tem de derrubar o download.
    """
    return REDE.obter(url, ausentes=())


def baixar_fonte(fonte: dict, destino: Path) -> dict:
    """Baixa, valida a sentinela e grava snapshot + meta. Devolve o resultado."""
    bruto = buscar(fonte["url"])
    texto, codificacao = decodificar(bruto)
    plano = normalizar(texto)

    sentinela = fonte.get("sentinela") or ""
    ok = sentinela.lower() in plano.lower() if sentinela else True

    dir_fonte = destino / fonte["id"]
    dir_fonte.mkdir(parents=True, exist_ok=True)
    arquivo = dir_fonte / f"{hoje().isoformat()}.html"
    # Grava em `.part` e só promove quando a sentinela passa: o caminho
    # canônico nunca recebe página que não foi conferida.
    parcial = dir_fonte / f"{arquivo.name}.part"
    parcial.write_text(texto, encoding="utf-8")
    if ok:
        parcial.replace(arquivo)

    meta = {
        "id": fonte["id"],
        "url": fonte["url"],
        "baixado_em": hoje().isoformat(),
        "bytes_origem": len(bruto),
        "codificacao": codificacao,
        "sha256": hashlib.sha256(bruto).hexdigest(),
        "sentinela": sentinela,
        "sentinela_ok": ok,
        # O nome do arquivo que FICOU: o `.html` promovido, ou o `.part`
        # rejeitado, para que o meta nunca aponte para um snapshot que não existe.
        "arquivo": arquivo.name if ok else parcial.name,
    }
    (dir_fonte / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    # Só na CLI: como efeito de importação, fechava o stdout de quem importa
    # o módulo (o pytest, por exemplo).
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Baixa os compilados do Planalto.")
    p.add_argument("--fonte", action="append", default=[], metavar="ID",
                   help="id da fonte (repetível)")
    p.add_argument("--todas", action="store_true", help="baixa todas as fontes")
    p.add_argument("--listar", action="store_true", help="lista as fontes e sai")
    p.add_argument("--saida", default=str(SNAPSHOTS), help="diretório de saída")
    args = p.parse_args()

    fontes = json.loads(FONTES.read_text(encoding="utf-8"))["fontes"]
    if args.listar:
        for f in fontes:
            print(f"{f['id']:28s} {len(f['rotulos'])} rótulo(s)  {f['url']}")
        return 0

    alvo = fontes if args.todas else [f for f in fontes if f["id"] in set(args.fonte)]
    if not alvo:
        print("Nada a fazer: use --todas ou --fonte ID (veja --listar).")
        return 1

    destino = Path(args.saida)
    falhas: list[tuple[str, str]] = []
    for i, f in enumerate(alvo, 1):
        try:
            meta = baixar_fonte(f, destino)
        except Exception as e:                     # rede, HTTP, gravação
            falhas.append((f["id"], str(e)))
            print(f"[{i:2d}/{len(alvo)}] ✗ {f['id']:28s} {e}")
        else:
            if meta["sentinela_ok"]:
                print(f"[{i:2d}/{len(alvo)}] ✓ {f['id']:28s} "
                      f"{meta['bytes_origem']:8d}B  {meta['codificacao']}")
            else:
                falhas.append((f["id"], f"sentinela ausente: {meta['sentinela']!r}"))
                print(f"[{i:2d}/{len(alvo)}] ✗ {f['id']:28s} "
                      f"sentinela ausente: {meta['sentinela']!r} ({meta['codificacao']})")
        if i < len(alvo):
            time.sleep(CORTESIA_S)

    print(f"\n{len(alvo) - len(falhas)}/{len(alvo)} fontes íntegras.")
    if falhas:
        print("Falhas:")
        for fid, motivo in falhas:
            print(f"  {fid}: {motivo}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
