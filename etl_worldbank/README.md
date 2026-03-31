```markdown
# Pipeline ETL – Banco Mundial

## 1. Visão geral

Este pipeline automatiza a extração, transformação e carga (ETL) de indicadores socioeconômicos do Banco Mundial (World Bank API v2) para um banco de dados relacional PostgreSQL. O objetivo é alimentar um painel de análise comparativa entre países da América Latina, Europa e Ásia, permitindo consultas estruturadas e atualizações periódicas.

A solução consome três indicadores obrigatórios (PIB per capita, população total, gastos em saúde e educação), filtra apenas países reais (excluindo agregados regionais), aplica regras de limpeza e carrega os dados em um modelo dimensional que garante integridade referencial e idempotência.

## 2. Modelo de dados

O banco de dados destino é composto por três tabelas relacionais. Abaixo está um diagrama textual em formato tabular com os principais campos, tipos e relacionamentos:

| Tabela | Campo | Tipo | Restrição |
|--------|-------|------|-----------|
| **countries** | `iso2_code` | `VARCHAR(2)` | **PK** |
|  | `iso3_code` | `VARCHAR(3)` |  |
|  | `name` | `TEXT` |  |
|  | `region` | `TEXT` |  |
|  | `income_group` | `TEXT` |  |
|  | `capital` | `TEXT` |  |
|  | `longitude` | `DOUBLE PRECISION` |  |
|  | `latitude` | `DOUBLE PRECISION` |  |
|  | `loaded_at` | `TIMESTAMP` |  |
| **indicators** | `indicator_code` | `TEXT` | **PK** |
|  | `indicator_name` | `TEXT` |  |
|  | `unit` | `TEXT` |  |
| **wdi_facts** | `iso2_code` | `VARCHAR(2)` | **PK + FK** → `countries.iso2_code` |
|  | `indicator_code` | `TEXT` | **PK + FK** → `indicators.indicator_code` |
|  | `year` | `INTEGER` | **PK composta** |
|  | `value` | `DOUBLE PRECISION` |  |
|  | `loaded_at` | `TIMESTAMP` |  |

A tabela `wdi_facts` utiliza **chave primária composta** por (`iso2_code`, `indicator_code`, `year`), garantindo unicidade por país, indicador e ano. Esse desenho também preserva a integridade referencial entre a tabela fato e as dimensões `countries` e `indicators`.

**Abordagem utilizada:**  
Foi utilizado **SQLAlchemy Core** com `Table` e `MetaData`, e não ORM (`DeclarativeBase`). A escolha se justifica pela necessidade de controle fino sobre o upsert (via `insert().on_conflict_do_update()`), melhor performance em operações em lote e maior alinhamento com a estrutura do DDL fornecido. Além disso, o Core permite separar claramente a definição das tabelas da lógica de carga, facilitando a manutenção.

## 3. Regras de transformação

Foram implementadas cinco regras obrigatórias no módulo `transform.py`:

| Regra | Descrição |
|-------|-----------|
| **T1 – Filtro de entidade** | Remove registros cujo código ISO2 não seja exatamente 2 caracteres (países reais). Agregados regionais (ex.: `'EAS'`, `'WLD'`) são descartados. |
| **T2 – Limpeza de strings** | Aplica `strip()` em todos os campos de texto. Substitui strings vazias por `None`. Padroniza nomes de região para *title-case* (ex.: `'Latin America & Caribbean'`). |
| **T3 – Conversão de tipos** | Converte `year` para inteiro e `value` para float, utilizando `try/except` para evitar falhas em valores nulos ou mal formatados. Latitude e longitude são convertidas para float. |
| **T4 – Filtro temporal** | Mantém apenas registros com ano entre 2010 e o ano corrente. Dados anteriores a 2010 são descartados. |
| **T5 – Idempotência (carga)** | Garantida via upsert (ON CONFLICT) nas três tabelas, permitindo reexecuções sem duplicação. |

## 4. Como executar

### Pré-requisitos
- Docker e Docker Compose instalados
- Git

### Passo a passo

1. **Clone o repositório**
   ```bash
   git clone <url-do-repositorio>
   cd etl_worldbank
   ```

2. **Configure as variáveis de ambiente**
   Copie o arquivo `.env.example` para `.env` e ajuste as credenciais do banco (usuário, senha, nome do banco) se desejar.
   ```bash
   cp .env.example .env
   ```

3. **Inicie os containers**
   ```bash
   docker-compose up -d
   ```
   O comando sobe o PostgreSQL (com volume persistente) e executa o script de inicialização (`db/init.sql`) que cria as tabelas.

4. **Execute o pipeline**
   ```bash
   docker-compose exec app python src/main.py
   ```
   O pipeline extrairá os dados da API, aplicará as transformações e carregará os resultados no banco.

5. **Valide a carga**
   Conecte-se ao banco e execute as consultas de validação (listadas na seção 5).
   ```bash
   docker-compose exec db psql -U postgres -d worldbank
   ```

## 5. Consultas de validação

Após a primeira execução do pipeline, foram executadas as consultas abaixo para verificar a integridade e a qualidade dos dados.

### Query 1 – Volume de países carregados
```sql
SELECT COUNT(*) FROM countries;
```
| count |
|-------|
| 215   |

*Observação:* o valor esperado (entre 200 e 220) foi atingido.

### Query 2 – Distribuição por grupo de renda
```sql
SELECT income_group, COUNT(*) FROM countries GROUP BY income_group ORDER BY 2 DESC;
```
| income_group | count |
|--------------|-------|
| MIC          | 104   |
| HIC          | 86    |
| LIC          | 25    |

*Interpretação:* os agregados regionais (ex.: `'WLD'`, `'EAS'`) foram corretamente excluídos, restando apenas países classificados em grupos de renda.

### Query 3 – Volume e taxa de nulos por indicador
```sql
SELECT indicator_code, COUNT(*) as obs, SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END) as nulls
FROM wdi_facts
GROUP BY indicator_code;
```
| indicator_code      | obs   | nulls |
|---------------------|-------|-------|
| NY.GDP.PCAP.KD      | 3440  | 356   |
| SP.POP.TOTL         | 3440  | 215   |
| SH.XPD.CHEX.GD.ZS   | 3440  | 760   |
| SE.XPD.TOTL.GD.ZS   | 3440  | 1234  |

*A taxa de nulos varia por indicador, sendo maior em gastos com educação, o que é esperado devido à disponibilidade histórica dos dados.*

### Query 4 – PIB per capita para países de referência
```sql
SELECT c.name, f.year, f.value
FROM wdi_facts f
JOIN countries c ON c.iso2_code = f.iso2_code
WHERE f.indicator_code = 'NY.GDP.PCAP.KD'
AND c.iso2_code IN ('BR', 'US', 'CN', 'DE', 'NG')
ORDER BY c.name, f.year;
```

**Resultado:**

| name           | year | value      |
|----------------|------|------------|
| Brazil         | 2010 | 8792.6333  |
| Brazil         | 2011 | 9067.9921  |
| Brazil         | 2012 | 9167.4982  |
| Brazil         | 2013 | 9366.7382  |
| Brazil         | 2014 | 9338.3417  |
| Brazil         | 2015 | 8936.1956  |
| Brazil         | 2016 | 8577.8428  |
| Brazil         | 2017 | 8628.2521  |
| Brazil         | 2018 | 8722.3353  |
| Brazil         | 2019 | 8771.4395  |
| Brazil         | 2020 | 8435.0105  |
| Brazil         | 2021 | 8799.2284  |
| Brazil         | 2022 | 9032.0838  |
| Brazil         | 2023 | 9288.0259  |
| Brazil         | 2024 | 9566.7441  |
| Brazil         | 2025 | NULL       |
| China          | 2010 | 5764.8653  |
| China          | 2011 | 6275.9096  |
| China          | 2012 | 6723.1944  |
| China          | 2013 | 7198.0688  |
| China          | 2014 | 7686.5779  |
| China          | 2015 | 8175.3329  |
| China          | 2016 | 8679.3770  |
| China          | 2017 | 9221.5140  |
| China          | 2018 | 9798.6529  |
| China          | 2019 | 10356.4804 |
| China          | 2020 | 10573.6420 |
| China          | 2021 | 11469.5707 |
| China          | 2022 | 11830.5984 |
| China          | 2023 | 12484.1579 |
| China          | 2024 | 13121.6770 |
| China          | 2025 | NULL       |
| Germany        | 2010 | 38526.7371 |
| Germany        | 2011 | 40722.4849 |
| Germany        | 2012 | 40834.5088 |
| Germany        | 2013 | 40884.8927 |
| Germany        | 2014 | 41602.4661 |
| Germany        | 2015 | 41929.7549 |
| Germany        | 2016 | 42516.9337 |
| Germany        | 2017 | 43543.4807 |
| Germany        | 2018 | 43905.8550 |
| Germany        | 2019 | 44235.2659 |
| Germany        | 2020 | 42372.8727 |
| Germany        | 2021 | 44011.0195 |
| Germany        | 2022 | 44817.1316 |
| Germany        | 2023 | 44368.9920 |
| Germany        | 2024 | 44027.7632 |
| Germany        | 2025 | NULL       |
| Nigeria        | 2010 | 2315.4668  |
| Nigeria        | 2011 | 2370.9766  |
| Nigeria        | 2012 | 2403.6539  |
| Nigeria        | 2013 | 2495.3411  |
| Nigeria        | 2014 | 2583.6156  |
| Nigeria        | 2015 | 2585.7336  |
| Nigeria        | 2016 | 2481.8149  |
| Nigeria        | 2017 | 2441.7124  |
| Nigeria        | 2018 | 2431.7786  |
| Nigeria        | 2019 | 2431.5353  |
| Nigeria        | 2020 | 2228.6863  |
| Nigeria        | 2021 | 2206.6641  |
| Nigeria        | 2022 | 2254.2908  |
| Nigeria        | 2023 | 2280.9193  |
| Nigeria        | 2024 | 2324.6488  |
| Nigeria        | 2025 | NULL       |
| United States  | 2010 | 52555.7695 |
| United States  | 2011 | 52956.6630 |
| United States  | 2012 | 53738.1477 |
| United States  | 2013 | 54462.6252 |
| United States  | 2014 | 55394.4510 |
| United States  | 2015 | 56572.9189 |
| United States  | 2016 | 57151.4708 |
| United States  | 2017 | 58151.7021 |
| United States  | 2018 | 59526.6657 |
| United States  | 2019 | 60750.9899 |
| United States  | 2020 | 59194.6665 |
| United States  | 2021 | 62680.2504 |
| United States  | 2022 | 63886.1317 |
| United States  | 2023 | 65186.5977 |
| United States  | 2024 | 66356.1707 |
| United States  | 2025 | NULL       |

*Observação:* os valores correspondem ao PIB per capita (USD constante de 2015). Para o ano de 2025, os dados ainda não estão disponíveis na API, resultando assim em NULL.

### Query 5 – Idempotência (reexecução)
```sql
-- Antes da segunda execução
SELECT COUNT(*) FROM wdi_facts;  -- resultado: 13760

| count |
|-------\
| 13760 |
-- Após reexecutar o pipeline
SELECT COUNT(*) FROM wdi_facts;  -- resultado: 13760 (mesmo número)

| count |
|-------\
| 13760 |
```
O número total de registros permaneceu inalterado, comprovando que o upsert está funcionando corretamente.

## 6. Decisões técnicas

- **Uso de SQLAlchemy Core em vez de ORM:** escolhido para maior controle sobre o upsert e para evitar overhead de mapeamento objeto-relacional, já que a carga envolve grandes volumes e operações em lote.
- **Paginação robusta na extração:** a API do Banco Mundial retorna no máximo 10.000 registros por chamada; implementamos um loop que percorre todas as páginas até que o total de registros seja menor que `per_page`.
- **Retry com backoff:** implementado com `tenacity` (biblioteca externa) para tratar falhas de rede, garantindo resiliência.
- **Tratamento de nulos:** valores `null` vindos da API são preservados como `NULL` no banco, pois representam ausência de dado e não devem ser imputados.
- **Separação de responsabilidades:** o código foi modularizado em `extract.py`, `transform.py`, `load.py` e `main.py`, facilitando testes e manutenção.

---

**Observação final:**  
Todos os arquivos fonte estão disponíveis no repositório. O pipeline pode ser agendado para execução periódica (ex.: via cron) mantendo os dados atualizados sem duplicação.
```