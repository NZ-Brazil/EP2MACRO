# coding: utf8

"""
formato:
saídas do EP:
arquivos por energético, um por cenário. O sufixo do cenário (ex.: _S0) é
livre e varia a cada rodada; a identificação do energético é feita pelo início
do nome do arquivo, não pelo sufixo. Os nomes são casados de forma tolerante:
maiúsculas/minúsculas são ignoradas e espaço equivale a underscore (ver
normalizar()), então 'steam coal 3100_S0' casa com Steam_Coal_3100,
'sugarcane bagasse_S0' com Sugarcane_Bagasse etc.
  colunas: time_index, year, AC, AL, AM, ... (uma coluna por UF)
Demand_[Energetico]_[cenario].csv (demanda por UF, em MWh; os arquivos de
                                   demanda de Liquid Fuels e Outros Combustíveis
                                   vêm com o prefixo Demand_, EXCETO NaturalGas,
                                   que mantém o nome antigo sem prefixo)
Demand_Hydrogen_mass_[cenario].csv (demanda de H2 por UF, em MASSA, não em MWh:
                                   tratada à parte, ver ETAPA 1 item (e))
electricity_[ano]_[cenario].csv  (já horário, 8760 linhas, por UF)
co2_[cenario].csv                (emissões nacionais por UF, já em tCO2e; o
                                   arquivo real vem em minúsculas)
[Energetico]_[cenario].csv       (SEM prefixo Demand_: demanda por UF, em MWh,
                                   de energéticos com fator cadastrado em
                                   FATORES_CO2_TEP, ex.: Coal, Steam_Coal_3100,
                                   Sugarcane_Bagasse, Firewood etc. Não geram
                                   coluna de demanda, só entram na conta de CO2)
EXO_DEMAND_METADATA.csv          (ignorado)
electricity_[cenario].csv         (sem ano; ignorado por enquanto)
energéticos em IGNORAR            (ex.: 'black liquor', 'charcoal mass', 'coke
                                   gas', 'firewood mass', 'tar': sem fator e sem
                                   coluna de demanda; descartados de propósito)

saídas do modelo Waste (resíduos), na pasta 'Waste output':
SAIDA_WASTE_EN-[cenario].csv   (demanda de eletricidade por ano e por UF,
                                 anos de 2020 a 2050, uma coluna por UF)
SAIDA_WASTE_GEE-[cenario].csv  (emissões de CO2 por ano e por UF, só nos
                                 anos de interesse: 2025, 2030, ..., 2050)
  o sufixo do cenário (ex.: -S0) é livre, igual ao EP; a identificação do
  arquivo é feita pelo prefixo (SAIDA_WASTE_EN / SAIDA_WASTE_GEE).

saídas do modelo transporte-agricultura, já no formato MACRO, na pasta
'Transport_Agriculture output':
demand_ano.csv
demand_LF_ano.csv
elec_demand_ano.csv
h2_demand_ano.csv
CO2e*.csv (emissões; arquivo identificado pelo prefixo "CO2e" no nome,
           casamento tolerante a maiúsculas/minúsculas e sufixo, igual ao
           usado para os demais arquivos do EP e do Waste -- transposto,
           anos nas colunas)

o que faz este tradutor:

ETAPA 1 - converte as saídas do EP para o formato MACRO
- Liquid Fuels e Outros Combustíveis: para cada energético e cada ano, soma
  as UFs (-> total nacional anual), divide por 8760 e repete o valor
  horário em 8760 linhas. Colunas de saída: Demand_[Energetico].
  NaturalGas entra em "Outros Combustíveis".
  Energéticos sem arquivo correspondente ficam com demanda zero.
  Hidrogênio NÃO entra aqui: não existe mais coluna Demand_Hydrogen.
- Electricity: renomeia time_index -> Time_Index, remove a coluna year,
  prefixa cada UF com elec_BR_.
- Hydrogen: o arquivo Demand_Hydrogen_mass_* vem em MASSA de H2. Os valores
  são convertidos para MWh pelo PCS (poder calorífico superior) do H2, e
  mantidos POR UF (sem somar os estados, igual ao Waste), divididos por 8760
  e repetidos em 8760 linhas. Gera h2_demand_[ano].csv, que na ETAPA 3 é
  somado ao h2_demand_[ano].csv do transp-agric.
- CO2: soma as UFs do(s) arquivo(s) CO2_*.csv (emissão nacional direta,
  sem fator) e soma a demanda de cada energético cadastrado em
  FATORES_CO2_TEP (ex.: Coal_*.csv, Steam_Coal_3100_*.csv,
  Sugarcane_Bagasse_*.csv etc.), cada uma convertida pelo seu próprio fator
  de emissão (tCO2e/tep -> tCO2e/MWh, ver MWH_POR_TEP). Colunas geradas:
  CO2_EP_Base e CO2_[Energetico] para cada energético de FATORES_CO2_TEP
  que tiver arquivo correspondente.
- resultado intermediário gravado em 'MACRO input/_EP_convertido' (para conferência)

ETAPA 2 - converte as saídas do Waste para o formato MACRO
- Electricity (SAIDA_WASTE_EN): para cada ano de interesse, mantém a
  demanda por UF (sem somar os estados, diferente do EP), divide por 8760
  e repete o valor horário em 8760 linhas. Colunas: elec_BR_[UF].
- CO2 (SAIDA_WASTE_GEE): soma as UFs -> total nacional por ano. Coluna
  CO2_Waste no arquivo intermediário.
- resultado intermediário gravado em 'MACRO input/_Waste_convertido' (para conferência)

ETAPA 3 - soma os resultados convertidos (EP + Waste + transp-agric)
- demandas (demand_ano, demand_LF_ano, elec_demand_ano, h2_demand_ano):
  alinhamento das linhas pelo Time_Index (não pela posição); alinhamento
  das colunas pelo nome (a ordem das colunas difere entre os modelos);
  união das colunas: coluna presente em só uma das fontes é reportada na
  tela e preenchida com zero nas demais (ver PREENCHER_FALTANTES_COM_ZERO).
  elec_demand = EP + transp-agric - Waste (o Waste é subtraído); as demais
  demandas somam EP + transp-agric (o Waste não gera essas colunas).
- CO2 (resultado em tCO2e/ano, igual ao transp-agric): soma numa única
  coluna TODAS as colunas do CO2_Emissions.csv intermediário do EP
  (CO2_EP_Base + uma coluna CO2_[Energetico] para cada energético de
  FATORES_CO2_TEP, cada um via seu próprio fator), o CO2_Emissions.csv
  intermediário do Waste (CO2_Waste) e a linha 'Total (Transp + Agri)' do
  CO2e*.csv, transposta; o total é então dividido por 8760 (HORAS).
  resultado final: CO2_Emissions.csv com as colunas Year e CO2_Total.

resultados finais (entradas do MACRO), na pasta 'MACRO input':
demand_ano.csv (combustíveis não-líquidos)
demand_LF_ano.csv (combustíveis líquidos)
elec_demand_ano.csv
h2_demand_ano.csv
CO2_Emissions.csv
"""

import os
import re
import pandas as pd

# ---------------------------------------------------------------- configuração

in_dir = 'EP output'                        # saídas do EP
waste_dir = 'Waste output'                  # saídas do modelo Waste
ta_dir = 'Transport_Agriculture output'     # saídas do modelo transporte-agricultura
out_dir = 'MACRO input'                     # resultado final (soma das três fontes)
ep_dir = os.path.join(out_dir, '_EP_convertido')       # intermediário, só EP
waste_out_dir = os.path.join(out_dir, '_Waste_convertido')   # intermediário, só Waste

ANOS = range(2025, 2051, 5)
HORAS = 8760

# --- hidrogênio -------------------------------------------------------------
# O arquivo de H2 do EP (Demand_Hydrogen_mass_*) vem em MASSA, não em MWh, e é
# convertido pelo PCS (poder calorífico superior) do H2 = 141,8 MJ/kg.
# 141,8 / 3600 = 0,039389 MWh/kg  (o PCI seria 120 MJ/kg = 0,033333 MWh/kg).
#
# CONFERIR a unidade de massa do arquivo antes de rodar: kg, t ou kt. O fator
# muda três ordens de grandeza entre uma opção e outra.
UNIDADE_MASSA_H2 = 't'          # 'kg', 't' ou 'kt'

PCS_H2_MJ_POR_KG = 141.8
MJ_POR_MWH = 3600.0
KG_POR_UNIDADE = {'kg': 1.0, 't': 1e3, 'kt': 1e6}

# MWh por unidade de massa do arquivo
PCS_H2_MWH = (PCS_H2_MJ_POR_KG / MJ_POR_MWH) * KG_POR_UNIDADE[UNIDADE_MASSA_H2]

# prefixo das colunas de UF no h2_demand_[ano].csv. Precisa ser IGUAL ao usado
# pelo transp-agric, senão a ETAPA 3 vai criar colunas duplicadas em vez de
# somar (a diferença aparece no relatório de colunas no fim da execução).
PREFIXO_H2 = 'h2_BR_'

# arquivo de emissões do transp-agric: identificado pelo PREFIXO "co2e" no
# nome (casamento tolerante a maiúsculas/minúsculas e espaço vs. underscore,
# via normalizar() -- igual ao usado para co2_*.csv do EP e SAIDA_WASTE_*),
# não pelo nome completo. Casa CO2e.csv, CO2e_S0.csv, co2e final.csv etc.
TA_EMISSOES_PREFIXO = 'co2e'
TA_EMISSOES_LINHA = 'Total (Transp + Agri)'

# quando uma coluna existe em um modelo e não no outro: True preenche com zero,
# False interrompe a execução. Em ambos os casos a diferença é reportada na tela.
PREENCHER_FALTANTES_COM_ZERO = True

# energéticos que aparecem nas saídas do EP mas NÃO devem ser processados: não
# têm fator de CO2 cadastrado e não geram coluna de demanda. São descartados
# explicitamente (e antes de qualquer casamento por prefixo) porque alguns
# colidiriam por engano com tokens conhecidos: 'charcoal mass' começa com
# 'charcoal_' (token de demanda Charcoal) e 'firewood mass' com 'firewood_'
# (fator Firewood). Nomes na forma normalizada (minúsculas, espaço->underscore).
IGNORAR = {'black_liquor', 'charcoal_mass', 'coke_gas', 'firewood_mass', 'tar'}

# fatores de emissão de CO2 de energéticos que não aparecem nas planilhas de
# demanda (Liquid Fuels / Outros Combustíveis): entram só na conta de CO2,
# nunca em Demand_[Energetico]. Cada energético desta lista deve ter um
# arquivo próprio em 'EP output' com o mesmo nome (ex.: Coal_S0.csv,
# Steam_Coal_3100_S0.csv), igual ao que já acontece com Coal hoje.
# Os fatores originais estão em tCO2e/tep e a demanda do EP sai em MWh,
# então são convertidos para tCO2e/MWh (1 tep = 41,868 GJ / 3,6 GJ por MWh
# = 11,63 MWh).
MWH_POR_TEP = 11.63

FATORES_CO2_TEP = {
    'Coal': 3.98,
    'Biogas': 0.00225472099398565,
    'Biomass': 0.0795491993467333,
    'Coal_Coke': 4.50824157,
    'Commercial_LPG': 2.65485022343153,
    'Dry_Natural_Gas': 2.37539304015129,
    'Firewood': 0.525262011613697,
    'Heavy_Fuel_Oil': 3.24843183801881,
    'Kerosene': 3.02048311838864,
    'LPG': 2.65090454095986,
    'Non_Renewables': 6.03971908321129,
    'Petroleum_Coke': 4.09230407410899,
    'Petroleum_Derived': 3.07794718090624,
    'Refinery_Gas': 2.41955214685352,
    'Residential_LPG': 2.6575604731073,
    'Steam_Coal_3100': 4.0616,
    'Steam_Coal_3300': 4.0616,
    'Steam_Coal_3700': 4.0616,
    'Steam_Coal_4200': 4.0616,
    'Steam_Coal_4500': 4.0616,
    'Steam_Coal_4700': 4.0616,
    'Steam_Coal_6000': 4.0616,
    'Sugarcane_Bagasse': 0.0738815424123426,
}   # tCO2e/tep

FATORES_CO2_MWH = {
    nome: fator / MWH_POR_TEP for nome, fator in FATORES_CO2_TEP.items()
}   # tCO2e/MWh

os.makedirs(out_dir, exist_ok=True)
os.makedirs(ep_dir, exist_ok=True)
os.makedirs(waste_out_dir, exist_ok=True)

# maps energy name (token) from the source file -> target column name (sem "Demand_")
en_nome = {
    "Liquid Fuels": {
        "Ethanol": "Ethanol",
        "Gasoline": "Gasoline",
        "Flexfuel": "Flexfuel",
        "JetFuel": "Jetfuel",
        "JetFuel_SAF": "SAF_Jetfuel",
        "JetFuel_Fossil": "fossil_Jetfuel",
        "Diesel": "Diesel",
        "BioDiesel": "BioDiesel",
    },
    "Outros Combustíveis": {
        "Ammonia": "Ammonia",
        "Biomethane": "Biomethane",
        "Charcoal": "Charcoal",
        "NaturalGas": "NaturalGas",
        # Hydrogen saiu daqui de propósito: passou a compor o h2_demand_[ano].csv
    },
}

lf_columns = [f'Demand_{c}' for c in en_nome["Liquid Fuels"].values()]
cb_columns = [f'Demand_{c}' for c in en_nome["Outros Combustíveis"].values()]

# mapa: nome do energético no arquivo -> (categoria, coluna alvo "Demand_xxx")
token_para_categoria_alvo = {
    fonte: (categoria, f'Demand_{alvo}')
    for categoria, mapa in en_nome.items()
    for fonte, alvo in mapa.items()
}

# diferenças de colunas encontradas na etapa 2, reportadas no final
relatorio_colunas = []


def normalizar(nome):
    """normaliza um nome de arquivo (sem extensão) para casar independentemente
    de caixa e de espaço vs. underscore: minúsculas e espaços viram underscore.
    Ex.: 'steam coal 3100_S0' -> 'steam_coal_3100_s0'."""
    return nome.lower().replace(' ', '_')


def ler_csv(caminho):
    """utf-8-sig porque os arquivos do transp-agric vêm com BOM."""
    return pd.read_csv(caminho, encoding='utf-8-sig')


def colunas_estado(df):
    """colunas de UF: todas menos time_index e year."""
    return [c for c in df.columns if c not in ('time_index', 'year')]


def total_nacional(df, ano):
    """soma das colunas de UF para o ano informado (0.0 se o ano não existir)."""
    linha = df[df['year'] == ano]
    if linha.empty:
        return 0.0
    return float(linha[colunas_estado(df)].sum(axis=1).values[0])


# ============================================================== ETAPA 1: EP ===

csv_lista = [f for f in os.listdir(in_dir) if f.lower().endswith('.csv')]

arquivos_energia = {}        # coluna alvo (Demand_xxx) -> nome do arquivo
arquivos_co2_fator = {}      # nome do energético (chave de FATORES_CO2_MWH) -> nome do arquivo
arquivos_co2_direto = []     # nomes dos arquivos CO2_*.csv
arquivos_eletricidade = {}   # ano -> nome do arquivo electricity_[ano]_*.csv
arquivo_h2_massa = None      # nome do arquivo Demand_Hydrogen_mass_*.csv

# tokens de demanda normalizados, do mais longo para o mais curto, para casar
# "JetFuel_SAF" antes de "JetFuel", por exemplo
tokens_demanda_norm = sorted(
    ((normalizar(fonte), destino)
     for fonte, (_categoria, destino) in token_para_categoria_alvo.items()),
    key=lambda item: len(item[0]), reverse=True,
)

# chaves de fator de CO2 normalizadas, também do mais longo para o mais curto,
# para casar "Coal_Coke" antes de "Coal", "Steam_Coal_3100" antes de "Coal" etc.
chaves_co2_norm = sorted(
    ((normalizar(chave), chave) for chave in FATORES_CO2_MWH),
    key=lambda item: len(item[0]), reverse=True,
)


def casar_demanda(nucleo):
    """casa o miolo de um nome (já normalizado, sem o prefixo demand_ e sem
    extensão) com um token de demanda; retorna a coluna alvo 'Demand_xxx' ou
    None. Ex.: 'hydrogen_mass_s0' -> 'Demand_Hydrogen'."""
    for chave_norm, destino in tokens_demanda_norm:
        if nucleo == chave_norm or nucleo.startswith(chave_norm + '_'):
            return destino
    return None


for csv_nome in csv_lista:
    # nome normalizado: casa independentemente de caixa e de espaço vs. underscore
    nb = normalizar(csv_nome.rsplit('.', 1)[0])

    m = re.match(r'^electricity_(\d{4})_.+$', nb)
    if m:
        arquivos_eletricidade[int(m.group(1))] = csv_nome
        continue

    if nb.startswith('electricity'):
        # electricity_[cenario].csv, sem ano: ignorado por enquanto
        continue

    if nb == 'exo_demand_metadata':
        continue

    # arquivos explicitamente ignorados (ver IGNORAR): descartados ANTES de
    # qualquer casamento por prefixo para não serem capturados por engano
    if any(nb == ig or nb.startswith(ig + '_') for ig in IGNORAR):
        continue

    # CO2 direto: co2_*.csv (o arquivo real vem em minúsculas)
    if nb == 'co2' or nb.startswith('co2_'):
        arquivos_co2_direto.append(csv_nome)
        continue

    # hidrogênio: capturado ANTES do casamento genérico de demanda, porque não
    # gera coluna Demand_Hydrogen e sim o h2_demand_[ano].csv (ver item (e))
    nucleo_h2 = nb[len('demand_'):] if nb.startswith('demand_') else nb
    if nucleo_h2 == 'hydrogen' or nucleo_h2.startswith('hydrogen_'):
        if arquivo_h2_massa is not None:
            raise ValueError(
                f'mais de um arquivo de hidrogênio em {in_dir}: '
                f'{arquivo_h2_massa} e {csv_nome}')
        arquivo_h2_massa = csv_nome
        continue

    # arquivos de demanda (Liquid Fuels e Outros Combustíveis) agora vêm com o
    # prefixo Demand_ no nome do arquivo (ex.: Demand_Diesel_S0.csv)
    if nb.startswith('demand_'):
        destino = casar_demanda(nb[len('demand_'):])
        if destino is not None:
            arquivos_energia[destino] = csv_nome
        else:
            print(f'Aviso: {csv_nome} tem prefixo Demand_ mas não corresponde '
                  f'a nenhum energético conhecido, deixado de lado')
        continue

    # NaturalGas é o único energético de demanda que manteve o nome antigo,
    # sem o prefixo Demand_
    if nb == 'naturalgas' or nb.startswith('naturalgas_'):
        arquivos_energia['Demand_NaturalGas'] = csv_nome
        continue

    # fator de CO2 (energéticos que entram só na conta de CO2, sem prefixo)
    encontrado_co2 = False
    for chave_norm, chave in chaves_co2_norm:
        if nb == chave_norm or nb.startswith(chave_norm + '_'):
            arquivos_co2_fator[chave] = csv_nome
            encontrado_co2 = True
            break
    if encontrado_co2:
        continue

    print(f'Aviso: {csv_nome} não corresponde a nenhuma coluna esperada, deixado de lado')

# --- (a) e (b): Liquid Fuels e Outros Combustíveis, por ano ---
for ano in ANOS:
    linha_lf = {}
    for alvo in lf_columns:
        arq = arquivos_energia.get(alvo)
        linha_lf[alvo] = 0.0 if arq is None else total_nacional(ler_csv(f'{in_dir}/{arq}'), ano) / HORAS

    lfs = pd.DataFrame([linha_lf])
    lfs = pd.concat([lfs] * HORAS, ignore_index=True)
    lfs.insert(0, 'Time_Index', range(1, len(lfs) + 1))
    lfs.to_csv(f'{ep_dir}/demand_LF_{ano}.csv', index=False)

    linha_cb = {}
    for alvo in cb_columns:
        arq = arquivos_energia.get(alvo)
        linha_cb[alvo] = 0.0 if arq is None else total_nacional(ler_csv(f'{in_dir}/{arq}'), ano) / HORAS

    cbs = pd.DataFrame([linha_cb])
    cbs = pd.concat([cbs] * HORAS, ignore_index=True)
    cbs.insert(0, 'Time_Index', range(1, len(cbs) + 1))
    cbs.to_csv(f'{ep_dir}/demand_{ano}.csv', index=False)

# --- (c): Electricity, já horária, só reformata cabeçalho ---
for ano, arq in arquivos_eletricidade.items():
    df = ler_csv(f'{in_dir}/{arq}')
    if 'year' in df.columns:
        df = df.drop(columns=['year'])
    estados = [c for c in df.columns if c != 'time_index']
    df = df.rename(columns={'time_index': 'Time_Index'})
    df = df.rename(columns={c: f'elec_BR_{c}' for c in estados})
    df.to_csv(f'{ep_dir}/elec_demand_{ano}.csv', index=False)

# --- (e): Hydrogen, massa -> MWh (PCS), por UF ---
if arquivo_h2_massa is None:
    print(f'Aviso: nenhum arquivo de hidrogênio encontrado em {in_dir}; '
          f'o h2_demand do EP não será gerado')
else:
    df_h2 = ler_csv(f'{in_dir}/{arquivo_h2_massa}')
    estados_h2 = colunas_estado(df_h2)
    print(f'Hidrogênio: {arquivo_h2_massa}, massa em "{UNIDADE_MASSA_H2}", '
          f'convertida por {PCS_H2_MWH:.6g} MWh/{UNIDADE_MASSA_H2} (PCS)')

    for ano in ANOS:
        linha = df_h2[df_h2['year'] == ano]
        if linha.empty:
            print(f'Aviso: {arquivo_h2_massa} não tem dados para o ano {ano}')
            valores = {c: 0.0 for c in estados_h2}
        else:
            valores = {c: float(linha[c].values[0]) * PCS_H2_MWH / HORAS
                       for c in estados_h2}

        df_ano = pd.DataFrame([valores])
        df_ano = pd.concat([df_ano] * HORAS, ignore_index=True)
        df_ano = df_ano.rename(columns={c: f'{PREFIXO_H2}{c}' for c in estados_h2})
        df_ano.insert(0, 'Time_Index', range(1, len(df_ano) + 1))
        df_ano.to_csv(f'{ep_dir}/h2_demand_{ano}.csv', index=False)


# --- (d): CO2, abertas por fonte (arquivo intermediário, para conferência) ---
co2_linhas = {}
for ano in ANOS:
    linha = {}
    for i, arq in enumerate(arquivos_co2_direto):
        df = ler_csv(f'{in_dir}/{arq}')
        nome_col = 'CO2_EP_Base' if len(arquivos_co2_direto) == 1 else f'CO2_EP_Base_{i + 1}'
        linha[nome_col] = total_nacional(df, ano)
    for nome_energetico, arq in arquivos_co2_fator.items():
        df = ler_csv(f'{in_dir}/{arq}')
        fator = FATORES_CO2_MWH[nome_energetico]
        linha[f'CO2_{nome_energetico}'] = total_nacional(df, ano) * fator
    co2_linhas[ano] = linha
co2_ep = pd.DataFrame.from_dict(co2_linhas, orient='index')
co2_ep.index.name = 'Year'
co2_ep.reset_index().to_csv(f'{ep_dir}/CO2_Emissions.csv', index=False)


# =========================================================== ETAPA 2: Waste ===

waste_csv_lista = [f for f in os.listdir(waste_dir) if f.lower().endswith('.csv')]

arquivo_waste_en = next((f for f in waste_csv_lista if f.startswith('SAIDA_WASTE_EN')), None)
arquivo_waste_gee = next((f for f in waste_csv_lista if f.startswith('SAIDA_WASTE_GEE')), None)

if arquivo_waste_en is None:
    print('Aviso: nenhum arquivo SAIDA_WASTE_EN* encontrado em Waste output')
if arquivo_waste_gee is None:
    print('Aviso: nenhum arquivo SAIDA_WASTE_GEE* encontrado em Waste output')

# --- Electricity (por UF, sem somar os estados) ---
if arquivo_waste_en is not None:
    df_en = ler_csv(f'{waste_dir}/{arquivo_waste_en}')
    col_ano, estados_en = df_en.columns[0], list(df_en.columns[1:])
    df_en = df_en.rename(columns={col_ano: 'Ano'})

    for ano in ANOS:
        linha = df_en[df_en['Ano'] == ano]
        if linha.empty:
            print(f'Aviso: {arquivo_waste_en} não tem dados para o ano {ano}')
            valores = {c: 0.0 for c in estados_en}
        else:
            valores = {c: float(linha[c].values[0]) / HORAS for c in estados_en}

        df_ano = pd.DataFrame([valores])
        df_ano = pd.concat([df_ano] * HORAS, ignore_index=True)
        df_ano = df_ano.rename(columns={c: f'elec_BR_{c}' for c in estados_en})
        df_ano.insert(0, 'Time_Index', range(1, len(df_ano) + 1))
        df_ano.to_csv(f'{waste_out_dir}/elec_demand_{ano}.csv', index=False)

# --- CO2 (soma das UFs -> total nacional por ano) ---
co2_waste = pd.Series(0.0, index=list(ANOS))
if arquivo_waste_gee is not None:
    df_gee = ler_csv(f'{waste_dir}/{arquivo_waste_gee}')
    col_ano, estados_gee = df_gee.columns[0], list(df_gee.columns[1:])
    df_gee = df_gee.rename(columns={col_ano: 'Ano'})

    for ano in ANOS:
        linha = df_gee[df_gee['Ano'] == ano]
        if linha.empty:
            print(f'Aviso: {arquivo_waste_gee} não tem dados para o ano {ano}')
            continue
        co2_waste[ano] = float(linha[estados_gee].sum(axis=1).values[0])

co2_waste_df = pd.DataFrame({'Year': list(ANOS), 'CO2_Waste': co2_waste.values})
co2_waste_df.to_csv(f'{waste_out_dir}/CO2_Emissions.csv', index=False)


# ================================================ ETAPA 3: soma das 3 fontes ===

def somar_demandas(nome_arquivo, fontes):
    """Combina o mesmo arquivo entre várias fontes (rótulo, pasta, sinal).

    Cada item de `fontes` é uma tupla (rotulo, pasta) ou (rotulo, pasta, sinal),
    onde sinal é +1 para somar (padrão, se omitido) ou -1 para subtrair.

    Alinha as linhas pelo Time_Index e as colunas pelo nome. A ordem final das
    colunas segue a primeira fonte que existir, com as colunas exclusivas das
    demais fontes no fim. Fontes onde o arquivo não existe são ignoradas.
    """
    fontes_norm = [(f[0], f[1], f[2] if len(f) > 2 else 1) for f in fontes]

    existentes = [(rotulo, os.path.join(pasta, nome_arquivo), sinal)
                  for rotulo, pasta, sinal in fontes_norm
                  if os.path.exists(os.path.join(pasta, nome_arquivo))]
    faltando = [rotulo for rotulo, pasta, sinal in fontes_norm
                if not os.path.exists(os.path.join(pasta, nome_arquivo))]

    if not existentes:
        return None

    if faltando:
        relatorio_colunas.append(
            f'{nome_arquivo}: sem arquivo de {", ".join(faltando)}, ignorado(s) na conta')

    dfs = [(rotulo, ler_csv(caminho).set_index('Time_Index'), sinal)
           for rotulo, caminho, sinal in existentes]

    indice_base = dfs[0][1].index
    for rotulo, df, _ in dfs[1:]:
        if not df.index.equals(indice_base):
            raise ValueError(f'{nome_arquivo}: Time_Index diferente entre {dfs[0][0]} e {rotulo}')

    # união das colunas, mantendo a ordem da primeira fonte e as extras no fim
    colunas = list(dfs[0][1].columns)
    for _, df, _ in dfs[1:]:
        colunas += [c for c in df.columns if c not in colunas]

    for rotulo, df, _ in dfs:
        faltando_col = [c for c in colunas if c not in df.columns]
        if faltando_col:
            relatorio_colunas.append(
                f'{nome_arquivo}: ausentes em {rotulo} (preenchidas com zero) -> {", ".join(faltando_col)}')
    if any(c not in df.columns for _, df, _ in dfs for c in colunas) and not PREENCHER_FALTANTES_COM_ZERO:
        raise ValueError(f'{nome_arquivo}: colunas divergentes e PREENCHER_FALTANTES_COM_ZERO=False')

    resultado = None
    for _, df, sinal in dfs:
        df = df.reindex(columns=colunas, fill_value=0) * sinal
        resultado = df if resultado is None else resultado.add(df, fill_value=0)

    resultado = resultado[colunas]
    resultado.reset_index().to_csv(os.path.join(out_dir, nome_arquivo), index=False)
    return resultado


for ano in ANOS:
    somar_demandas(f'demand_{ano}.csv', [('EP', ep_dir), ('transp-agric', ta_dir)])
    somar_demandas(f'demand_LF_{ano}.csv', [('EP', ep_dir), ('transp-agric', ta_dir)])
    somar_demandas(f'elec_demand_{ano}.csv', [
        ('EP', ep_dir), ('transp-agric', ta_dir), ('Waste', waste_out_dir, -1),
    ])
    somar_demandas(f'h2_demand_{ano}.csv', [('EP', ep_dir), ('transp-agric', ta_dir)])


# --- CO2 final: soma EP + Waste + transp-agric numa única coluna ---

# transp-agric: procura na pasta o csv cujo nome (normalizado) comece por
# "co2e" -- ex.: CO2e.csv, CO2e_S0.csv, co2e final.csv; se houver mais de um
# candidato, interrompe (ambíguo, melhor conferir manualmente)
candidatos_ta_co2 = [
    f for f in os.listdir(ta_dir) if f.lower().endswith('.csv')
    and (lambda nb: nb == TA_EMISSOES_PREFIXO or nb.startswith(TA_EMISSOES_PREFIXO + '_'))(
        normalizar(f.rsplit('.', 1)[0]))
]
if len(candidatos_ta_co2) > 1:
    raise ValueError(
        f'mais de um arquivo "{TA_EMISSOES_PREFIXO}*.csv" em {ta_dir}: {candidatos_ta_co2}')
arquivo_ta_co2 = candidatos_ta_co2[0] if candidatos_ta_co2 else None

# tabela transposta (anos nas colunas), pega a linha do total
co2_ta = pd.Series(0.0, index=list(ANOS))
if arquivo_ta_co2 is not None:
    bruto = ler_csv(os.path.join(ta_dir, arquivo_ta_co2))
    rotulos = bruto.iloc[:, 0].astype(str).str.strip()
    linha = bruto[rotulos.str.lower() == TA_EMISSOES_LINHA.lower()]
    if linha.empty:
        raise ValueError(f'{arquivo_ta_co2}: linha "{TA_EMISSOES_LINHA}" não encontrada')
    # transpõe: mantém só as colunas cujo nome é um ano. Aceita tanto "2025"
    # quanto "2025.00000" (o CO2e.csv do transp-agric vem com os anos
    # formatados como float no cabeçalho; um casamento exato de 4 dígitos
    # perdia essas colunas silenciosamente e zerava a emissão de Transp+Agri)
    colunas_ano = {}
    for c in bruto.columns:
        cs = str(c).strip()
        try:
            valor = float(cs)
        except ValueError:
            continue
        if valor.is_integer() and 1900 <= valor <= 2100:
            colunas_ano[c] = int(valor)
    linha = linha.iloc[0]
    co2_ta = pd.Series(
        {ano: pd.to_numeric(linha[c], errors='coerce') for c, ano in colunas_ano.items()}
    ).reindex(list(ANOS)).fillna(0.0)
else:
    print(f'Aviso: nenhum arquivo "{TA_EMISSOES_PREFIXO}*.csv" encontrado em {ta_dir}, '
          f'emissões do transp-agric zeradas')

# final: soma de todas as colunas do EP + total do Waste + total do transp-agric,
# dividida por 8760 (HORAS)
co2_total = (
    co2_ep.reindex(list(ANOS)).fillna(0.0).sum(axis=1)
    + co2_waste.reindex(list(ANOS)).fillna(0.0)
    + co2_ta
) / HORAS
co2_final = pd.DataFrame({'Year': list(ANOS), 'CO2_Total': co2_total.values})
co2_final.to_csv(os.path.join(out_dir, 'CO2_Emissions.csv'), index=False)


# ======================================================== relatório de colunas ===

if relatorio_colunas:
    print('\nDiferenças de colunas entre os modelos '
          f'(preenchidas com zero = {PREENCHER_FALTANTES_COM_ZERO}):')
    for linha_rel in relatorio_colunas:
        print(f'  - {linha_rel}')
else:
    print('\nNenhuma diferença de colunas entre os modelos.')