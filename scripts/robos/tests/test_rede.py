# -*- coding: utf-8 -*-
"""Testes da rede comum dos robôs (`fontes/rede.py`).

Sem rede: o `urlopen` é substituído por um dublê que devolve, em ordem, as
respostas ou exceções de um roteiro, e conta as chamadas.
"""
import io
import urllib.error

import pytest

from fontes import rede as r


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(codigo: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://exemplo", codigo, "x", {}, None)


@pytest.fixture
def roteiro(monkeypatch):
    """roteiro([b"ok"]) faz o urlopen devolver b"ok"; exceções são levantadas."""
    chamadas = []

    def montar(passos):
        fila = list(passos)

        def falso(pedido, timeout):
            chamadas.append((pedido.full_url, dict(pedido.header_items()), timeout))
            passo = fila.pop(0)
            if isinstance(passo, BaseException):
                raise passo
            return _Resposta(passo)
        monkeypatch.setattr(r.urllib.request, "urlopen", falso)
        return chamadas
    return montar


def _rede(**kw):
    esperas = []
    rede = r.Rede({"User-Agent": "teste"}, dormir=esperas.append, **kw)
    return rede, esperas


def test_devolve_os_bytes_com_os_cabecalhos(roteiro):
    chamadas = roteiro([b"<html>ok</html>"])
    rede, _ = _rede()
    assert rede.obter("https://exemplo/a") == b"<html>ok</html>"
    url, cabecalhos, timeout = chamadas[0]
    assert url == "https://exemplo/a" and cabecalhos["User-agent"] == "teste" and timeout == 60


def test_codigo_ausente_vira_none_sem_nova_tentativa(roteiro):
    chamadas = roteiro([_http(404)])
    rede, esperas = _rede()
    assert rede.obter("https://exemplo", ausentes=(404,)) is None
    assert len(chamadas) == 1 and esperas == []


def test_sem_ausentes_404_e_falha_depois_das_tentativas(roteiro):
    """Para uma URL de `fontes.json`, 404 é página que sumiu: tem de derrubar."""
    chamadas = roteiro([_http(404)] * 3)
    rede, esperas = _rede(tentativas=3)
    with pytest.raises(r.FalhaDeRede) as e:
        rede.obter("https://exemplo", ausentes=())
    assert len(chamadas) == 3
    assert esperas == [2, 4]            # 2n depois da n-ésima falha, nunca depois da última
    assert isinstance(e.value.causa, urllib.error.HTTPError) and e.value.causa.code == 404
    assert str(e.value).startswith("falha após 3 tentativas:")


def test_conexao_que_volta_na_segunda_tentativa(roteiro):
    chamadas = roteiro([urllib.error.URLError("caiu"), b"voltou"])
    rede, esperas = _rede(tentativas=3, espera=lambda n: 3.6)
    assert rede.obter("https://exemplo") == b"voltou"
    assert len(chamadas) == 2 and esperas == [3.6]


def test_timeout_e_tentado_de_novo(roteiro):
    roteiro([TimeoutError(), TimeoutError()])
    rede, _ = _rede(tentativas=2)
    with pytest.raises(r.FalhaDeRede) as e:
        rede.obter("https://exemplo")
    assert isinstance(e.value.causa, TimeoutError)


def test_resposta_truncada_e_tentada_de_novo(roteiro):
    """`IncompleteRead` não é OSError: em 25/10/2026 escapou e derrubou o Cotejador."""
    import http.client
    chamadas = roteiro([http.client.IncompleteRead(b"meia ficha"), b"inteira"])
    rede, _ = _rede(tentativas=2)
    assert rede.obter("https://exemplo") == b"inteira"
    assert len(chamadas) == 2


def test_uma_tentativa_so_diz_tentativa_no_singular(roteiro):
    roteiro([urllib.error.URLError("caiu")])
    rede, esperas = _rede(tentativas=1)
    with pytest.raises(r.FalhaDeRede, match="falha após 1 tentativa:"):
        rede.obter("https://exemplo")
    assert esperas == []


def test_tentativas_por_chamada_vencem_as_da_rede(roteiro):
    chamadas = roteiro([_http(502), _http(502)])
    rede, _ = _rede(tentativas=5)
    with pytest.raises(r.FalhaDeRede):
        rede.obter("https://exemplo", tentativas=2)
    assert len(chamadas) == 2


class TestLimitador:
    def _relogio(self, instantes):
        fila = list(instantes)
        return lambda: fila.pop(0)

    def test_intervalo_zero_nunca_espera(self):
        esperas = []
        lim = r.Limitador(0, relogio=lambda: 0.0, dormir=esperas.append)
        lim.esperar()
        lim.esperar()
        assert esperas == []

    def test_espera_o_que_falta_do_intervalo(self):
        esperas = []
        # criação em 0; 1ª requisição em 0; 2ª em 0,5 — faltam 0,7 de 1,2
        lim = r.Limitador(1.2, relogio=self._relogio([0.0, 0.0, 0.5]), dormir=esperas.append)
        lim.esperar()
        lim.esperar()
        assert esperas == [pytest.approx(0.7)]

    def test_quem_chega_depois_do_intervalo_nao_espera(self):
        esperas = []
        lim = r.Limitador(1.2, relogio=self._relogio([0.0, 0.0, 5.0]), dormir=esperas.append)
        lim.esperar()
        lim.esperar()
        assert esperas == []
