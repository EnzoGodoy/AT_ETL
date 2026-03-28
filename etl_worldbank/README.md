# Pipeline ETL – Banco Mundial

## Visão Geral
Este pipeline extrai dados socioeconômicos da API pública do Banco Mundial (World Bank Data API v2), transforma‑os conforme regras de qualidade e carrega‑os em um banco PostgreSQL. O objetivo é disponibilizar um painel de indicadores (PIB per capita, população, gastos em saúde e educação) para análises comparativas entre países.

## Modelo de Dados
O esquema relacional é composto por três tabelas:

| Tabela       | Descrição                                  | Chaves / Relacionamentos                              |
|--------------|--------------------------------------------|-------------------------------------------------------|
| `countries`  | Dimensão de países                         | PK: `iso2_code`                                       |
| `indicators` | Dimensão de indicadores                    | PK: `indicator_code`                                  |
| `wdi_facts`  | Fatos – séries históricas                  | PK composta: `iso2_code`, `indicator_code`, `year`    |
|              |                                            | FK: `iso2_code` → `countries`                         |
|              |                                            | FK: `indicator_code` → `indicators`                   |

**Abordagem de mapeamento:** Foi utilizado **SQLAlchemy Core** (`Table` + `MetaData`), pois oferece controle explícito sobre os comandos SQL, facilita a implementação de `upsert` via `on_conflict_do_update` e evita overhead desnecessário de ORM, mantendo a performance em cargas em lote.

## Regras de Transformação
1. **T1 – Filtro de entidade**  
   - Países: mantém apenas registros com `iso2_code` de 2 caracteres e `income_group` em {LIC, MIC, HIC}.  
   - Indicadores: utiliza apenas os países válidos obtidos na etapa anterior.

2. **T2 – Limpeza de strings**  
   - Aplica `strip()` em todos os campos de texto.  
   - Substitui strings vazias por `None`.  
   - Padroniza nomes de região para *title case* (ex.: "Latin America & Caribbean").

3. **T3 – Conversão de tipos**  
   - `year` → inteiro; valores inválidos são descartados.  
   - `value` (numérico) → `float`; `None` em caso de erro.  
   - `latitude` e `longitude` → `float`; `None` se ausentes ou inválidas.

4. **T4 – Filtro temporal**  
   - Mantém apenas registros com `year` entre 2010 e o ano corrente.

5. **T5 – (implícita) Idempotência**  
   - A carga utiliza `ON CONFLICT DO UPDATE`, garantindo que execuções repetidas não criem duplicatas e atualizem os dados mais recentes.

## Como Executar
1. **Clone o repositório**  
   ```bash
   git clone <url>
   cd etl_worldbank