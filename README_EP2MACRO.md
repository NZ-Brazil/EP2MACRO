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
| `in_dir` | `EP output` | entrada — saídas do modelo EP (maioria dos arquivos) |
| `IN_DIR_ELETRICIDADE_EXTRA` | derivada de `in_dir` (`<pai de in_dir>/ShapeData/final_energy`) | entrada — apenas `electricity_[ano]_*.csv`, pesquisada **recursivamente**; ver nota abaixo |
| `waste_dir` | `Waste output` | entrada — saídas do modelo Waste |
| `ta_dir` | `Transport_Agriculture output` | entrada — saídas já no formato MACRO |
| `out_dir` | `MACRO input` | **saída final** — entradas do MACRO |
| `ep_dir` | `MACRO input/_EP_convertido` | saída intermediária (só EP, para conferência) |
| `waste_out_dir` | `MACRO input/_Waste_convertido` | saída intermediária (só Waste, para conferência) |

Esses nomes são strings fixas no código; para integrar em outra estrutura de diretórios, ajustar essas constantes (ou parametrizá-las) é o ponto de entrada natural.

**Nota sobre a plataforma NZB**: lá, o EP grava os arquivos `electricity_[ano]_*.csv` fora de `in_dir` (que costuma apontar para a subpasta `EXO_DEMAND`) — eles ficam numa pasta **irmã**, `ShapeData/final_energy` (dentro de uma subpasta por execução, ex. `electricity.csvd/`). `IN_DIR_ELETRICIDADE_EXTRA` é derivada automaticamente a partir do diretório-pai de `in_dir` e pesquisada recursivamente, então isso funciona sem configuração extra desde que `in_dir` aponte para a `EXO_DEMAND` real; se essa pasta não existir (uso local, com tudo solto em `EP output`), é ignorada silenciosamente e a eletricidade é buscada só em `in_dir`, como antes. Da mesma forma, os quatro arquivos de demanda do transp-agric (`demand_*`, `demand_LF_*`, `elec_demand_*`, `h2_demand_*`) e o `CO2e*.csv` são procurados dentro de `ta_dir` **recursivamente** (função `encontrar_arquivo`), então funcionam tanto soltos em `ta_dir` quanto dentro de uma subpasta (ex. `ta_dir/output/`).

## O que o script faz

O processamento tem três etapas sequenciais.

### Etapa 1 — converte as saídas do EP

Lê todos os `.csv` de `EP output` e classifica cada arquivo pelo **início do nome** (o sufixo de cenário, ex. `_S0`, é livre e ignorado). O casamento de nomes é tolerante a maiúsculas/minúsculas e trata espaço como equivalente a underscore (função `normalizar`), então `steam coal 3100_S0.csv` casa com o token `Steam_Coal_3100`.

- **Liquid Fuels e Outros Combustíveis** (`Demand_[Energetico]_[cenario].csv`, exceto `NaturalGas` que não tem prefixo `Demand_`): para cada energético e cada ano em `ANOS`, soma as UFs, divide por 8760 e repete o valor em 8760 linhas horárias. Gera `demand_LF_[ano].csv` (combustíveis líquidos) e `demand_[ano].csv` (demais). Energético sem arquivo correspondente recebe demanda zero. Hidrogênio **não** entra aqui.
- **Electricity** (`electricity_[ano]_[cenario].csv`, já horário, 8760 linhas): renomeia `time_index` → `Time_Index`, remove a coluna `year`, prefixa cada UF com `elec_BR_`. Gera `elec_demand_[ano].csv`. Procurada em `in_dir` **e** (recursivamente) em `IN_DIR_ELETRICIDADE_EXTRA`; se o mesmo ano aparecer nas duas pastas, prevalece a de `IN_DIR_ELETRICIDADE_EXTRA`. Se não for encontrada em nenhuma das duas, é impresso um aviso e o `elec_demand` do EP não é gerado (fica de fora da soma da Etapa 3, mas não interrompe a execução).
- **Hydrogen** (`Demand_Hydrogen_mass_[cenario].csv`): vem em **massa** de H2, não em MWh. A unidade dessa massa é descoberta automaticamente em `EXO_DEMAND_METADATA.csv` (coluna `unit`, na(s) linha(s) cujo `file_name` bate com o arquivo de hidrogênio já identificado — `detectar_unidade_massa_h2()`); só cai no fallback `UNIDADE_MASSA_H2` se os metadados não existirem, não tiverem a linha do hidrogênio, tiverem unidades divergentes entre as linhas, ou uma unidade não reconhecida (ver `UNIDADES_MASSA_METADADOS`) — em qualquer um desses casos, um aviso explica o motivo. Se a unidade detectada divergir da configurada manualmente, também é avisado, e a **detectada** é a usada. A massa (na unidade decidida) é então convertida para MWh pelo PCS do H2, mantida **por UF** (sem somar estados), dividida por 8760 e repetida em 8760 linhas. Gera `h2_demand_[ano].csv`, com colunas prefixadas por `PREFIXO_H2`.
- **CO2**: soma as UFs dos arquivos `co2_*.csv` (emissão nacional direta) e soma a demanda de cada energético cadastrado em `FATORES_CO2_TEP` (ex. `Coal_*.csv`, `Steam_Coal_3100_*.csv`), cada um convertido pelo seu próprio fator (tCO2e/tep → tCO2e/MWh). Gera colunas `CO2_EP_Base` e `CO2_[Energetico]` por energético encontrado.
- Arquivos `EXO_DEMAND_METADATA.csv` e `electricity_[cenario].csv` (sem ano) são ignorados. Energéticos em `IGNORAR` (sem fator de CO2 nem coluna de demanda: `black_liquor`, `charcoal_mass`, `coke_gas`, `firewood_mass`, `tar`) são descartados antes de qualquer casamento por prefixo.
- Resultado intermediário gravado em `MACRO input/_EP_convertido`.

### Etapa 2 — converte as saídas do Waste

Lê `Waste output`, identificando os arquivos pelo prefixo (sufixo de cenário livre, igual ao EP):

- `SAIDA_WASTE_EN-[cenario].csv` → eletricidade por ano e UF (2020–2050). Mantém **por UF** (sem somar), divide por 8760, repete em 8760 linhas. Gera `elec_demand_[ano].csv`. Se o arquivo tiver uma coluna `BR`, ela é descartada (eletricidade não deve ser somada, só mantida por UF).
- `SAIDA_WASTE_GEE-[cenario].csv` → emissões de CO2 por ano e UF (só nos anos de `ANOS`: 2025, 2030, ..., 2050). Gera coluna `CO2_Waste`. As colunas de UF e a coluna `BR` (quando existe) **nunca são somadas juntas** — isso duplicava o total quando a coluna `BR` apareceu pela primeira vez. Em vez disso: **se `BR` existir**, o script calcula os dois valores (soma das UFs e `BR`) a cada ano e usa o **maior** dos dois — segurança para o caso de um dia divergirem de verdade; se a diferença entre os dois passar de 0,5%, é impresso um aviso (na prática, a diferença observada é sempre < 0,1%, provavelmente arredondamento interno do modelo Waste). **Se `BR` não existir**, soma as colunas de UF normalmente (comportamento de sempre).
- Resultado intermediário gravado em `MACRO input/_Waste_convertido`.

### Etapa 3 — soma as três fontes

Combina EP + Waste + Transport_Agriculture (este último já vem pronto no formato MACRO — os arquivos `demand_[ano].csv`, `demand_LF_[ano].csv`, `elec_demand_[ano].csv`, `h2_demand_[ano].csv` e um `CO2e*.csv`, procurados dentro de `ta_dir` recursivamente, soltos ou dentro de uma subpasta). O `h2_demand` do transp-agric já vem em MWh — ao contrário do H2 do EP, não passa por nenhuma conversão de unidade na Etapa 3, só é somado.

- **Demandas**: alinhamento das linhas pelo `Time_Index` (não pela posição) e das colunas pelo nome (a ordem difere entre modelos). Coluna presente em só uma fonte é reportada no relatório final e preenchida com zero nas demais (controlado por `PREENCHER_FALTANTES_COM_ZERO`) — isso é sobre colunas dentro de um arquivo que existe nas duas fontes. Já quando uma fonte inteira não tem o arquivo (nem `demand_[ano].csv`, nem `elec_demand_[ano].csv` etc.), o padrão (`EXIGIR_TODAS_FONTES = True`) é **não gerar** o arquivo final daquele ano/tipo — só um aviso, nada é escrito em `MACRO input/` — em vez de somar só o que existe (ver Configuração e Erros e avisos). A mesma regra vale para o `CO2_Emissions.csv` final: se EP, Waste ou transp-agric não tiverem contribuído com nenhum arquivo de CO2, o arquivo final não é gerado.
  - `elec_demand_[ano].csv` = EP + transp-agric **−** Waste (Waste é subtraído).
  - `demand_[ano].csv`, `demand_LF_[ano].csv`, `h2_demand_[ano].csv` = EP + transp-agric (Waste não gera essas colunas).
- **CO2** (`CO2_Emissions.csv`, colunas `Year` e `CO2_Total`): soma todas as colunas do `CO2_Emissions.csv` intermediário do EP, o `CO2_Waste` do intermediário do Waste, e a linha `Total (Transp + Agri)` (transposta) do arquivo `CO2e*.csv` do transp-agric (ex. `CO2e.csv`); o total é dividido por 8760. (Nota: esta seção mencionava antes `ExternalEmissions2Macro_FirewoodDemand2Magpie.csv` — nome que não corresponde ao que o código de fato procura, `TA_EMISSOES_PREFIXO = 'co2e'`; corrigido aqui para bater com o comportamento real.)

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
- `UNIDADE_MASSA_H2` — `'kg'`, `'t'` ou `'kt'`. **Fallback**, usado só quando a unidade não pôde ser descoberta automaticamente em `EXO_DEMAND_METADATA.csv` (ver Etapa 1 / Hydrogen). Mesmo com a detecção automática, vale conferir esta constante — se um dia os metadados não estiverem disponíveis, é ela quem decide, e errar desloca o resultado em três ordens de grandeza.
- `UNIDADES_MASSA_METADADOS` — mapa de string de unidade (como aparece em `EXO_DEMAND_METADATA.csv`, ex. `'tonne'`) para o vocabulário do script (`'kg'`/`'t'`/`'kt'`). Ampliar aqui se o EP passar a usar outra grafia (ex. `'ton'`, `'kilograms'`).
- `PCS_H2_MJ_POR_KG = 141.8` — poder calorífico superior do H2, usado na conversão massa→MWh.
- `PREFIXO_H2 = 'h2_BR_'` — prefixo das colunas de UF no `h2_demand_[ano].csv`. **Precisa ser idêntico** ao usado pelo modelo transporte-agricultura, senão a Etapa 3 cria colunas duplicadas em vez de somar (o desvio aparece no relatório de colunas ao final da execução).
- `PREENCHER_FALTANTES_COM_ZERO` — `True` preenche colunas ausentes em um modelo com zero (quando o arquivo existe nas duas fontes, mas uma coluna só existe numa delas); `False` interrompe a execução (`ValueError`) quando há divergência de colunas entre fontes. Em ambos os casos a diferença é reportada em stdout.
- `EXIGIR_TODAS_FONTES` — `True` (padrão) cancela a geração do arquivo final (demanda ou CO2) daquele ano/tipo quando uma fonte inteira não tem o arquivo correspondente (nem direto, nem numa subpasta) — só avisa e não escreve nada, em vez de somar só o que existe. `False` volta ao comportamento antigo (soma só o que existe, reporta a ausência). É a proteção direta contra o que aconteceu no case do cenário 02 (elec_demand negativo por fonte ausente).
- `IGNORAR` — energéticos do EP descartados de propósito (sem fator de CO2 e sem coluna de demanda).
- `FATORES_CO2_TEP` — dicionário de fatores de emissão (tCO2e/tep) por energético; convertido internamente para tCO2e/MWh via `MWH_POR_TEP = 11.63`. Adicionar um novo energético à conta de CO2 significa adicionar uma entrada aqui **e** garantir que exista o arquivo `[Energetico]_[cenario].csv` correspondente em `EP output`.
- `TA_EMISSOES_CSV` / `TA_EMISSOES_LINHA` — nome do arquivo e rótulo da linha usados para extrair o total de emissões do modelo transporte-agricultura.

## Convenção de nomes de arquivo (EP)

O casamento de arquivos do EP por prefixo é sensível à ordem de verificação: tokens mais longos são testados antes dos mais curtos (ex. `JetFuel_SAF` antes de `JetFuel`; `Steam_Coal_3100` antes de `Coal`), para evitar que um nome mais específico seja capturado pelo token errado. Ao adicionar um novo energético cujo nome é prefixo de outro já cadastrado, revisar `tokens_demanda_norm` e `chaves_co2_norm` (ordenação por tamanho do nome normalizado, decrescente).

## Erros e avisos

O script imprime avisos (`Aviso: ...`) e segue a execução quando: um arquivo não corresponde a nenhuma coluna esperada; não é encontrado um arquivo de hidrogênio, de eletricidade do EP (nem em `in_dir` nem em `IN_DIR_ELETRICIDADE_EXTRA`), de Waste, ou de emissões do transp-agric; falta um ano em algum arquivo (nesse caso os valores daquele ano ficam em zero); o mesmo ano de eletricidade do EP aparece em `in_dir` e em `IN_DIR_ELETRICIDADE_EXTRA` (prevalece esta última). Fora do padrão `Aviso: ...`, também é impressa uma linha informativa quando a coluna `BR` é encontrada num arquivo do Waste (ver Etapa 2).

**Avisos da detecção automática de unidade do hidrogênio** (ver Etapa 1): `EXO_DEMAND_METADATA.csv` não encontrado; o arquivo não tem as colunas `file_name`/`unit` esperadas; o nome do arquivo de hidrogênio não é encontrado na coluna `file_name`; há mais de uma unidade cadastrada para o mesmo arquivo; ou a unidade encontrada não está em `UNIDADES_MASSA_METADADOS`. Em qualquer um desses casos o script cai para a unidade configurada manualmente em `UNIDADE_MASSA_H2` e avisa que não foi possível conferir automaticamente — vale revisar o log nesse caso, já que é a configuração de maior risco (ver "Pontos de atenção"). Quando a unidade é detectada mas diverge da configurada em `UNIDADE_MASSA_H2`, o script avisa e usa a detectada (prevalece o metadado sobre a configuração manual).

**Avisos de arquivo final não gerado (`EXIGIR_TODAS_FONTES = True`, padrão)** — ver Etapa 3: se, na hora de somar `demand_[ano].csv`, `demand_LF_[ano].csv`, `elec_demand_[ano].csv` ou `h2_demand_[ano].csv`, faltar o arquivo de **qualquer uma** das fontes esperadas (EP e/ou transp-agric, conforme o arquivo), o script avisa `"... arquivo final NÃO gerado (EXIGIR_TODAS_FONTES=True)"` e **não escreve** aquele arquivo em `out_dir` (em vez de gerar um resultado parcial, como o caso do cenário 02 em que só o Waste entrava na conta). O mesmo vale para `CO2_Emissions.csv`: se faltar o EP (nem soma direta nem por fator), o Waste ou o transp-agric, o arquivo final de CO2 não é gerado. Se `EXIGIR_TODAS_FONTES = False`, o comportamento antigo é mantido (soma o que existir, tratando a fonte ausente como zero, e apenas registra no relatório de colunas).

**Aviso de valores negativos nos arquivos finais** — depois de escrever os arquivos finais (quando `EXIGIR_TODAS_FONTES = True` isso normalmente não deve mais acontecer, mas serve de segunda camada de defesa, inclusive se a flag for desligada), o script relê `demand_[ano].csv`, `demand_LF_[ano].csv`, `elec_demand_[ano].csv` e `h2_demand_[ano].csv` de `out_dir` e avisa, por arquivo, quais colunas têm valor negativo e qual o mínimo encontrado — sem apagar ou corrigir o arquivo, só como alerta (geralmente sinal de fonte ausente com o Waste subtraindo mais do que EP + transp-agric somam).

O script interrompe a execução com `ValueError` quando: há mais de um arquivo de hidrogênio em `EP output`; há mais de um arquivo `electricity_[ano]_*.csv` para o mesmo ano encontrado por `encontrar_arquivo` numa mesma pasta (mesmo ano em `in_dir` e em `IN_DIR_ELETRICIDADE_EXTRA` **não** é erro — só um aviso, e prevalece o de `IN_DIR_ELETRICIDADE_EXTRA`); o `Time_Index` diverge entre fontes num mesmo arquivo a somar; há mais de um arquivo `co2e*.csv` em `ta_dir`; a linha de total não é encontrada no `CO2e*.csv`; ou há colunas divergentes entre fontes com `PREENCHER_FALTANTES_COM_ZERO = False`.

Ao final, é impresso um relatório consolidado de todas as diferenças de colunas encontradas na Etapa 3 (arquivos com fonte ausente, colunas exclusivas de uma fonte, e agora também os avisos de "arquivo final NÃO gerado").

## Pontos de atenção para integração na plataforma do NZB

- O script não tem argumentos de CLI nem variáveis de ambiente — para rodar como job parametrizável, os caminhos de pasta (`in_dir`, `waste_dir`, `ta_dir`, `out_dir`) e `UNIDADE_MASSA_H2` são os candidatos naturais a virar parâmetros externos.
- **Histórico**: numa rodada real na plataforma (case aplicado do cenário 02), `elec_demand` do EP e do transp-agric não estavam sendo lidos (ficando a demanda final baseada só no Waste, subtraído — resultado negativo), porque (1) o EP grava `electricity_[ano]_*.csv` fora de `in_dir`/`EXO_DEMAND`, numa pasta irmã `ShapeData/final_energy`; e (2) os arquivos do transp-agric usados naquela rodada não incluíam `elec_demand_*`/`h2_demand_*`/`CO2e*` na pasta apontada por `ta_dir` (só `demand_*`/`demand_LF_*`). O primeiro ponto foi corrigido com `IN_DIR_ELETRICIDADE_EXTRA` (pesquisa recursiva numa pasta irmã derivada de `in_dir`); o segundo, tornando a busca em `ta_dir` recursiva e tolerante (`encontrar_arquivo`), para que os quatro arquivos de demanda e o `CO2e*.csv` sejam achados mesmo dentro de uma subpasta — mas **`ta_dir` continua precisando apontar para uma pasta que realmente contenha esses arquivos**; nenhuma busca resolve um arquivo que não foi gerado/copiado para lá. Também foi corrigido um caso em que `SAIDA_WASTE_GEE*.csv` passou a trazer uma coluna `BR` (total nacional) além das UFs, o que duplicava a emissão do Waste na conta final de CO2.
- Não há validação de schema nas leituras de CSV além do que está descrito acima — arquivos com colunas ou nomes fora do esperado geram avisos silenciosos ("deixado de lado") em vez de erro; se a plataforma precisa garantir que nenhum arquivo de entrada seja ignorado por engano, vale capturar e tratar essas mensagens de aviso como sinal de falha.
- A leitura de CSV usa `encoding='utf-8-sig'` em todos os arquivos (por causa do BOM nos arquivos do transp-agric); arquivos de outras origens com encoding diferente vão falhar ou ler incorretamente.
- O script sobrescreve arquivos de saída existentes sem confirmação (`to_csv` padrão) — não há checagem de idempotência ou versionamento de execução.
- `UNIDADE_MASSA_H2` era a configuração de maior risco (um erro nela não gerava exceção, só um resultado de hidrogênio errado por 1000x ou 1.000.000x). Isso foi mitigado com a detecção automática a partir de `EXO_DEMAND_METADATA.csv` (coluna `file_name` = nome do arquivo de hidrogênio, coluna `unit` = unidade): quando a detecção funciona, ela prevalece sobre `UNIDADE_MASSA_H2` e avisa se as duas divergem; `UNIDADE_MASSA_H2` continua existindo só como *fallback* para quando o metadado não puder ser lido/entendido — nesse caso o risco antigo volta a existir e vale conferir o aviso no log.
- **Histórico (segunda rodada de ajustes)**: além das correções acima, foram adicionadas três camadas de segurança pedidas por Rachel: (1) detecção automática da unidade do hidrogênio via `EXO_DEMAND_METADATA.csv`, para não depender só de `UNIDADE_MASSA_H2` configurado manualmente; (2) `EXIGIR_TODAS_FONTES`, que bloqueia a geração dos arquivos finais de demanda e de `CO2_Emissions.csv` quando falta o arquivo de alguma fonte esperada, em vez de gerar um resultado parcial/errado (era exatamente o que causava a demanda negativa do cenário 02); (3) uma checagem final que relê os arquivos de demanda já gravados e avisa se algum valor ficou negativo, como segunda camada de defesa.
