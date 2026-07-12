# 🚌 Olho Vivo Dashboard

Dashboard interativo em **Python + Streamlit** para explorar em tempo real os dados públicos da **API Olho Vivo**, da SPTrans — o sistema oficial de rastreamento do transporte público de São Paulo.

Cobre **todos os endpoints** da API v2.1: linhas, paradas, corredores, empresas, posição de veículos em tempo real e previsão de chegada, cada um com seus próprios filtros interativos.

---

## 📋 Sumário

- [Visão geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades)
- [Arquitetura do projeto](#-arquitetura-do-projeto)
- [Pré-requisitos](#-pré-requisitos)
- [Configuração do token da API](#-configuração-do-token-da-api)
- [Rodando localmente](#-rodando-localmente)
- [Deploy no Streamlit Community Cloud](#-deploy-no-streamlit-community-cloud)
- [Estrutura dos arquivos](#-estrutura-dos-arquivos)
- [Detalhes técnicos da autenticação](#-detalhes-técnicos-da-autenticação)
- [Solução de problemas](#-solução-de-problemas)
- [Segurança e boas práticas](#-segurança-e-boas-práticas)
- [Referências](#-referências)

---

## 🔎 Visão geral

A API Olho Vivo é a API pública da SPTrans que alimenta apps como o "Olho Vivo" oficial, com a localização de toda a frota de ônibus da cidade de São Paulo em tempo real, previsões de chegada por parada, cadastro de linhas, paradas, corredores e empresas operadoras.

Este projeto é um **cliente completo** dessa API, encapsulado em uma classe Python (`sptrans_client.py`) e exposto através de um dashboard Streamlit (`app.py`) com abas organizadas por categoria e filtros para cada tipo de consulta.

Documentação oficial da API:
https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api/

---

## ✨ Funcionalidades

O app é dividido em 8 abas:

| Aba | O que faz | Filtros disponíveis |
|---|---|---|
| 🔎 **Linhas** | Busca linhas de ônibus por número ou nome (via API, tempo real) | Termo de busca, sentido (Principal→Secundário / Secundário→Principal / ambos) |
| 📚 **Todas as Linhas (GTFS)** | Lista **todo** o cadastro de linhas do sistema, a partir do arquivo GTFS estático | Filtro por número/nome, por tipo de rota (`route_type`) |
| 📍 **Paradas** | Busca pontos de parada | Por nome/endereço, por código de linha, ou por código de corredor |
| 🛣️ **Corredores** | Lista todos os corredores inteligentes da cidade | — |
| 🏢 **Empresas** | Lista empresas operadoras do sistema | Filtro por área de operação |
| 🚍 **Posição dos Veículos** | Localização em tempo real da frota | Todos os veículos / por linha / por empresa-garagem, com filtro de acessibilidade e busca por letreiro |
| ⏱️ **Previsão de Chegada** | Previsão de chegada dos ônibus | Por parada+linha, por linha (todas as paradas), ou por parada (todas as linhas), com filtro multi-select de linhas |
| 🗺️ **Mapa Geral (Tempo Real)** | Mapa interativo com toda a frota em operação | Filtro por letreiro, somente acessíveis, auto-atualização a cada 30s |

Todos os resultados são exibidos em tabelas (`pandas`) e, quando fazem sentido geograficamente, em mapas (`st.map` ou `pydeck` para o mapa interativo).

### Por que uma aba separada para "Todas as Linhas"?

A API Olho Vivo **não tem um endpoint que liste todas as linhas de uma vez** —
o `/Linha/Buscar` exige um termo de busca (número ou nome), retornando `404`
se o parâmetro vier vazio. Não existe forma de "listar tudo" só com essa API.

O cadastro completo de linhas existe, mas em outra fonte: o **GTFS estático**
da SPTrans (arquivo `.zip` com `routes.txt`, `stops.txt`, etc.), baixado
separadamente (com login próprio, diferente do token da API). A aba
**📚 Todas as Linhas (GTFS)** lê esse arquivo — via upload manual na tela, ou
automaticamente se você salvar o `.zip` em `gtfs/gtfs.zip` no repositório.

Veja o passo a passo de como obter o arquivo diretamente na aba do app
(expander "ℹ️ Como obter o arquivo GTFS").


---

## 🏗️ Arquitetura do projeto

```
┌─────────────────┐      HTTP + cookie de sessão      ┌──────────────────────┐
│   app.py         │ ────────────────────────────────► │  API Olho Vivo       │
│  (Streamlit UI)  │ ◄──────────────────────────────── │  (SPTrans)           │
└────────┬─────────┘         JSON                      └──────────────────────┘
         │
         │ usa
         ▼
┌──────────────────────┐
│  sptrans_client.py    │  Encapsula autenticação, sessão HTTP e
│  (SPTransClient)      │  todos os métodos da API (um por endpoint)
└──────────────────────┘
```

- **`sptrans_client.py`**: camada de acesso à API. Não depende do Streamlit — poderia ser reutilizada em outro contexto (script, notebook, outro framework).
- **`app.py`**: camada de apresentação. Cuida da UI, dos filtros e da exibição dos dados, delegando toda chamada de rede ao cliente.

---

## ✅ Pré-requisitos

- Python 3.9+
- Um **token de acesso** válido da API Olho Vivo (veja a próxima seção)
- (Opcional, para deploy) Conta no [Streamlit Community Cloud](https://streamlit.io/cloud)

### Como obter o token

1. Acesse https://www.sptrans.com.br/desenvolvedores/
2. Crie uma conta / faça login em "Meus Aplicativos"
3. Gere um token de acesso — ele será usado no `POST /Login/Autenticar`

> ⚠️ Trate o token como uma senha. Nunca o cole em código-fonte, prints públicos ou mensagens de chat/e-mail. Veja a seção [Segurança](#-segurança-e-boas-práticas).

---

## 🔑 Configuração do token da API

O app **não tem campo para digitar o token na tela** — ele é lido automaticamente de uma destas fontes, nesta ordem de prioridade:

1. **`st.secrets["SPTRANS_TOKEN"]`** — usado no Streamlit Community Cloud
2. **Variável de ambiente `SPTRANS_TOKEN`** — usado ao rodar localmente via arquivo `.env`

### Localmente (arquivo `.env`)

Crie um arquivo `.env` na raiz do projeto (já ignorado pelo `.gitignore`):

```
SPTRANS_TOKEN=seu_token_aqui
```

### No Streamlit Community Cloud (Secrets)

1. No painel do seu app, clique em **⋮ → Settings → Secrets**
2. Cole:
   ```toml
   SPTRANS_TOKEN = "seu_token_aqui"
   ```
3. Clique em **Save changes** — o app reinicia automaticamente com o novo valor

---

## 💻 Rodando localmente

```bash
# 1. Clone o repositório
git clone <url-do-seu-repositorio>
cd sptrans-dashboard

# 2. (Recomendado) crie um ambiente virtual
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o token
cp .env.example .env
# edite o .env e cole seu token

# 5. Rode o app
streamlit run app.py
```

O app abre automaticamente em `http://localhost:8501`.

---

## ☁️ Deploy no Streamlit Community Cloud

1. Suba o repositório para o GitHub (o `.env` **não** deve ser commitado — confira o `.gitignore`)
2. Em https://share.streamlit.io, clique em **Create app** e aponte para o repositório, branch e `app.py`
3. Configure o secret `SPTRANS_TOKEN` conforme a seção [acima](#no-streamlit-community-cloud-secrets)
4. Deploy 🎉

---

## 📁 Estrutura dos arquivos

```
sptrans-dashboard/
├── app.py                 # Dashboard Streamlit (UI, abas, filtros)
├── sptrans_client.py       # Cliente da API Olho Vivo (autenticação + endpoints)
├── requirements.txt        # Dependências Python
├── .env.example            # Modelo do arquivo de variáveis de ambiente
├── .gitignore               # Ignora .env, __pycache__, secrets.toml
└── README.md                # Este arquivo
```

### `sptrans_client.py` — métodos disponíveis

| Método | Endpoint da API | Descrição |
|---|---|---|
| `autenticar()` | `POST /Login/Autenticar` | Autentica e mantém o cookie de sessão |
| `buscar_linhas(termo)` | `GET /Linha/Buscar` | Busca linhas por número/nome |
| `buscar_linha_sentido(termo, sentido)` | `GET /Linha/BuscarLinhaSentido` | Busca linha filtrando por sentido |
| `buscar_paradas(termo)` | `GET /Parada/Buscar` | Busca paradas por nome/endereço |
| `buscar_paradas_por_linha(cod_linha)` | `GET /Parada/BuscarParadasPorLinha` | Paradas atendidas por uma linha |
| `buscar_paradas_por_corredor(cod_corredor)` | `GET /Parada/BuscarParadasPorCorredor` | Paradas de um corredor |
| `listar_corredores()` | `GET /Corredor` | Lista todos os corredores |
| `listar_empresas()` | `GET /Empresa` | Lista empresas operadoras por área |
| `posicao_todos()` | `GET /Posicao` | Posição de todos os veículos em operação |
| `posicao_por_linha(cod_linha)` | `GET /Posicao/Linha` | Posição dos veículos de uma linha |
| `posicao_por_garagem(cod_empresa, cod_linha?)` | `GET /Posicao/Garagem` | Veículos de uma empresa/garagem |
| `previsao_parada_linha(cod_parada, cod_linha)` | `GET /Previsao` | Previsão de chegada (parada + linha) |
| `previsao_por_linha(cod_linha)` | `GET /Previsao/Linha` | Previsão em todas as paradas de uma linha |
| `previsao_por_parada(cod_parada)` | `GET /Previsao/Parada` | Previsão de todas as linhas em uma parada |

---

## 🔐 Detalhes técnicos da autenticação

A API Olho Vivo usa **autenticação por cookie de sessão**, não por header/token Bearer:

1. Faz-se um `POST /Login/Autenticar?token={token}`
2. Se o token for válido, a API responde `true` e define um **cookie de sessão**
3. Esse cookie precisa ser reenviado em todas as chamadas seguintes

O `sptrans_client.py` resolve isso usando `requests.Session()`, que persiste cookies automaticamente entre chamadas. Além disso:

- Se uma chamada retornar `401`, o cliente **descarta a sessão antiga, cria uma nova e reautentica** automaticamente antes de tentar de novo (uma única vez)
- Erros de autenticação (`SPTransAuthError`) e erros de chamada à API (`SPTransAPIError`) são exceções customizadas com mensagens detalhadas — status HTTP e corpo da resposta — em vez do erro genérico do `requests`

---

## 🛠️ Solução de problemas

**Autenticação falha / erro 401 mesmo com token correto**
A API Olho Vivo por vezes bloqueia por firewall IPs de provedores de nuvem/datacenter (comum em ambientes como Streamlit Community Cloud). Se o erro persistir mesmo com um token válido testado localmente, considere:
- Rodar o app localmente
- Hospedar em um VPS com IP dedicado/residencial

**A API retorna dados em formato inesperado**
Alguns endpoints (como `/Empresa`) já têm tratamento defensivo no código: se a estrutura vier diferente do esperado, o app mostra um aviso e um expander "Ver resposta bruta da API (debug)" com o JSON cru, em vez de quebrar.

**Token exposto acidentalmente**
Se você compartilhou seu token em algum lugar público (chat, print, repositório), gere um novo imediatamente em "Meus Aplicativos" no site da SPTrans e atualize o secret/`.env`.

**Deploy no Streamlit Cloud não reflete as últimas alterações**
Force um reinício em **Manage app → ⋮ → Reboot app** para garantir que o container releia o repositório e os secrets mais recentes.

---

## 🔒 Segurança e boas práticas

- O token **nunca** é hardcoded no código-fonte
- O token **nunca** aparece em campos de texto na interface (não há input manual)
- `.env` e `secrets.toml` estão no `.gitignore` — nunca devem ser commitados
- Se o token for exposto (mesmo acidentalmente), gere um novo imediatamente

---

## 📚 Referências

- [Documentação oficial da API Olho Vivo](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api/)
- [Documentação do Streamlit](https://docs.streamlit.io)
- [Gerenciamento de Secrets no Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

---

## 📝 Licença

Projeto de uso livre para fins de estudo e demonstração. Os dados são fornecidos pela SPTrans através da API pública Olho Vivo — consulte os termos de uso oficiais da SPTrans para aplicações em produção.
