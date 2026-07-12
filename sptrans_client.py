"""
Cliente para a API Olho Vivo (SPTrans) - v2.1
Documentação: https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api/

A API usa autenticação por cookie de sessão: primeiro faz-se um POST /Login/Autenticar
com o token, e o cookie retornado deve ser reutilizado nas chamadas seguintes.
Por isso usamos requests.Session() para persistir o cookie automaticamente.
"""

import requests
from typing import Optional, List, Dict, Any


BASE_URL = "https://api.olhovivo.sptrans.com.br/v2.1"

CLIENT_VERSION = "v2-diagnostico-401"  # marcador para confirmar que o deploy está atualizado


class SPTransAuthError(Exception):
    """Erro de autenticação (token inválido/expirado ou IP bloqueado pela SPTrans)."""


class SPTransAPIError(Exception):
    """Erro de chamada à API, com detalhes de status/corpo da resposta para diagnóstico."""


class SPTransClient:
    def __init__(self, token: str):
        if not token:
            raise ValueError("Token não informado. Configure SPTRANS_TOKEN no .env")
        self.token = token
        self.session = requests.Session()
        self._autenticado = False

    def autenticar(self) -> bool:
        """POST /Login/Autenticar?token={token} -> True/False. Cookie é salvo na Session."""
        url = f"{BASE_URL}/Login/Autenticar"
        try:
            resp = self.session.post(url, params={"token": self.token}, timeout=15)
        except requests.exceptions.RequestException as e:
            raise SPTransAuthError(
                f"Não foi possível conectar à API do Olho Vivo: {e}"
            ) from e

        if resp.status_code != 200:
            raise SPTransAuthError(
                f"Falha ao autenticar (HTTP {resp.status_code}). "
                f"Resposta da API: {resp.text[:300]!r}. "
                "Verifique se o token está correto/ativo em 'Meus Aplicativos'. "
                "Se o token estiver correto, a SPTrans pode estar bloqueando o IP "
                "deste servidor (comum em provedores de nuvem como Streamlit Cloud)."
            )

        self._autenticado = resp.text.strip().lower() == "true"
        if not self._autenticado:
            raise SPTransAuthError(
                "A API respondeu 200 mas recusou o token (retornou 'false'). "
                "Gere um novo token em 'Meus Aplicativos' no site da SPTrans e confirme "
                "que ele foi copiado sem espaços extras."
            )
        return self._autenticado

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        if not self._autenticado:
            self.autenticar()

        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=15)
        except requests.exceptions.RequestException as e:
            raise SPTransAPIError(f"Falha de conexão ao chamar {path}: {e}") from e

        # Se a sessão expirou (ou o cookie ficou inválido), tenta reautenticar do zero
        # usando uma NOVA sessão HTTP (evita reaproveitar cookie/conexão possivelmente
        # presos a um IP de saída diferente, comum em ambientes de nuvem com egress rotativo).
        if resp.status_code == 401:
            self.session = requests.Session()
            self._autenticado = False
            self.autenticar()
            try:
                resp = self.session.get(url, params=params, timeout=15)
            except requests.exceptions.RequestException as e:
                raise SPTransAPIError(f"Falha de conexão ao chamar {path}: {e}") from e

        if resp.status_code != 200:
            raise SPTransAPIError(
                f"Erro HTTP {resp.status_code} em {path}. "
                f"Resposta da API: {resp.text[:300]!r}"
            )

        if not resp.text:
            return None
        try:
            return resp.json()
        except ValueError as e:
            raise SPTransAPIError(
                f"Resposta de {path} não é JSON válido: {resp.text[:300]!r}"
            ) from e

    # ---------------- Linhas ----------------
    def buscar_linhas(self, termos_busca: str) -> List[Dict]:
        """GET /Linha/Buscar?termosBusca=... Aceita número ou nome (ex: 8000, Lapa)."""
        return self._get("/Linha/Buscar", {"termosBusca": termos_busca}) or []

    def buscar_linha_sentido(self, termos_busca: str, sentido: int) -> List[Dict]:
        """GET /Linha/BuscarLinhaSentido?termosBusca=...&sentido=1|2"""
        return self._get(
            "/Linha/BuscarLinhaSentido",
            {"termosBusca": termos_busca, "sentido": sentido},
        ) or []

    # ---------------- Paradas ----------------
    def buscar_paradas(self, termos_busca: str) -> List[Dict]:
        """GET /Parada/Buscar?termosBusca=... (nome ou endereço)"""
        return self._get("/Parada/Buscar", {"termosBusca": termos_busca}) or []

    def buscar_paradas_por_linha(self, codigo_linha: int) -> List[Dict]:
        """GET /Parada/BuscarParadasPorLinha?codigoLinha=..."""
        return self._get(
            "/Parada/BuscarParadasPorLinha", {"codigoLinha": codigo_linha}
        ) or []

    def buscar_paradas_por_corredor(self, codigo_corredor: int) -> List[Dict]:
        """GET /Parada/BuscarParadasPorCorredor?codigoCorredor=..."""
        return self._get(
            "/Parada/BuscarParadasPorCorredor", {"codigoCorredor": codigo_corredor}
        ) or []

    # ---------------- Corredores ----------------
    def listar_corredores(self) -> List[Dict]:
        """GET /Corredor"""
        return self._get("/Corredor") or []

    # ---------------- Empresas ----------------
    def listar_empresas(self) -> List[Dict]:
        """GET /Empresa"""
        return self._get("/Empresa") or []

    # ---------------- Posição dos veículos ----------------
    def posicao_todos(self) -> Dict:
        """GET /Posicao -> posição de TODOS os veículos de TODAS as linhas em operação"""
        return self._get("/Posicao") or {}

    def posicao_por_linha(self, codigo_linha: int) -> Dict:
        """GET /Posicao/Linha?codigoLinha=..."""
        return self._get("/Posicao/Linha", {"codigoLinha": codigo_linha}) or {}

    def posicao_por_garagem(
        self, codigo_empresa: int, codigo_linha: Optional[int] = None
    ) -> Dict:
        """GET /Posicao/Garagem?codigoEmpresa=...&codigoLinha=... (linha é opcional)"""
        params = {"codigoEmpresa": codigo_empresa}
        if codigo_linha:
            params["codigoLinha"] = codigo_linha
        return self._get("/Posicao/Garagem", params) or {}

    # ---------------- Previsão de chegada ----------------
    def previsao_parada_linha(self, codigo_parada: int, codigo_linha: int) -> Dict:
        """GET /Previsao?codigoParada=...&codigoLinha=..."""
        return self._get(
            "/Previsao", {"codigoParada": codigo_parada, "codigoLinha": codigo_linha}
        ) or {}

    def previsao_por_linha(self, codigo_linha: int) -> Dict:
        """GET /Previsao/Linha?codigoLinha=... -> previsão em todas as paradas da linha"""
        return self._get("/Previsao/Linha", {"codigoLinha": codigo_linha}) or {}

    def previsao_por_parada(self, codigo_parada: int) -> Dict:
        """GET /Previsao/Parada?codigoParada=... -> previsão de todas as linhas na parada"""
        return self._get("/Previsao/Parada", {"codigoParada": codigo_parada}) or {}
