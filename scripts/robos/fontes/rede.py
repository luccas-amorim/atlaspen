# -*- coding: utf-8 -*-
"""A rede dos robôs: uma porta só para toda requisição HTTP.

Até 25/10/2026 cada robô tinha a sua — `nucleo/baixar.py`,
`recenseador/leis_do_ano.py`, `sentinela/dou_watcher.py` e
`inventario_diplomas.py` —, com os mesmos cabeçalhos copiados e as mesmas
novas tentativas reescritas quatro vezes, cada uma do seu jeito. As fontes que
entram agora (Senado, normas.leg.br, GitHub) chegariam como a quinta, a sexta e
a sétima cópia.

O que mora aqui é só o transporte: cabeçalhos, novas tentativas, espera entre
elas, intervalo mínimo entre requisições e a separação entre "a página não
existe" e "a rede falhou". `obter` devolve BYTES.

O que NÃO mora aqui é a decodificação. O Planalto mistura cp1252 sem declarar e
UTF-16 com BOM, e decodificar errado não quebra: corrompe em silêncio (ver
`nucleo/baixar.py`). Cada fonte decodifica o que é seu, com o rigor que a sua
fonte pede. Por isso o `decodificar` do ctresb, que usa `errors="replace"` na
primeira tentativa, NÃO veio junto.

`Limitador` e `Rede` são adaptados de `scripts/comum.py` do ctresb/leis
(commit deea03b), MIT, Copyright (c) 2026 João Davi — o aviso completo da
licença está em `LICENSE-ctresb-leis.txt`, nesta pasta.
"""
from __future__ import annotations

import http.client
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Iterable

# UA de navegador: sem ele o Planalto recusa a conexão (verificado na F0), e o
# in.gov.br quer ainda Accept e Accept-Language de navegador, senão devolve 403.
UA_NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


class FalhaDeRede(RuntimeError):
    """A rede falhou depois de todas as tentativas.

    `causa` é a última exceção, para quem precisa distinguir HTTP de conexão.
    """

    def __init__(self, url: str, tentativas: int, causa: BaseException | None):
        plural = "tentativa" if tentativas == 1 else "tentativas"
        super().__init__(f"falha após {tentativas} {plural}: {causa}")
        self.url = url
        self.tentativas = tentativas
        self.causa = causa


class Limitador:
    """Intervalo mínimo entre o início de duas requisições, entre threads.

    Adaptado do `Limitador` do ctresb/leis, que contava em requisições por
    segundo; aqui o número é o intervalo em segundos, que é como os robôs
    sempre o escreveram (`PAUSA = 1.2`). Intervalo zero não espera.
    """

    def __init__(self, intervalo: float,
                 relogio: Callable[[], float] = time.monotonic,
                 dormir: Callable[[float], None] = time.sleep):
        self.intervalo = intervalo
        self._relogio = relogio
        self._dormir = dormir
        self._proxima = relogio()
        self._trava = threading.Lock()

    def esperar(self) -> None:
        if self.intervalo <= 0:
            return
        with self._trava:
            agora = self._relogio()
            if self._proxima > agora:
                self._dormir(self._proxima - agora)
                agora = self._proxima
            self._proxima = agora + self.intervalo


class Rede:
    """GET com cabeçalhos fixos, novas tentativas e ausência declarada.

    - `ausentes`: códigos HTTP que querem dizer "isto não existe" — o número de
      lei que ainda não saiu, o dia sem edição do DOU. Viram `None` na hora, sem
      nova tentativa.
    - Qualquer outro erro HTTP, de conexão ou de tempo esgotado é tentado de
      novo, com `espera(n)` segundos depois da n-ésima falha. Esgotadas as
      tentativas, `FalhaDeRede`.
    """

    def __init__(self, cabecalhos: dict[str, str], *, tentativas: int = 3,
                 timeout: float = 60, espera: Callable[[int], float] = lambda n: 2 * n,
                 intervalo: float = 0.0,
                 dormir: Callable[[float], None] = time.sleep):
        self.cabecalhos = dict(cabecalhos)
        self.tentativas = tentativas
        self.timeout = timeout
        self.espera = espera
        self.limitador = Limitador(intervalo, dormir=dormir)
        self._dormir = dormir

    def obter(self, url: str, *, ausentes: Iterable[int] = (404,),
              tentativas: int | None = None,
              cabecalhos: dict[str, str] | None = None,
              corpo: bytes | None = None) -> bytes | None:
        """GET, ou POST quando há `corpo` (a API do CNJ só responde a POST)."""
        ausentes = frozenset(ausentes)
        total = tentativas or self.tentativas
        pedido = urllib.request.Request(url, data=corpo, headers={**self.cabecalhos, **(cabecalhos or {})})
        ultimo: BaseException | None = None
        for n in range(1, total + 1):
            self.limitador.esperar()
            try:
                with urllib.request.urlopen(pedido, timeout=self.timeout) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                if e.code in ausentes:
                    return None
                ultimo = e
            # `http.client.HTTPException` cobre a resposta que chega pela metade
            # (`IncompleteRead`): não é OSError, e na primeira rodada real do
            # Cotejador, em 25/10/2026, uma ficha do Senado de 226 KB truncada
            # escapou por aqui e derrubou a execução inteira.
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
                ultimo = e
            if n < total:
                self._dormir(self.espera(n))
        raise FalhaDeRede(url, total, ultimo)
