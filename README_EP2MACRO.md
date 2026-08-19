# EP2MACRO — Tradutor de saídas (EP + Waste + Transporte-Agricultura) para o formato MACRO

Script Python (`EP2MACRO.py`) que converte as saídas de três modelos — **EP** (planejamento energético), **Waste** (resíduos) e **Transport_Agriculture** (transporte e agricultura) — para um formato único, soma os resultados e gera os arquivos de entrada do modelo **MACRO**.

Este README documenta contrato de entrada/saída, configuração e regras de negócio do script, para orientar sua integração como etapa de pipeline na plataforma do NZB.

## Requisitos

- Python 3
- [pandas](https://pandas.pydata.org/)

Sem outras dependências. O script não recebe argumentos de linha de comando: toda a configuração é feita por constantes no topo do arquivo (veja [Configuração](#configuração)).

## Como executar

```bash
python EP2MACRO.py
```

Deve ser executado a partir do diretório que contém as pastas de entrada listadas abaixo (`in_dir`, `waste_dir`, `ta_dir`). O script cria as pastas de saída automaticamente (`os.makedirs(..., exist_ok=True)`) se não existirem. Mensagens de aviso, erro e o relatório final de diferenças de colunas são impressos em stdout — se integrado a um pipeline, capturar essa saída é recomendado para logging/monitoramento.

## Estrutura de pastas

| Constante | Pasta padrão | Papel |
|---|---|---|
| `in_dir` | `EP output` | entrada — saídas do modelo EP |
| `waste_dir` | `Waste output` | entrada — saídas do modelo Waste |
| `ta_dir` | `Transport_Agriculture output` | entrada — saídas já no formato MACRO |
| `out_dir` | `MACRO input` | **saída final** — entradas do MACRO |
| `ep_dir` | `MACRO input/_EP_convertido` | saída intermediária (só EP, para conferência) |
| `waste_out_dir` | `MACRO input/_Waste_convertido` | saída intermediária (só Waste, para conferência) |

Esses nomes são strings fixas no código (linhas 113–118); para integrar em outra estrutura de diretórios, ajustar essas constantes (ou parametrizá-las) é o ponto de entrada natural.

## O que o script faz

O processamento tem três etapas sequenciais.

### Etapa 1 — converte as saídas do EP

Lê todos os `.csv` de `EP output` e classifica cada arquivo pelo **início do nome** (o sufixo de cenário, ex. `_S0`, é livre e ignorado). O casamento de nomes é tolerante a maiúsculas/minúsculas e trata espaço como equivalente a underscore (função `normalizar`), então `steam coal 3100_S0.csv` casa com o token `Steam_Coal_3100`.

- **Liquid Fuels e Outros Combustíveis** (`Demand_[Energetico]_[cenario].csv`, exceto `NaturalGas` que não tem prefixo `Demand_`): para cada energético e cada ano em `ANOS`, soma as UFs, divide por 8760 e repete o valor em 8760 linhas horárias. Gera `demand_LF_[ano].csv` (combustíveis líquidos) e `demand_[ano].csv` (demais). Energético sem arquivo correspondente recebe demanda zero. Hidrogênio **não** entra aqui.
- **Electricity** (`electricity_[ano]_[cenario].csv`, já horário, 8760 linhas): renomeia `time_index` → `Time_Index`, remove a coluna `year`, prefixa cada UF com `elec_BR_`. Gera `elec_demand_[ano].csv`.
- **Hydrogen** (`Demand_Hydrogen_mass_[cenario].csv`): vem em **massa** de H2, não em MWh. É convertido para MWh pelo PCS do H2, mantido **por UF** (sem somar estados), dividido por 8760 e repetido em 8760 linhas. Gera `h2_demand_[ano].csv`, com colunas prefixadas por `PREFIXO_H2`.
- **CO2**: soma as UFs dos arquivos `co2_*.csv` (emissão nacional direta) e soma a demanda de cada energético cadastrado em `FATORES_CO2_TEP` (ex. `Coal_*.csv`, `Steam_Coal_3100_*.csv`), cada um convertido pelo seu próprio fator (tCO2e/tep → tCO2e/MWh). Gera colunas `CO2_EP_Base` e `CO2_[Energetico]` por energético encontrado.
- Arquivos `EXO_DEMAND_METADATA.csv` e `electricity_[cenario].csv` (sem ano) são ignorados. Energéticos em `IGNORAR` (sem fator de CO2 nem coluna de demanda: `black_liquor`, `charcoal_mass`, `coke_gas`, `firewood_mass`, `tar`) são descartados antes de qualquer casamento por prefixo.
- Resultado intermediário gravado em `MACRO input/_EP_convertido`.

### Etapa 2 — converte as saídas do Waste

Lê `Waste output`, identificando os arquivos pelo prefixo (sufixo de cenário livre, igual ao EP):

- `SAIDA_WASTE_EN-[cenario].csv` → eletricidade por ano e UF (2020–2050). Mantém **por UF** (sem somar), divide por 8760, repete em 8760 linhas. Gera `elec_demand_[ano].csv`.
- `SAIDA_WASTE_GEE-[cenario].csv` → emissões de CO2 por ano e UF (só nos anos de `ANOS`: 2025, 2030, ..., 2050). Soma as UFs → total nacional. Gera coluna `CO2_Waste`.
- Resultado intermediário gravado em `MACRO input/_Waste_convertido`.

### Etapa 3 — soma as três fontes

Combina EP + Waste + Transport_Agriculture (este último já vem pronto no formato MACRO, na pasta `Transport_Agriculture output`, com os arquivos `demand_[ano].csv`, `demand_LF_[ano].csv`, `elec_demand_[ano].csv`, `h2_demand_[ano].csv` e `ExternalEmissions2Macro_FirewoodDemand2Magpie.csv`).

- **Demandas**: alinhamento das linhas pelo `Time_Index` (não pela posição) e das colunas pelo nome (a ordem difere entre modelos). Coluna presente em só uma fonte é reportada no relatório final e preenchida com zero nas demais (controlado por `PREENCHER_FALTANTES_COM_ZERO`).
  - `elec_demand_[ano].csv` = EP + transp-agric **−** Waste (Waste é subtraído).
  - `demand_[ano].csv`, `demand_LF_[ano].csv`, `h2_demand_[ano].csv` = EP + transp-agric (Waste não gera essas colunas).
- **CO2** (`CO2_Emissions.csv`, colunas `Year` e `CO2_Total`): soma todas as colunas do `CO2_Emissions.csv` intermediário do EP, o `CO2_Waste` do intermediário do Waste, e a linha `Total (Transp + Agri)` (transposta) de `ExternalEmissions2Macro_FirewoodDemand2Magpie.csv`; o total é dividido por 8760.

## Saídas finais (entradas do MACRO)

Gravadas em `MACRO input/`, uma por ano em `ANOS` (exceto CO2, que é único e já anual):

- `demand_[ano].csv` — combustíveis não-líquidos
- `demand_LF_[ano].csv` — combustíveis líquidos
- `elec_demand_[ano].csv`
- `h2_demand_[ano].csv`
- `CO2_Emissions.csv` — colunas `Year`, `CO2_Total`

## Configuração

Constantes no topo do arquivo que **precisam ser conferidas antes de cada execução**:

- `ANOS = range(2025, 2051, 5)` — anos processados (2025, 2030, ..., 2050).
- `HORAS = 8760` — horas no ano, usado para toda conversão anual→horária.
- `UNIDADE_MASSA_H2` — `'kg'`, `'t'` ou `'kt'`. **Precisa bater com a unidade real do arquivo de hidrogênio do EP**; errar essa constante desloca o resultado em três ordens de grandeza. Não há validação automática — é responsabilidade de quem roda o script conferir a unidade do arquivo de origem.
- `PCS_H2_MJ_POR_KG = 141.8` — poder calorífico superior do H2, usado na conversão massa→MWh.
- `PREFIXO_H2 = 'h2_BR_'` — prefixo das colunas de UF no `h2_demand_[ano].csv`. **Precisa ser idêntico** ao usado pelo modelo transporte-agricultura, senão a Etapa 3 cria colunas duplicadas em vez de somar (o desvio aparece no relatório de colunas ao final da execução).
- `PREENCHER_FALTANTES_COM_ZERO` — `True` preenche colunas ausentes em um modelo com zero; `False` interrompe a execução (`ValueError`) quando há divergência de colunas entre fontes. Em ambos os casos a diferença é reportada em stdout.
- `IGNORAR` — energéticos do EP descartados de propósito (sem fator de CO2 e sem coluna de demanda).
- `FATORES_CO2_TEP` — dicionário de fatores de emissão (tCO2e/tep) por energético; convertido internamente para tCO2e/MWh via `MWH_POR_TEP = 11.63`. Adicionar um novo energético à conta de CO2 significa adicionar uma entrada aqui **e** garantir que exista o arquivo `[Energetico]_[cenario].csv` correspondente em `EP output`.
- `TA_EMISSOES_CSV` / `TA_EMISSOES_LINHA` — nome do arquivo e rótulo da linha usados para extrair o total de emissões do modelo transporte-agricultura.

## Convenção de nomes de arquivo (EP)

O casamento de arquivos do EP por prefixo é sensível à ordem de verificação: tokens mais longos são testados antes dos mais curtos (ex. `JetFuel_SAF` antes de `JetFuel`; `Steam_Coal_3100` antes de `Coal`), para evitar que um nome mais específico seja capturado pelo token errado. Ao adicionar um novo energético cujo nome é prefixo de outro já cadastrado, revisar `tokens_demanda_norm` e `chaves_co2_norm` (ordenação por tamanho do nome normalizado, decrescente).

## Erros e avisos

O script imprime avisos (`Aviso: ...`) e segue a execução quando: um arquivo não corresponde a nenhuma coluna esperada; não é encontrado um arquivo de hidrogênio, de Waste, ou de emissões do transp-agric; falta um ano em algum arquivo (nesse caso os valores daquele ano ficam em zero).

O script interrompe a execução com `ValueError` quando: há mais de um arquivo de hidrogênio em `EP output`; o `Time_Index` diverge entre fontes num mesmo arquivo a somar; a linha de total não é encontrada em `ExternalEmissions2Macro_FirewoodDemand2Magpie.csv`; ou há colunas divergentes entre fontes com `PREENCHER_FALTANTES_COM_ZERO = False`.

Ao final, é impresso um relatório consolidado de todas as diferenças de colunas encontradas na Etapa 3 (arquivos com fonte ausente, colunas exclusivas de uma fonte).

## Pontos de atenção para integração na plataforma do NZB

- O script não tem argumentos de CLI nem variáveis de ambiente — para rodar como job parametrizável, os caminhos de pasta (`in_dir`, `waste_dir`, `ta_dir`, `out_dir`) e `UNIDADE_MASSA_H2` são os candidatos naturais a virar parâmetros externos.
- Não há validação de schema nas leituras de CSV além do que está descrito acima — arquivos com colunas ou nomes fora do esperado geram avisos silenciosos ("deixado de lado") em vez de erro; se a plataforma precisa garantir que nenhum arquivo de entrada seja ignorado por engano, vale capturar e tratar essas mensagens de aviso como sinal de falha.
- A leitura de CSV usa `encoding='utf-8-sig'` em todos os arquivos (por causa do BOM nos arquivos do transp-agric); arquivos de outras origens com encoding diferente vão falhar ou ler incorretamente.
- O script sobrescreve arquivos de saída existentes sem confirmação (`to_csv` padrão) — não há checagem de idempotência ou versionamento de execução.
- `UNIDADE_MASSA_H2` é a configuração de maior risco: um erro nela não gera exceção, apenas um resultado de hidrogênio errado por 1000x ou 1.000.000x. Vale considerar validação automática (ex. faixa de valores plausível) antes de expor esse parâmetro a usuários da plataforma.
