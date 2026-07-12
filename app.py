"""
Dashboard Olho Vivo (SPTrans) - Streamlit
Cobre todos os endpoints da API v2.1: Linhas, Paradas, Corredores, Empresas,
Posição dos veículos e Previsão de chegada.

Rodar com: streamlit run app.py
"""

import os
import time
from datetime import datetime

import pandas as pd
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv

from sptrans_client import SPTransClient, SPTransAuthError, SPTransAPIError, CLIENT_VERSION

load_dotenv()

st.set_page_config(
    page_title="Olho Vivo Dashboard",
    page_icon="🚌",
    layout="wide",
)

# ------------------------------------------------------------------
# Autenticação / Cliente (cacheado por sessão do Streamlit)
# ------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_client(token: str) -> SPTransClient:
    client = SPTransClient(token)
    client.autenticar()
    return client


def carregar_token() -> str:
    """Lê o token exclusivamente de st.secrets (Streamlit Cloud) ou .env (local).
    Não há campo de digitação: o token nunca aparece na tela."""
    try:
        return st.secrets["SPTRANS_TOKEN"]
    except (KeyError, FileNotFoundError):
        return os.getenv("SPTRANS_TOKEN", "")


st.sidebar.title("🚌 Olho Vivo Dashboard")
token = carregar_token()

if not token:
    st.error(
        "Token não configurado. Adicione `SPTRANS_TOKEN = \"seu_token\"` em "
        "App settings → Secrets (Streamlit Cloud) ou no arquivo `.env` (local)."
    )
    st.stop()

try:
    client = get_client(token)
except SPTransAuthError as e:
    st.error(f"❌ Falha de autenticação: {e}")
    st.info(
        "Dica: se você estiver no Streamlit Community Cloud, a SPTrans às vezes "
        "bloqueia por firewall os IPs de provedores de nuvem/datacenter. Isso é um "
        "bloqueio do lado da SPTrans, não um bug no código — nesse caso, considere "
        "rodar localmente ou usar um servidor com IP residencial/dedicado."
    )
    st.stop()
except Exception as e:
    st.error(f"Falha inesperada ao autenticar na API: {e}")
    st.stop()

st.sidebar.success("Autenticado ✅")
st.sidebar.caption(f"Última renovação de sessão: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.caption(f"🔧 sptrans_client versão: `{CLIENT_VERSION}`")


def call_api(func, *args, **kwargs):
    """Executa uma chamada à API tratando erros de forma visível ao usuário,
    em vez de deixar o Streamlit redigir a exceção."""
    try:
        return func(*args, **kwargs)
    except SPTransAuthError as e:
        st.error(f"❌ Sessão expirou ou token foi recusado: {e}")
        return None
    except SPTransAPIError as e:
        st.error(f"❌ Erro ao consultar a API: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Erro inesperado: {e}")
        return None

# ------------------------------------------------------------------
# Navegação por abas — uma por categoria da API
# ------------------------------------------------------------------
tab_linhas, tab_paradas, tab_corredores, tab_empresas, tab_posicao, tab_previsao, tab_mapa = st.tabs(
    [
        "🔎 Linhas",
        "📍 Paradas",
        "🛣️ Corredores",
        "🏢 Empresas",
        "🚍 Posição dos Veículos",
        "⏱️ Previsão de Chegada",
        "🗺️ Mapa Geral (Tempo Real)",
    ]
)

# ==================== LINHAS ====================
with tab_linhas:
    st.header("Buscar Linhas")
    st.caption("Aceita número ou nome da linha (total ou parcial). Ex: 8000, Lapa, Ramos")

    col1, col2 = st.columns([3, 1])
    with col1:
        termo_linha = st.text_input(
            "Termo de busca",
            value="",
            placeholder="Ex: 8000, Lapa, Ramos — deixe em branco para listar todas as linhas",
            key="termo_linha",
        )
    with col2:
        filtrar_sentido = st.selectbox(
            "Sentido (opcional)",
            options=["Ambos", "1 - Principal → Secundário", "2 - Secundário → Principal"],
            key="sentido_linha",
        )

    if st.button("Buscar linhas", key="btn_buscar_linha"):
        if not termo_linha.strip():
            st.info("Nenhum termo informado — retornando **todas as linhas** do sistema.")
        with st.spinner("Consultando API..."):
            if filtrar_sentido == "Ambos":
                resultado = call_api(client.buscar_linhas, termo_linha.strip())
            else:
                sentido_num = 1 if filtrar_sentido.startswith("1") else 2
                resultado = call_api(client.buscar_linha_sentido, termo_linha.strip(), sentido_num)

        if resultado:
            df = pd.DataFrame(resultado)
            df = df.rename(
                columns={
                    "cl": "Código Linha",
                    "lc": "Circular?",
                    "lt": "Letreiro (nº)",
                    "sl": "Sentido",
                    "tl": "Tipo",
                    "tp": "Terminal Principal → Secundário",
                    "ts": "Terminal Secundário → Principal",
                }
            )
            st.dataframe(df, use_container_width=True)
            st.session_state["ultimas_linhas"] = resultado
            st.caption(f"{len(resultado)} linha(s) encontrada(s).")
        else:
            st.info("Nenhuma linha encontrada para esse termo.")

# ==================== PARADAS ====================
with tab_paradas:
    st.header("Buscar Paradas")

    modo_parada = st.radio(
        "Tipo de busca",
        options=["Por nome/endereço", "Por código de linha", "Por código de corredor"],
        horizontal=True,
        key="modo_parada",
    )

    resultado_paradas = []

    if modo_parada == "Por nome/endereço":
        termo_parada = st.text_input("Nome da parada ou endereço", value="Afonso", key="termo_parada")
        if st.button("Buscar paradas", key="btn_buscar_parada"):
            with st.spinner("Consultando API..."):
                resultado_paradas = call_api(client.buscar_paradas, termo_parada)

    elif modo_parada == "Por código de linha":
        codigo_linha_parada = st.number_input(
            "Código da linha (obtido na aba Linhas)", min_value=0, step=1, key="cod_linha_parada"
        )
        if st.button("Buscar paradas da linha", key="btn_buscar_parada_linha"):
            with st.spinner("Consultando API..."):
                resultado_paradas = call_api(client.buscar_paradas_por_linha, int(codigo_linha_parada))

    else:  # Por corredor
        corredores = call_api(client.listar_corredores)
        opcoes_corredor = {f"{c['nc']} (cód. {c['cc']})": c["cc"] for c in (corredores or [])}
        if opcoes_corredor:
            escolha_corredor = st.selectbox("Corredor", options=list(opcoes_corredor.keys()), key="sel_corredor_parada")
            if st.button("Buscar paradas do corredor", key="btn_buscar_parada_corredor"):
                with st.spinner("Consultando API..."):
                    resultado_paradas = call_api(client.buscar_paradas_por_corredor, opcoes_corredor[escolha_corredor])
        else:
            st.info("Não foi possível carregar a lista de corredores.")

    if resultado_paradas:
        df_p = pd.DataFrame(resultado_paradas).rename(
            columns={"cp": "Código Parada", "np": "Nome", "ed": "Endereço", "py": "lat", "px": "lon"}
        )
        st.dataframe(df_p, use_container_width=True)
        st.caption(f"{len(resultado_paradas)} parada(s) encontrada(s).")

        if {"lat", "lon"}.issubset(df_p.columns):
            st.map(df_p.rename(columns={"lat": "latitude", "lon": "longitude"})[["latitude", "longitude"]])

# ==================== CORREDORES ====================
with tab_corredores:
    st.header("Corredores Inteligentes")
    if st.button("Listar corredores", key="btn_corredores"):
        with st.spinner("Consultando API..."):
            corredores = call_api(client.listar_corredores)
        if corredores:
            df_c = pd.DataFrame(corredores).rename(columns={"cc": "Código", "nc": "Nome"})
            st.dataframe(df_c, use_container_width=True)
            st.caption(f"{len(corredores)} corredor(es) cadastrados.")
        else:
            st.info("Nenhum corredor retornado.")

# ==================== EMPRESAS ====================
with tab_empresas:
    st.header("Empresas Operadoras")
    if st.button("Listar empresas", key="btn_empresas"):
        with st.spinner("Consultando API..."):
            dados_emp = call_api(client.listar_empresas)

        linhas_flat = []
        estrutura_inesperada = False
        for area_bloco in (dados_emp or []):
            if not isinstance(area_bloco, dict):
                estrutura_inesperada = True
                continue
            for area in area_bloco.get("e", []):
                if not isinstance(area, dict):
                    estrutura_inesperada = True
                    continue
                cod_area = area.get("a")
                for emp in area.get("e", []):
                    if not isinstance(emp, dict):
                        estrutura_inesperada = True
                        continue
                    linhas_flat.append(
                        {
                            "Área": cod_area,
                            "Código Empresa": emp.get("c"),
                            "Nome": emp.get("n"),
                        }
                    )

        if estrutura_inesperada:
            st.warning(
                "A API retornou parte dos dados em um formato inesperado (itens ignorados). "
                "Exibindo o que foi possível interpretar abaixo."
            )
            with st.expander("Ver resposta bruta da API (debug)"):
                st.json(dados_emp)

        if linhas_flat:
            df_emp = pd.DataFrame(linhas_flat)
            areas_disponiveis = sorted(df_emp["Área"].unique())
            area_filtro = st.multiselect("Filtrar por área", options=areas_disponiveis, default=areas_disponiveis)
            df_emp_filtrado = df_emp[df_emp["Área"].isin(area_filtro)]
            st.dataframe(df_emp_filtrado, use_container_width=True)
            st.caption(f"{len(df_emp_filtrado)} empresa(s) exibidas de {len(df_emp)} totais.")
        else:
            st.info("Nenhuma empresa retornada.")

# ==================== POSIÇÃO DOS VEÍCULOS ====================
with tab_posicao:
    st.header("Posição dos Veículos em Tempo Real")

    modo_pos = st.radio(
        "Filtro",
        options=["Todos os veículos", "Por linha", "Por empresa/garagem"],
        horizontal=True,
        key="modo_pos",
    )

    if modo_pos == "Todos os veículos":
        st.caption("Retorna a posição de TODOS os veículos em operação agora (pode ser um volume grande).")
        if st.button("Atualizar posições", key="btn_pos_todos"):
            with st.spinner("Consultando API..."):
                dados = call_api(client.posicao_todos)
            linhas = (dados or {}).get("l", [])
            registros = []
            for linha in linhas:
                for v in linha.get("vs", []):
                    registros.append(
                        {
                            "Letreiro": linha.get("c"),
                            "Código Linha": linha.get("cl"),
                            "Sentido": linha.get("sl"),
                            "Destino": linha.get("lt0"),
                            "Origem": linha.get("lt1"),
                            "Prefixo Veículo": v.get("p"),
                            "Acessível": v.get("a"),
                            "Horário Captura (UTC)": v.get("ta"),
                            "lat": v.get("py"),
                            "lon": v.get("px"),
                        }
                    )
            if dados is not None and registros:
                df_pos = pd.DataFrame(registros)
                st.caption(f"Horário de referência da API: {dados.get('hr')} | {len(df_pos)} veículo(s)")

                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    so_acessiveis = st.checkbox("Somente veículos acessíveis", key="chk_acessivel_todos")
                with col_f2:
                    filtro_letreiro = st.text_input("Filtrar por letreiro contém", value="", key="filtro_letreiro_todos")

                if so_acessiveis:
                    df_pos = df_pos[df_pos["Acessível"] == True]
                if filtro_letreiro:
                    df_pos = df_pos[df_pos["Letreiro"].str.contains(filtro_letreiro, case=False, na=False)]

                st.dataframe(df_pos, use_container_width=True)
                st.map(df_pos.rename(columns={"lat": "latitude", "lon": "longitude"})[["latitude", "longitude"]])
            else:
                st.info("Nenhum veículo retornado no momento.")

    elif modo_pos == "Por linha":
        codigo_linha_pos = st.number_input(
            "Código da linha (obtido na aba Linhas)", min_value=0, step=1, key="cod_linha_pos"
        )
        if st.button("Consultar posição da linha", key="btn_pos_linha"):
            with st.spinner("Consultando API..."):
                dados = call_api(client.posicao_por_linha, int(codigo_linha_pos))
            veiculos = (dados or {}).get("vs", [])
            if veiculos:
                df_v = pd.DataFrame(veiculos).rename(
                    columns={"p": "Prefixo", "a": "Acessível", "ta": "Horário (UTC)", "py": "lat", "px": "lon"}
                )
                st.caption(f"Horário de referência: {dados.get('hr')} | {len(df_v)} veículo(s) na linha")
                st.dataframe(df_v, use_container_width=True)
                st.map(df_v.rename(columns={"lat": "latitude", "lon": "longitude"})[["latitude", "longitude"]])
            else:
                st.info("Nenhum veículo encontrado para essa linha no momento.")

    else:  # Por empresa/garagem
        empresas = call_api(client.listar_empresas)
        opcoes_emp = {}
        for area_bloco in (empresas or []):
            if not isinstance(area_bloco, dict):
                continue
            for area in area_bloco.get("e", []):
                if not isinstance(area, dict):
                    continue
                for emp in area.get("e", []):
                    if not isinstance(emp, dict):
                        continue
                    opcoes_emp[f"{emp.get('n')} (cód. {emp.get('c')})"] = emp.get("c")

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            if opcoes_emp:
                escolha_emp = st.selectbox("Empresa", options=list(opcoes_emp.keys()), key="sel_empresa_pos")
                codigo_empresa = opcoes_emp[escolha_emp]
            else:
                codigo_empresa = st.number_input("Código da empresa", min_value=0, step=1, key="cod_empresa_manual")
        with col_e2:
            codigo_linha_garagem = st.number_input(
                "Código da linha (opcional)", min_value=0, step=1, key="cod_linha_garagem"
            )

        if st.button("Consultar veículos na garagem", key="btn_pos_garagem"):
            with st.spinner("Consultando API..."):
                dados = call_api(client.posicao_por_garagem, 
                    int(codigo_empresa), int(codigo_linha_garagem) if codigo_linha_garagem else None
                )
            linhas = (dados or {}).get("l", [])
            registros = []
            for linha in linhas:
                for v in linha.get("vs", []):
                    registros.append(
                        {
                            "Letreiro": linha.get("c"),
                            "Código Linha": linha.get("cl"),
                            "Prefixo Veículo": v.get("p"),
                            "Acessível": v.get("a"),
                            "Horário (UTC)": v.get("ta"),
                            "lat": v.get("py"),
                            "lon": v.get("px"),
                        }
                    )
            if registros:
                df_g = pd.DataFrame(registros)
                st.dataframe(df_g, use_container_width=True)
                st.map(df_g.rename(columns={"lat": "latitude", "lon": "longitude"})[["latitude", "longitude"]])
            else:
                st.info("Nenhum veículo encontrado.")

# ==================== PREVISÃO DE CHEGADA ====================
with tab_previsao:
    st.header("Previsão de Chegada")

    modo_prev = st.radio(
        "Filtro",
        options=["Por parada + linha", "Por linha (todas as paradas)", "Por parada (todas as linhas)"],
        horizontal=True,
        key="modo_prev",
    )

    if modo_prev == "Por parada + linha":
        col1, col2 = st.columns(2)
        with col1:
            cod_parada_prev = st.number_input("Código da parada", min_value=0, step=1, key="cod_parada_prev1")
        with col2:
            cod_linha_prev = st.number_input("Código da linha", min_value=0, step=1, key="cod_linha_prev1")

        if st.button("Consultar previsão", key="btn_prev1"):
            with st.spinner("Consultando API..."):
                dados = call_api(client.previsao_parada_linha, int(cod_parada_prev), int(cod_linha_prev))
            p = (dados or {}).get("p", {})
            if p:
                st.subheader(f"📍 {p.get('np')}")
                registros = []
                for linha in p.get("l", []):
                    for v in linha.get("vs", []):
                        registros.append(
                            {
                                "Letreiro": linha.get("c"),
                                "Destino": linha.get("lt0"),
                                "Prefixo Veículo": v.get("p"),
                                "Previsão Chegada": v.get("t"),
                                "Acessível": v.get("a"),
                            }
                        )
                if registros:
                    st.caption(f"Horário de referência: {dados.get('hr')}")
                    st.dataframe(pd.DataFrame(registros), use_container_width=True)
                else:
                    st.info("Nenhuma previsão disponível no momento.")
            else:
                st.info("Nenhum dado retornado — verifique os códigos informados.")

    elif modo_prev == "Por linha (todas as paradas)":
        cod_linha_prev2 = st.number_input("Código da linha", min_value=0, step=1, key="cod_linha_prev2")
        if st.button("Consultar previsão da linha", key="btn_prev2"):
            with st.spinner("Consultando API..."):
                dados = call_api(client.previsao_por_linha, int(cod_linha_prev2))
            paradas = (dados or {}).get("ps", [])
            registros = []
            for parada in paradas:
                for v in parada.get("vs", []):
                    registros.append(
                        {
                            "Parada": parada.get("np"),
                            "Código Parada": parada.get("cp"),
                            "Prefixo Veículo": v.get("p"),
                            "Previsão Chegada": v.get("t"),
                            "Acessível": v.get("a"),
                        }
                    )
            if registros:
                df_prev2 = pd.DataFrame(registros)
                st.caption(f"Horário de referência: {dados.get('hr')} | {len(paradas)} parada(s)")

                filtro_parada_nome = st.text_input("Filtrar parada por nome contém", value="", key="filtro_parada_nome")
                if filtro_parada_nome:
                    df_prev2 = df_prev2[df_prev2["Parada"].str.contains(filtro_parada_nome, case=False, na=False)]

                st.dataframe(df_prev2, use_container_width=True)
            else:
                st.info("Nenhuma previsão disponível para essa linha no momento.")

    else:  # Por parada
        cod_parada_prev3 = st.number_input("Código da parada", min_value=0, step=1, key="cod_parada_prev3")
        if st.button("Consultar previsão da parada", key="btn_prev3"):
            with st.spinner("Consultando API..."):
                dados = call_api(client.previsao_por_parada, int(cod_parada_prev3))
            p = (dados or {}).get("p", {})
            if p:
                st.subheader(f"📍 {p.get('np')}")
                registros = []
                for linha in p.get("l", []):
                    for v in linha.get("vs", []):
                        registros.append(
                            {
                                "Letreiro": linha.get("c"),
                                "Código Linha": linha.get("cl"),
                                "Destino": linha.get("lt0"),
                                "Origem": linha.get("lt1"),
                                "Prefixo Veículo": v.get("p"),
                                "Previsão Chegada": v.get("t"),
                                "Acessível": v.get("a"),
                            }
                        )
                if registros:
                    df_prev3 = pd.DataFrame(registros)
                    letreiros_disponiveis = sorted(df_prev3["Letreiro"].unique())
                    filtro_letreiro_prev = st.multiselect(
                        "Filtrar por linha(s)", options=letreiros_disponiveis, default=letreiros_disponiveis
                    )
                    df_prev3 = df_prev3[df_prev3["Letreiro"].isin(filtro_letreiro_prev)]
                    st.caption(f"Horário de referência: {dados.get('hr')}")
                    st.dataframe(df_prev3, use_container_width=True)
                else:
                    st.info("Nenhuma previsão disponível no momento.")
            else:
                st.info("Nenhum dado retornado — verifique o código informado.")

# ==================== MAPA GERAL / TEMPO REAL ====================
with tab_mapa:
    st.header("Mapa Geral — Frota em Tempo Real")
    st.caption(
        "Puxa a posição de todos os veículos (GET /Posicao) e permite filtrar por letreiro/linha, "
        "acessibilidade e visualizar num mapa interativo com auto-refresh opcional."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_letreiro_mapa = st.text_input("Filtrar por letreiro contém (ex: 8000)", value="", key="filtro_mapa")
    with col2:
        so_acessiveis_mapa = st.checkbox("Somente acessíveis", key="chk_acessivel_mapa")
    with col3:
        auto_refresh = st.checkbox("Auto-atualizar a cada 30s", key="chk_autorefresh")

    placeholder = st.empty()

    def carregar_e_exibir():
        dados = call_api(client.posicao_todos)
        linhas = (dados or {}).get("l", [])
        registros = []
        for linha in linhas:
            for v in linha.get("vs", []):
                registros.append(
                    {
                        "Letreiro": linha.get("c"),
                        "Código Linha": linha.get("cl"),
                        "Destino": linha.get("lt0"),
                        "Origem": linha.get("lt1"),
                        "Prefixo": v.get("p"),
                        "Acessível": v.get("a"),
                        "lat": v.get("py"),
                        "lon": v.get("px"),
                    }
                )
        df = pd.DataFrame(registros)

        if not df.empty:
            if filtro_letreiro_mapa:
                df = df[df["Letreiro"].str.contains(filtro_letreiro_mapa, case=False, na=False)]
            if so_acessiveis_mapa:
                df = df[df["Acessível"] == True]

        with placeholder.container():
            st.caption(f"Horário de referência API: {dados.get('hr')} | {len(df)} veículo(s) exibidos")
            if not df.empty:
                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=df,
                    get_position="[lon, lat]",
                    get_color="[255, 90, 30, 160]",
                    get_radius=60,
                    pickable=True,
                )
                view_state = pdk.ViewState(
                    latitude=df["lat"].mean(), longitude=df["lon"].mean(), zoom=11
                )
                st.pydeck_chart(
                    pdk.Deck(
                        layers=[layer],
                        initial_view_state=view_state,
                        tooltip={"text": "{Letreiro}\nDestino: {Destino}\nPrefixo: {Prefixo}"},
                    )
                )
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Nenhum veículo encontrado com os filtros aplicados.")

    if st.button("Carregar frota agora", key="btn_carregar_mapa") or auto_refresh:
        carregar_e_exibir()
        if auto_refresh:
            time.sleep(30)
            st.rerun()
