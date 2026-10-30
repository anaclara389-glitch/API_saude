import colorsys
import re

import altair as alt
import pandas as pd
import requests
import streamlit as st

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
BASE_URL = "https://apidadosabertos.saude.gov.br"

CATALOGO = {
    "Doenças transmitidas por mosquitos (arboviroses)": {
        "Zika vírus": {"caminho": "arboviroses/zikavirus", "params": {}},
        "Dengue": {"caminho": "arboviroses/dengue", "params": {}},
    },
    "Estrutura de atendimento à saúde": {
        "Hospitais e leitos": {"caminho": "assistencia-a-saude/hospitais-e-leitos", "params": {}},
        # Atenção: neste endereço da API é "unidade-basicas" (sem o "s" em "unidade")
        "Unidades Básicas de Saúde": {
            "caminho": "assistencia-a-saude/unidade-basicas-de-saude", "params": {}},
    },
}

# A API aceita no máximo 20 registros por requisição
LIMITE_MAXIMO_API = 20

DESCRICAO_DATASET = {
    "Zika vírus": "Casos de Zika notificados ao Ministério da Saúde. Cada linha é uma notificação.",
    "Dengue": "Casos de dengue notificados ao Ministério da Saúde. Cada linha é uma notificação.",
    "Hospitais e leitos": "Hospitais cadastrados no CNES, com a quantidade de leitos totais e do SUS.",
    "Unidades Básicas de Saúde": "Unidades Básicas de Saúde (UBS) cadastradas, com endereço, horários e estrutura.",
}

# Dicionário de nomes amigáveis (chave em minúsculo = nome original na API).
# Colunas que não estiverem aqui são traduzidas automaticamente por `nome_amigavel`.
# Para ajustar um nome, é só editar ou acrescentar uma linha.
DICIONARIO = {
    # --- Arboviroses ---
    "nu_notificacao": "Nº da notificação",
    "dt_notificacao": "Data da notificação",
    "dt_sin_pri": "Data dos primeiros sintomas",
    "dt_sintomas": "Data dos primeiros sintomas",
    "sg_uf": "UF",
    "sg_uf_not": "UF de notificação",
    "id_municip": "Município de notificação",
    "cs_sexo": "Sexo",
    "cs_raca": "Raça/cor",
    "nu_idade_n": "Idade",
    "classi_fin": "Classificação final do caso",
    "evolucao": "Evolução do caso",
    "hospitaliz": "Foi hospitalizado?",
    "criterio": "Critério de confirmação",
    # --- Hospitais e leitos ---
    "codigo_cnes": "Código CNES",
    "nome_estabelecimento": "Nome do estabelecimento",
    "nome_razao_social": "Razão social",
    "nome_fantasia": "Nome fantasia",
    "descricao_natureza_juridica_estabelecimento": "Natureza jurídica",
    "estado_sigla": "UF",
    "codigo_uf": "Código da UF",
    "codigo_municipio": "Código do município",
    "municipio": "Município",
    "nome_municipio": "Município",
    "endereco_estabelecimento": "Endereço",
    "bairro_estabelecimento": "Bairro",
    "codigo_cep_estabelecimento": "CEP",
    "numero_telefone_estabelecimento": "Telefone",
    "endereco_email_estabelecimento": "E-mail",
    "latitude_estabelecimento_decimo_grau": "Latitude",
    "longitude_estabelecimento_decimo_grau": "Longitude",
    "descricao_turno_atendimento": "Turno de atendimento",
    "quantidade_total_leitos": "Total de leitos",
    "quantidade_total_leitos_sus": "Leitos do SUS",
    "quantidade_leitos_existentes": "Leitos existentes",
    "quantidade_leitos_sus": "Leitos do SUS",
    # --- Unidades Básicas de Saúde ---
    "cod_cnes": "Código CNES",
    "nom_estab": "Nome da unidade",
    "dsc_endereco": "Endereço",
    "dsc_bairro": "Bairro",
    "dsc_cidade": "Cidade",
    "dsc_telefone": "Telefone",
    "dsc_turno_atendimento": "Turno de atendimento",
    "cod_munic": "Código do município",
    "cod_uf": "Código da UF",
    "vlr_latitude": "Latitude",
    "vlr_longitude": "Longitude",
    "dsc_estrut_fisic_ambiencia": "Estrutura física e ambiência",
    "dsc_adap_defic_fisic_idosos": "Adaptação para pessoas com deficiência e idosos",
    "dsc_equipamentos": "Equipamentos",
    "dsc_medicamentos": "Medicamentos disponíveis",
}

# Prefixos comuns nos nomes da API e o que significam
PREFIXOS = {
    "dt": "Data de", "co": "Código", "cod": "Código", "codigo": "Código",
    "nu": "Nº", "nr": "Nº", "qt": "Quantidade de", "qtd": "Quantidade de",
    "no": "Nome", "nom": "Nome", "sg": "Sigla", "ds": "", "dsc": "",
    "vlr": "", "cs": "", "id": "",
}
SIGLAS = {"uf": "UF", "cnes": "CNES", "sus": "SUS", "cep": "CEP", "cpf": "CPF",
          "cnpj": "CNPJ", "ubs": "UBS", "id": "ID"}
EXPANSOES = {"munic": "município", "municip": "município", "estab": "estabelecimento",
             "endereco": "endereço", "codigo": "código", "descricao": "descrição",
             "natureza": "natureza", "juridica": "jurídica", "numero": "número",
             "quantidade": "quantidade", "medico": "médico", "saude": "saúde"}


def nome_amigavel(coluna: str) -> str:
    """Converte o nome técnico de uma coluna em um nome legível."""
    chave = coluna.lower()
    if chave in DICIONARIO:
        return DICIONARIO[chave]

    partes = [p for p in re.split(r"[_\.\s]+", chave) if p]
    if not partes:
        return coluna

    prefixo = ""
    if len(partes) > 1 and partes[0] in PREFIXOS:
        prefixo = PREFIXOS[partes[0]]
        partes = partes[1:]

    palavras = []
    for p in partes:
        if p in SIGLAS:
            palavras.append(SIGLAS[p])
        else:
            palavras.append(EXPANSOES.get(p, p))

    texto = " ".join(([prefixo] if prefixo else []) + palavras).strip()
    return texto[:1].upper() + texto[1:]


TIPOS_AMIGAVEIS = {"object": "Texto", "int64": "Número", "float64": "Número decimal",
                   "bool": "Sim/Não", "datetime64[ns]": "Data"}


# ----------------------------------------------------------------------------
# Tradução de códigos em textos (ex.: 1 -> Sim, 2 -> Não)
# Chave = nome original da coluna na API, em minúsculo.
# Para traduzir mais uma coluna, basta acrescentar uma linha em VALORES.
# ----------------------------------------------------------------------------
SIM_NAO = {"1": "Sim", "2": "Não", "9": "Ignorado"}
EXAME = {"1": "Positivo", "2": "Negativo", "3": "Inconclusivo", "4": "Não realizado"}

VALORES = {
    "cs_sexo": {"M": "Masculino", "F": "Feminino", "I": "Ignorado"},
    "cs_raca": {"1": "Branca", "2": "Preta", "3": "Amarela", "4": "Parda",
                "5": "Indígena", "9": "Ignorado"},
    "cs_gestant": {"1": "1º trimestre", "2": "2º trimestre", "3": "3º trimestre",
                   "4": "Idade gestacional ignorada", "5": "Não", "6": "Não se aplica",
                   "9": "Ignorado"},
    "cs_escol_n": {"0": "Analfabeto", "1": "1ª a 4ª série incompleta",
                   "2": "4ª série completa", "3": "5ª a 8ª série incompleta",
                   "4": "Ensino fundamental completo", "5": "Ensino médio incompleto",
                   "6": "Ensino médio completo", "7": "Superior incompleto",
                   "8": "Superior completo", "9": "Ignorado", "10": "Não se aplica"},
    "cs_zona": {"1": "Urbana", "2": "Rural", "3": "Periurbana", "9": "Ignorado"},
    "evolucao": {"1": "Cura", "2": "Óbito pelo agravo", "3": "Óbito por outras causas",
                 "4": "Óbito em investigação", "9": "Ignorado"},
    "criterio": {"1": "Laboratório", "2": "Clínico-epidemiológico", "3": "Em investigação"},
    "tpautocto": {"1": "Sim", "2": "Não", "3": "Indeterminado"},
    "resul_ns1": EXAME, "resul_vi_n": EXAME, "resul_pcr_": EXAME, "resul_pcr": EXAME,
}
# Campos de resposta Sim / Não / Ignorado
for _c in ["hospitaliz", "doenca_tra", "febre", "mialgia", "cefaleia", "exantema",
           "vomito", "nausea", "dor_costas", "conjuntvit", "artrite", "artralgia",
           "petequia_n", "leucopenia", "laco", "dor_retro", "diabetes", "hematolog",
           "hepatopat", "renal", "hipertensao", "acido_pept", "auto_imune"]:
    VALORES[_c] = SIM_NAO

# Códigos que mudam de significado conforme a doença
VALORES_POR_DATASET = {
    "Dengue": {
        "classi_fin": {"5": "Descartado", "8": "Inconclusivo", "10": "Dengue",
                       "11": "Dengue com sinais de alarme", "12": "Dengue grave"},
    },
}

DICIONARIO.update({
    "doenca_tra": "Doença relacionada ao trabalho?",
    "cs_gestant": "Gestante",
    "cs_escol_n": "Escolaridade",
    "cs_zona": "Zona de residência",
    "tpautocto": "Caso autóctone (contraído na cidade)?",
    "nu_idade_n": "Código da idade (original)",
    "idade_anos": "Idade (anos)",
    "faixa_etaria": "Faixa etária",
    "sem_not": "Semana epidemiológica da notificação",
    "sem_pri": "Semana epidemiológica dos sintomas",
    "nu_ano": "Ano",
    "febre": "Febre", "mialgia": "Dor muscular", "cefaleia": "Dor de cabeça",
    "exantema": "Manchas na pele", "vomito": "Vômito", "nausea": "Náusea",
    "dor_costas": "Dor nas costas", "conjuntvit": "Conjuntivite", "artrite": "Artrite",
    "artralgia": "Dor nas articulações", "petequia_n": "Petéquias",
    "leucopenia": "Leucopenia", "laco": "Prova do laço", "dor_retro": "Dor atrás dos olhos",
    "diabetes": "Diabetes", "hematolog": "Doença hematológica", "hepatopat": "Hepatopatia",
    "renal": "Doença renal", "hipertensao": "Hipertensão",
    "acido_pept": "Doença ácido-péptica", "auto_imune": "Doença autoimune",
    "resul_ns1": "Resultado do exame NS1", "resul_vi_n": "Resultado do isolamento viral",
    "resul_pcr_": "Resultado do PCR", "resul_pcr": "Resultado do PCR",
})


def normalizar_codigo(v):
    """Padroniza valores: vazios viram None e '1.0' vira '1'."""
    if isinstance(v, (list, dict)):
        return str(v)
    if v is None or pd.isna(v):
        return None
    s = str(v).strip()
    if s.lower() in ("", "nan", "none", "null", "nat"):
        return None
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except ValueError:
        pass
    return s


def decodificar_valores(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Troca códigos (1, 2, 9...) pelos textos correspondentes (Sim, Não, Ignorado...)."""
    for col in df.columns:
        tabela = VALORES_POR_DATASET.get(dataset, {}).get(col.lower()) or VALORES.get(col.lower())
        if not tabela and col.lower().startswith(("estabelecimento_possui_", "estabelecimento_faz_")):
            tabela = {"0": "Não", "1": "Sim"}
        if not tabela:
            continue

        def traduzir(v, tabela=tabela):
            codigo = normalizar_codigo(v)
            return "Não informado" if codigo is None else tabela.get(codigo, codigo)

        df[col] = df[col].map(traduzir)
    return df


def adicionar_idade(df: pd.DataFrame) -> pd.DataFrame:
    """A idade vem codificada (ex.: 4025 = 25 anos). Cria colunas legíveis."""
    col = next((c for c in df.columns if c.lower() == "nu_idade_n"), None)
    if not col:
        return df

    def anos(v):
        c = normalizar_codigo(v)
        if c is None or not c.isdigit():
            return None
        n = int(c)
        fator = {4: 1, 3: 1 / 12, 2: 1 / 365, 1: 1 / 8760}.get(n // 1000)
        return None if fator is None else round((n % 1000) * fator, 1)

    df["idade_anos"] = pd.to_numeric(df[col].map(anos), errors="coerce")
    df["faixa_etaria"] = (
        pd.cut(df["idade_anos"], bins=[-0.1, 4, 14, 24, 39, 59, 200],
               labels=["0 a 4 anos", "5 a 14 anos", "15 a 24 anos",
                       "25 a 39 anos", "40 a 59 anos", "60 anos ou mais"])
        .astype(object).fillna("Não informado")
    )
    return df


st.set_page_config(page_title="Painel de Saúde", page_icon="🩺", layout="wide")


# ----------------------------------------------------------------------------
# Funções de acesso e tratamento dos dados
# ----------------------------------------------------------------------------
def extrair_registros(payload):
    """A API pode devolver uma lista direta ou um dict com uma lista dentro."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for valor in payload.values():
            if isinstance(valor, list) and valor and isinstance(valor[0], dict):
                return valor
        return [payload]
    return []


@st.cache_data(ttl=3600, show_spinner=False)
def consultar_api(caminho: str, params_fixos: tuple, paginas: int, limite: int):
    """Consulta a API paginando com limit/offset. Retorna (DataFrame, url, erro)."""
    url = f"{BASE_URL}/{caminho}"
    registros = []
    limite = min(limite, LIMITE_MAXIMO_API)

    try:
        for pagina in range(paginas):
            params = dict(params_fixos)
            params.update({"limit": limite, "offset": pagina * limite})
            resposta = requests.get(url, params=params, timeout=30)
            if resposta.status_code != 200:
                if pagina == 0:
                    msgs = {
                        400: "A API recusou os parâmetros da consulta (código 400).",
                        401: "Este conjunto de dados exige autenticação (código 401).",
                        403: "Acesso negado a este conjunto de dados (código 403).",
                        404: "Endereço não encontrado na API (código 404). Ele pode ter mudado.",
                    }
                    return pd.DataFrame(), url, msgs.get(
                        resposta.status_code, f"A consulta falhou (código {resposta.status_code}).")
                break

            lote = extrair_registros(resposta.json())
            if not lote:
                break
            registros.extend(lote)
            if len(lote) < limite:
                break
    except requests.RequestException as e:
        return pd.DataFrame(), url, f"Erro de conexão: {e}"

    return pd.json_normalize(registros), url, None


def tratar_dataframe(df: pd.DataFrame, dataset: str = ""):
    """Converte tipos (datas, coordenadas), renomeia colunas para nomes
    amigáveis e devolve também o mapa nome-original -> nome-amigável."""
    df = df.copy()

    for col in df.columns:
        nome = col.lower()
        if df[col].dtype == object and ("data" in nome or nome.startswith("dt_")):
            convertido = pd.to_datetime(df[col], errors="coerce")
            if convertido.notna().mean() > 0.5:
                df[col] = convertido
        elif df[col].dtype == object and ("latitude" in nome or "longitude" in nome):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = decodificar_valores(df, dataset)
    df = adicionar_idade(df)

    # Renomeia garantindo nomes únicos
    mapa, usados = {}, set()
    for col in df.columns:
        novo = nome_amigavel(col)
        if novo in usados:
            novo = f"{novo} ({col})"
        usados.add(novo)
        mapa[col] = novo

    return df.rename(columns=mapa), mapa


def colunas_por_tipo(df: pd.DataFrame):
    datas = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    numericas = [
        c for c in df.select_dtypes("number").columns
        if "latitude" not in c.lower() and "longitude" not in c.lower()
        and not c.lower().startswith("código") and not c.lower().startswith("nº")
    ]
    categoricas = [
        c for c in df.select_dtypes(exclude=["number", "datetime"]).columns
        if 2 <= df[c].nunique() <= 60 and df[c].nunique() < len(df) * 0.8
    ]
    return datas, numericas, categoricas


def achar_coluna(df, trecho):
    """Procura uma coluna pelo trecho. Trechos curtos (ex.: 'uf') exigem palavra inteira."""
    for c in df.columns:
        nome = c.lower()
        if len(trecho) <= 3:
            if trecho in re.split(r"\W+", nome):
                return c
        elif trecho in nome:
            return c
    return None


# ----------------------------------------------------------------------------
# Tema / cores do layout
# ----------------------------------------------------------------------------
PERSONALIZADA = "🎨 Personalizada..."
PALETAS = {
    "🔵 Azul": "#0068C9",
    "🟢 Verde saúde": "#1B8A5A",
    "🟣 Roxo": "#7C3AED",
    "🟠 Laranja": "#E8590C",
    "🌸 Rosa": "#D6336C",
    "🔴 Vermelho": "#FF4B4B",
}

CSS_TEMA = """
<style>
/* Fundo da barra lateral */
[data-testid="stSidebar"] { background-color: __SIDEBAR__ !important; }

/* Títulos e números em destaque */
.stApp h1, .stApp h2, .stApp h3 { color: __PRIMARY__ !important; }
[data-testid="stMetricValue"] { color: __PRIMARY__ !important; }

/* Botão principal */
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background-color: __PRIMARY__ !important;
    border-color: __PRIMARY__ !important;
    color: __TEXTO_BOTAO__ !important;
}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
    filter: brightness(0.9);
}
button[kind="primary"] p, button[data-testid="stBaseButton-primary"] p {
    color: __TEXTO_BOTAO__ !important;
}

/* Abas */
button[data-baseweb="tab"][aria-selected="true"],
button[data-baseweb="tab"][aria-selected="true"] p { color: __PRIMARY__ !important; }
div[data-baseweb="tab-highlight"] { background-color: __PRIMARY__ !important; }

/* Campos selecionados (foco) e etiquetas do filtro */
div[data-baseweb="select"]:focus-within > div,
div[data-baseweb="input"]:focus-within { border-color: __PRIMARY__ !important; }
span[data-baseweb="tag"] { background-color: __PRIMARY__ !important; }
span[data-baseweb="tag"], span[data-baseweb="tag"] span { color: __TEXTO_BOTAO__ !important; }

/* Sliders e botões de rádio: giram o tom vermelho padrão para a cor escolhida */
[data-testid="stSlider"], [data-testid="stSelectSlider"],
[data-testid="stRadio"] { filter: __FILTRO__; }
</style>
"""


def _rgb(cor_hex: str):
    h = cor_hex.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def clarear(cor_hex: str, fator: float) -> str:
    """Mistura a cor com branco (fator 0 = cor original, 1 = branco)."""
    r, g, b = _rgb(cor_hex)
    return "#%02X%02X%02X" % tuple(round(c + (255 - c) * fator) for c in (r, g, b))


def cor_do_texto(cor_hex: str) -> str:
    """Branco em fundos escuros, cinza-escuro em fundos claros."""
    r, g, b = _rgb(cor_hex)
    return "#FFFFFF" if (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.6 else "#1F2937"


def aplicar_tema(cor: str):
    r, g, b = _rgb(cor)
    h, _, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    filtro = f"hue-rotate({round(h * 360)}deg) saturate({max(sat, 0.15):.2f})"
    css = (
        CSS_TEMA.replace("__PRIMARY__", cor)
        .replace("__SIDEBAR__", clarear(cor, 0.9))
        .replace("__TEXTO_BOTAO__", cor_do_texto(cor))
        .replace("__FILTRO__", filtro)
    )
    st.markdown(css, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Barra lateral
# ----------------------------------------------------------------------------
st.title("🩺 Painel de Saúde — Dados Abertos")
st.caption("Fonte: API de Dados Abertos do Ministério da Saúde (apidadosabertos.saude.gov.br)")

with st.sidebar:
    st.header("1. O que você quer consultar?")
    grupo = st.selectbox("Assunto", list(CATALOGO.keys()))
    datasets = CATALOGO[grupo]
    sub_nome = st.selectbox("Conjunto de dados", list(datasets.keys()))
    st.caption(DESCRICAO_DATASET.get(sub_nome, ""))

    st.header("2. Quantos dados buscar?")
    limite = st.select_slider(
        "Registros por requisição", options=[5, 10, 20], value=20,
        help="A API entrega os dados em blocos (páginas). Este é o tamanho de cada bloco.",
    )
    paginas = st.slider(
        "Quantidade de requisições", 1, 50, 5,
        help="Quantas vezes o app vai pedir um novo bloco de dados à API.",
    )
    st.caption(f"Serão buscados no máximo **{limite * paginas}** registros.")

    buscar = st.button("🔍 Buscar dados", type="primary", use_container_width=True)

    st.divider()
    with st.expander("🎨 Aparência"):
        paleta = st.selectbox("Cor do layout", list(PALETAS.keys()) + [PERSONALIZADA], key="paleta")
        if paleta == PERSONALIZADA:
            COR = st.color_picker("Escolha a cor", "#0068C9", key="cor_personalizada")
        else:
            COR = PALETAS[paleta]
        st.caption("Para modo escuro, use o menu ⋮ (canto superior direito) → Settings → Theme.")

    aplicar_tema(COR)

if buscar:
    with st.spinner("Consultando a API..."):
        escolhido = datasets[sub_nome]
        df_raw, url, erro = consultar_api(
            escolhido["caminho"], tuple(escolhido["params"].items()), paginas, limite
        )
    st.session_state["resultado"] = (df_raw, url, erro, sub_nome)

if "resultado" not in st.session_state:
    st.info("👈 Escolha o assunto na barra lateral e clique em **Buscar dados**.")
    st.stop()

df_raw, url, erro, nome_dataset = st.session_state["resultado"]

if erro:
    st.error(erro)
    st.stop()
if df_raw.empty:
    st.warning("A consulta não retornou registros.")
    st.stop()

df, mapa_colunas = tratar_dataframe(df_raw, nome_dataset)
datas, numericas, categoricas = colunas_por_tipo(df)

st.subheader(f"📌 {nome_dataset}")
st.caption(DESCRICAO_DATASET.get(nome_dataset, ""))

# ----------------------------------------------------------------------------
# Filtro
# ----------------------------------------------------------------------------
with st.expander("🔎 Filtrar os dados (opcional)"):
    if categoricas:
        col_filtro = st.selectbox("Filtrar por", ["(sem filtro)"] + categoricas)
        if col_filtro != "(sem filtro)":
            opcoes = sorted(df[col_filtro].dropna().astype(str).unique())
            selecionados = st.multiselect("Manter apenas estes valores", opcoes, default=opcoes)
            df = df[df[col_filtro].astype(str).isin(selecionados)]
    else:
        st.write("Não há colunas adequadas para filtro neste conjunto de dados.")

if df.empty:
    st.warning("Nenhum registro restou após o filtro.")
    st.stop()

# ----------------------------------------------------------------------------
# Indicadores principais
# ----------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total de registros", f"{len(df):,}".replace(",", "."),
          help="Quantidade de linhas retornadas pela API (após o filtro).")
c2.metric("Informações por registro", df.shape[1],
          help="Número de colunas (campos) disponíveis em cada registro.")
c3.metric("Campos sem preenchimento", f"{df.isna().mean().mean() * 100:.1f}%",
          help="Percentual de células vazias em toda a tabela.")

col_uf = achar_coluna(df, "uf")
if col_uf:
    c4.metric("Estados presentes", df[col_uf].nunique(), help=f"Valores distintos de “{col_uf}”.")
elif datas:
    c4.metric("Período dos dados",
              f"{df[datas[0]].min():%d/%m/%Y} a {df[datas[0]].max():%d/%m/%Y}")
else:
    c4.metric("Colunas numéricas", len(numericas))

cols_leitos = [c for c in numericas if "leito" in c.lower()]
if cols_leitos:
    st.markdown("**Total de leitos nos registros**")
    cols = st.columns(min(len(cols_leitos), 4))
    for i, c in enumerate(cols_leitos[:4]):
        cols[i].metric(c, f"{int(df[c].sum()):,}".replace(",", "."))

st.divider()

# ----------------------------------------------------------------------------
# Abas
# ----------------------------------------------------------------------------
abas = st.tabs([
    "📊 Resumo por categoria",
    "📈 Evolução ao longo do tempo",
    "🗺️ Localização no mapa",
    "🧹 Qualidade dos dados",
    "📄 Tabela completa",
])

# --- Resumo por categoria
with abas[0]:
    st.caption("Mostra quantos registros existem para cada valor de uma coluna "
               "(por exemplo, quantos por UF ou por sexo).")
    if categoricas:
        col_a, col_b = st.columns([1, 3])
        with col_a:
            col_cat = st.selectbox("Agrupar por", categoricas, key="cat")
            top_n = st.slider("Quantos itens mostrar", 3, 30, 10)
        contagem = (
            df[col_cat].map(normalizar_codigo).fillna("Não informado")
            .astype(str).value_counts().head(top_n)
        )
        dados = contagem.rename_axis("Categoria").reset_index(name="Quantidade")
        dados["%"] = (dados["Quantidade"] / len(df) * 100).round(1)
        with col_b:
            grafico = (
                alt.Chart(dados)
                .mark_bar(color=COR)
                .encode(
                    x=alt.X("Quantidade:Q", title="Quantidade de registros"),
                    y=alt.Y("Categoria:N", sort="-x", title=None,
                            axis=alt.Axis(labelLimit=300)),
                    tooltip=["Categoria", "Quantidade", "%"],
                )
            )
            st.altair_chart(grafico, use_container_width=True)
    else:
        st.info("Não há colunas de categoria adequadas para este gráfico.")

    if numericas:
        st.markdown("**Resumo estatístico dos campos numéricos**")
        resumo = df[numericas].describe().T.rename(columns={
            "count": "Preenchidos", "mean": "Média", "std": "Desvio padrão",
            "min": "Mínimo", "25%": "25% dos casos até", "50%": "Mediana",
            "75%": "75% dos casos até", "max": "Máximo",
        })
        st.dataframe(resumo, use_container_width=True)

# --- Evolução
with abas[1]:
    st.caption("Mostra quantos registros aparecem em cada período de tempo.")
    if datas:
        col_data = st.selectbox("Data a considerar", datas)
        freq = st.radio("Agrupar por", ["Dia", "Semana", "Mês"], index=2, horizontal=True)
        regra = {"Dia": "D", "Semana": "W", "Mês": "MS"}[freq]
        serie = df.set_index(col_data).sort_index().resample(regra).size()
        st.line_chart(serie.rename("Quantidade de registros"), color=COR)
    else:
        st.info("Este conjunto de dados não possui uma coluna de data.")

# --- Mapa
with abas[2]:
    st.caption("Cada ponto é um estabelecimento com coordenadas válidas.")
    col_lat = achar_coluna(df, "latitude") or achar_coluna(df, "lat")
    col_lon = achar_coluna(df, "longitude") or achar_coluna(df, "lon")
    if col_lat and col_lon:
        mapa = (
            df[[col_lat, col_lon]]
            .rename(columns={col_lat: "latitude", col_lon: "longitude"})
            .apply(pd.to_numeric, errors="coerce")
            .dropna()
        )
        mapa = mapa[mapa["latitude"].between(-35, 6) & mapa["longitude"].between(-75, -30)]
        if not mapa.empty:
            try:
                st.map(mapa, color=COR)
            except TypeError:  # versões antigas do Streamlit
                st.map(mapa)
            st.caption(f"{len(mapa)} pontos exibidos.")
        else:
            st.info("As coordenadas estão ausentes ou fora do Brasil.")
    else:
        st.info("Este conjunto de dados não possui latitude e longitude.")

# --- Qualidade
with abas[3]:
    st.caption("Ajuda a entender se os dados estão completos e como cada campo é identificado na API.")
    qualidade = pd.DataFrame({
        "Nome original na API": [next((o for o, n in mapa_colunas.items() if n == c), c) for c in df.columns],
        "Tipo de dado": [TIPOS_AMIGAVEIS.get(str(t), str(t)) for t in df.dtypes],
        "Preenchidos": df.notna().sum().values,
        "Vazios": df.isna().sum().values,
        "% vazio": (df.isna().mean() * 100).round(1).values,
        "Valores diferentes": df.nunique().values,
    }, index=pd.Index(df.columns, name="Campo")).sort_values("% vazio", ascending=False)
    st.dataframe(qualidade, use_container_width=True)
    st.caption(f"Registros repetidos: {int(df.duplicated().sum())}")

# --- Tabela
with abas[4]:
    st.dataframe(df, use_container_width=True, height=400)
    st.download_button(
        "⬇️ Baixar tabela em CSV",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{nome_dataset.lower().split(' (')[0].replace(' ', '_')}.csv",
        mime="text/csv",
    )