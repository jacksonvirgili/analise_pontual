import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Configuração opcional da página para usar o espaço todo
st.set_page_config(page_title="Dashboard Faturamento", layout="wide")

# 1. FUNÇÃO DE PROCESSAMENTO COM CACHE (Evita lentidão)
@st.cache_data
def carregar_e_processar_dados():
    # Lê o arquivo Excel direto da pasta
    df = pd.read_excel('Base Histórico Masculino.xlsx')

    # Função de quintil
    def classificar_quintil(x):
        return pd.qcut(x.rank(method='first'), q=5, labels=['p1', 'p2', 'p3', 'p4', 'p5'])

    # Criando a nova coluna de preço
    df['Classificação Preço'] = df.groupby(['Material - Subgrupo', 'Mês/Ano Comercial'])['Preço Material'].transform(classificar_quintil)

    # Agrupamento base usando 'Venda Valor'
    df_resumo = df.groupby(['Mês/Ano Comercial', 'Material - Subgrupo', 'Classificação Preço', 'Próprio x Terceiro']).agg(
        Venda_Valor=('Venda Valor', 'sum'),
        Venda_Pecas=('Venda Peças', 'sum'),
        Venda_Lucro_Bruto=('Venda Lucro Bruto', 'sum'),
        Estoque_Custo_Mes=('Estoque Custo Mês', 'sum'),
        Estoque_Pecas_Mes=('Estoque Peças Mês', 'sum'),
        Contagem_Material_Pai=('Material Pai - Código', 'nunique')
    ).reset_index()

    # Cálculo dos indicadores
    df_resumo['Média_Estoque_Custo'] = df_resumo['Estoque_Custo_Mes']
    df_resumo['Média_Estoque_Pecas'] = df_resumo['Estoque_Pecas_Mes']

    df_resumo['GMROI'] = np.where(df_resumo['Média_Estoque_Custo'] == 0, 0, df_resumo['Venda_Lucro_Bruto'] / df_resumo['Média_Estoque_Custo'])
    df_resumo['Margem'] = np.where(df_resumo['Venda_Valor'] == 0, 0, df_resumo['Venda_Lucro_Bruto'] / df_resumo['Venda_Valor'])
    df_resumo['Giro'] = np.where(df_resumo['Média_Estoque_Pecas'] == 0, 0, df_resumo['Venda_Pecas'] / df_resumo['Média_Estoque_Pecas'])
    
    total_pecas_st = df_resumo['Venda_Pecas'] + df_resumo['Estoque_Pecas_Mes']
    df_resumo['ST%'] = np.where(total_pecas_st == 0, 0, df_resumo['Venda_Pecas'] / total_pecas_st)

    return df_resumo

# Carrega os dados processados
df_resumo = carregar_e_processar_dados()


# 2. CONSTRUÇÃO DA INTERFACE (WIDGETS)
st.title("📊 Dashboard de Faturamento")

# Menu Lateral (Filtros)
st.sidebar.header("Opções do Gráfico")

# Adicionando a opção "Todos/Todas" no início das listas
lista_subgrupos = ['Todos'] + sorted(df_resumo['Material - Subgrupo'].dropna().unique().tolist())
lista_classificacoes = ['Todas', 'p1', 'p2', 'p3', 'p4', 'p5']

subgrupo = st.sidebar.selectbox("Selecione o Subgrupo:", options=lista_subgrupos)
classificacao = st.sidebar.selectbox("Selecione a Classificação (Preço):", options=lista_classificacoes)


# 3. LÓGICA DO GRÁFICO
# --- FILTRO ---
df_f = df_resumo.copy()

# Aplica o filtro de Subgrupo apenas se não for "Todos"
if subgrupo != 'Todos':
    df_f = df_f[df_f['Material - Subgrupo'] == subgrupo]

# Aplica o filtro de Classificação apenas se não for "Todas"
if classificacao != 'Todas':
    df_f = df_f[df_f['Classificação Preço'] == classificacao]


# --- VERIFICAÇÃO DE DADOS ---
if df_f.empty:
    # Mostra um aviso bonito na tela do Streamlit se o filtro ficar vazio
    st.warning(f"Não houve vendas para a combinação de Subgrupo: '{subgrupo}' e Classificação: '{classificacao}'.")
else:
    # --- AGRUPAMENTOS ---
    df_total = df_f.groupby('Mês/Ano Comercial', as_index=False)['Venda_Valor'].sum()
    df_bars = df_f.groupby(['Mês/Ano Comercial', 'Próprio x Terceiro'], as_index=False)['Venda_Valor'].sum()
    
    df_prop = df_bars[df_bars['Próprio x Terceiro'] == 'Própria']
    df_terc = df_bars[df_bars['Próprio x Terceiro'] == 'Terceiro']

    # --- CRIAÇÃO DO GRÁFICO (PLOTLY) ---
    fig = go.Figure()

    # Adiciona as barras
    fig.add_trace(go.Bar(
        x=df_prop['Mês/Ano Comercial'], 
        y=df_prop['Venda_Valor'], 
        name='Própria', 
        marker_color='#3780bf',
        hovertemplate='Própria: R$ %{y:,.2f}'
    ))
    
    fig.add_trace(go.Bar(
        x=df_terc['Mês/Ano Comercial'], 
        y=df_terc['Venda_Valor'], 
        name='Terceiro', 
        marker_color='#ff9933',
        hovertemplate='Terceiro: R$ %{y:,.2f}'
    ))
    
    # Adiciona a linha do total
    fig.add_trace(go.Scatter(
        x=df_total['Mês/Ano Comercial'], 
        y=df_total['Venda_Valor'], 
        name='Total (R$)', 
        mode='lines+markers', 
        line=dict(color='#2ca02c', width=4),
        marker=dict(size=8),
        hovertemplate='Total: R$ %{y:,.2f}'
    ))

    # Layout básico
    fig.update_layout(
        title=f"Faturamento | Subgrupo: {subgrupo} - Classificação: {classificacao.upper()}",
        barmode='group', # Barras lado a lado
        hovermode="x unified",
        template='plotly_white',
        yaxis=dict(
            title="Faturamento em R$",
            tickprefix="R$ ",
            separatethousands=True,
            rangemode="tozero"
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # 4. RENDERIZA NO STREAMLIT
    st.plotly_chart(fig, use_container_width=True)
