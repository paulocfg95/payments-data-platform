# Projeto: payments-data-platform

Contexto para o assistente de código. O dono do projeto é Paulo Guedes, Engenheiro de Dados Júnior em Manaus. O projeto é de portfólio no GitHub e tem um objetivo claro: provar na prática os requisitos de vagas de engenharia de dados júnior, em especial a da Efí (banco digital de pagamentos).

Este arquivo de contexto está em português para o dono do projeto. **Tudo o que for produzido no repositório segue as regras de idioma abaixo.**

## Idioma

| Parte | Idioma |
|---|---|
| Código, nomes de arquivos, funções, variáveis, DAGs e testes | Inglês |
| Tabelas, colunas e modelos do dbt | Inglês, em snake_case |
| Descrições de tabelas e colunas no dbt (catálogo) | Inglês |
| Mensagens de commit, nomes de branch e pull requests | Inglês |
| Comentários e docstrings | Inglês |
| README | Inglês, com um resumo curto em português no início |

Regras:

- **Inglês simples e direto.** Frases curtas, vocabulário técnico comum. O dono do projeto tem inglês intermediário e precisa conseguir explicar tudo numa entrevista com as mesmas palavras.
- **Consistência acima de tudo.** Nunca misturar português e inglês em nomes de tabelas, colunas ou funções.
- Valores categóricos dos dados também em inglês (por exemplo, `approved`, `declined`), exceto termos próprios do Brasil, como `pix` e `boleto`.

## Objetivo

Construir uma plataforma de dados pequena, mas completa, que:

1. Coleta dados públicos do Banco Central e transações de pagamento sintéticas.
2. Guarda o dado bruto num armazenamento de objetos (camada bronze).
3. Carrega os dados num PostgreSQL que faz o papel de data warehouse.
4. Transforma os dados com dbt num **modelo dimensional (star schema)**.
5. Testa código e dados automaticamente, com CI/CD no GitHub Actions.
6. Gera catálogo e linhagem dos dados com `dbt docs`.
7. É orquestrada pelo Apache Airflow, com cargas idempotentes.

## Requisitos da vaga que o projeto precisa cobrir

| Requisito | Onde aparece |
|---|---|
| Python e SQL | Extração e geração em Python; transformações em SQL no dbt |
| Orquestração | DAGs no Airflow, com retries, agendamento diário e backfill funcionando |
| Nuvem | Camada bronze no Amazon S3 (com MinIO como alternativa local) |
| Modelagem dimensional | Star schema com granularidade declarada |
| Data warehouse, ETL/ELT | PostgreSQL como warehouse; carga bruta primeiro, transformação depois (ELT) |
| DataOps e CI/CD | GitHub Actions rodando lint, pytest e `dbt build` a cada pull request |
| Git e GitFlow | Branches main, develop, feature/*, release/*, hotfix/* |
| Documentação | README completo e docstrings |
| Governança e catalogação | `dbt docs` com descrições de tabelas e colunas e linhagem |
| Segmento financeiro (diferencial) | Tema de pagamentos e dados do Banco Central |
| LGPD (ponto forte do candidato) | Pseudonimização de dados pessoais sintéticos (CPF e e-mail) na camada silver |

Toda decisão de implementação deve favorecer o que mostra esses requisitos de forma clara para um recrutador técnico. Simples e bem feito vale mais que grande e incompleto.

## Regras importantes

- **Dados sintéticos sempre identificados.** Clientes e transações gerados com Faker são fictícios. Dizer isso no README e nas descrições do dbt. Nunca usar dados reais de pessoas.
- **Nenhuma credencial no repositório.** Chaves da AWS, senhas e strings de conexão só em variáveis de ambiente ou num `.env` que está no `.gitignore`. Fornecer um `.env.example` sem valores reais.
- **Custo da AWS.** Usar só o S3 na camada gratuita. Antes de criar qualquer recurso, lembrar o dono de configurar um alerta de cobrança. Não criar Redshift, Glue, EMR nem outros serviços pagos sem pedido explícito.
- **Tudo roda localmente com um comando.** `docker compose up` sobe o ambiente inteiro. O S3 é opcional: com uma variável de ambiente, a camada bronze usa MinIO local.

## Fontes de dados

### 1. Banco Central do Brasil (dados reais)

- API de séries temporais do SGS, em formato JSON, para indicadores diários. Sugestão de séries: taxa Selic, CDI e dólar (PTAX). **Confirmar os códigos e o formato da URL na documentação oficial antes de implementar.**
- Opcional: estatísticas do Pix no portal de dados abertos do Banco Central (API Olinda). **Verificar quais conjuntos estão disponíveis e com que granularidade antes de implementar.**
- Tratar falhas: timeout, retentativas com espera crescente, validação do esquema da resposta e registro em log.

### 2. Transações sintéticas (Faker)

- Um gerador em Python cria, para cada dia de execução, um lote de transações de pagamento ligadas a um cadastro fixo de clientes.
- O gerador deve ser **determinístico por data** (semente derivada da data lógica do Airflow), para que reexecutar o mesmo dia gere os mesmos dados. Isso sustenta a idempotência.
- Campos da transação: `transaction_id`, `customer_cpf`, `transaction_at`, `payment_type` (`pix`, `boleto`, `credit_card`, `debit_card`), `channel` (`app`, `web`, `pos`), `amount`, `fee`, `status` (`approved`, `declined`, `refunded`).
- Campos do cliente: `cpf`, `name`, `email`, `state`, `city`, `created_at`, `segment` (`individual`, `business`).
- Incluir alguns problemas de qualidade de propósito, em baixa proporção (valores nulos, duplicados), para os testes de dados terem o que pegar e a camada silver tratar.

## Arquitetura

```
Banco Central (API) ─┐
                     ├─> Airflow ─> bronze (S3 ou MinIO, JSON/Parquet particionado por data)
Gerador Faker ───────┘                │
                                      v
                          PostgreSQL schema raw (carga por dia, idempotente)
                                      │
                                      v
                          dbt: staging (silver) ─> marts (gold, star schema)
                                      │
                                      v
                          dbt test + dbt docs (catálogo e linhagem)
```

### Camadas

- **bronze:** dado bruto como veio, no armazenamento de objetos, particionado por data: `bronze/<source>/dt=YYYY-MM-DD/<file>`.
- **raw (PostgreSQL):** cópia fiel do bronze em tabelas, para o dbt ler.
- **silver (dbt staging, modelos `stg_*`):** limpeza, tipagem, deduplicação, padronização de nomes e **pseudonimização** (CPF e e-mail viram hash com sal guardado em variável de ambiente; o nome do cliente não segue para as camadas seguintes).
- **gold (dbt marts):** star schema pronto para análise.

## Modelo dimensional (gold)

Granularidade da fato principal: **uma linha por transação**.

- `fact_transactions`: `customer_sk`, `date_sk`, `payment_type_sk`, `channel_sk`, `transaction_id`, `amount`, `fee`, `status`, `is_approved`.
- `dim_customer`: `customer_sk`, `customer_hash`, `state`, `city`, `segment`, `created_at`. Opcional, como evolução: SCD tipo 2 com `valid_from`, `valid_to` e `is_current`.
- `dim_date`: `date_sk`, `date`, `day`, `month`, `year`, `quarter`, `day_of_week`, `is_weekend`, `is_holiday` (opcional).
- `dim_payment_type`: `payment_type_sk`, `payment_type`, `description`.
- `dim_channel`: `channel_sk`, `channel`, `description`.
- `fact_daily_indicators`: `date_sk`, `selic_rate`, `cdi_rate`, `usd_brl_ptax`. Granularidade: uma linha por dia.

Opcional: um mart agregado (`agg_daily_payments`) com total transacionado, quantidade e taxa de aprovação por dia, tipo de pagamento e canal, cruzado com os indicadores do Banco Central.

Chaves substitutas geradas no dbt (por exemplo, com `dbt_utils.generate_surrogate_key`). Descrever cada tabela e coluna no `schema.yml`, em inglês.

## Orquestração (Airflow)

- DAGs sugeridas: `ingest_bcb`, `generate_transactions`, `transform_dbt`. Pode ser uma DAG só com grupos de tarefas, se ficar mais claro.
- Agendamento diário. Usar a **data lógica** da execução em caminhos, sementes e filtros, nunca a data atual do relógio.
- **Idempotência:** reexecutar um dia substitui os dados daquele dia, sem duplicar. No bronze, sobrescrever a partição do dia. No raw, apagar e inserir o dia (ou MERGE, disponível no PostgreSQL 15 ou superior). No dbt, modelos incrementais com `unique_key`.
- Retries com espera, timeouts e logs claros. Backfill de alguns dias deve funcionar.
- A transformação dbt roda depois das cargas, como tarefa dependente.

## Qualidade de dados e testes

- **dbt tests:** `unique` e `not_null` nas chaves, `relationships` entre fato e dimensões, `accepted_values` em `payment_type`, `channel` e `status`, e um teste de valor positivo em `amount`.
- **pytest:** testes do cliente da API (com respostas simuladas), do gerador (determinismo por data, esquema dos campos) e das funções de carga.
- **Checagem de contagem:** comparar o número de linhas entre bronze, raw e silver de um mesmo dia.

## CI/CD (GitHub Actions)

A cada pull request para develop ou main:

1. Lint do Python (ruff) e, se possível, do SQL (sqlfluff).
2. `pytest`.
3. `dbt build` contra um PostgreSQL de serviço no próprio workflow, com dados de exemplo pequenos.

O merge só acontece com a esteira verde. Opcional: gerar e publicar o `dbt docs` no GitHub Pages quando houver merge na main.

## GitFlow

- `main`: o que está pronto e estável.
- `develop`: integração.
- `feature/<name>`: cada etapa do projeto (por exemplo, `feature/bcb-ingestion`, `feature/star-schema`), com pull request para develop.
- `release/<version>` e `hotfix/<name>` quando fizer sentido.
- Commits pequenos e descritivos, em inglês, de preferência no padrão Conventional Commits (por exemplo, `feat: add bcb ingestion dag`, `test: add generator determinism test`). O histórico também é avaliado por recrutadores.

## Estrutura sugerida do repositório

```
payments-data-platform/
├── airflow/
│   └── dags/
├── src/
│   ├── extract/         # Banco Central API client
│   ├── generate/        # Faker transaction generator
│   └── load/            # bronze -> raw
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   └── marts/
│   └── tests/
├── tests/               # pytest
├── docs/                # architecture diagram and images
├── .github/workflows/
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

## Ordem de construção

1. **Fase 1:** Docker Compose com Airflow, PostgreSQL e MinIO. DAG que coleta uma série do Banco Central e grava no bronze. Testes do cliente da API.
2. **Fase 2:** gerador de transações, carga bronze para raw, projeto dbt com staging, star schema e testes de dados. Pseudonimização na silver.
3. **Fase 3:** GitHub Actions, opção de S3 no lugar do MinIO, `dbt docs`, README com diagrama e prints.

Ao fim de cada fase, o projeto deve estar funcionando e com o README atualizado, para poder ser mostrado mesmo incompleto.

## README (para recrutadores)

Em inglês, com um resumo de duas ou três frases em português no topo. Deve ter, nesta ordem:

1. O que o projeto faz, em duas ou três frases.
2. Diagrama da arquitetura.
3. Tecnologias usadas e por quê.
4. O modelo dimensional, com a granularidade explicada.
5. Como rodar localmente, passo a passo.
6. Decisões técnicas: idempotência, ELT, pseudonimização, testes e CI.
7. Aviso de que os dados de clientes e transações são sintéticos.
8. Próximos passos possíveis (por exemplo, SCD tipo 2, Spark, Databricks).

## O que evitar

- Complexidade sem motivo: Kubernetes, vários serviços de nuvem, streaming em tempo real.
- Notebooks como parte do pipeline; código em módulos Python testáveis.
- Dependências sem versão fixa no requirements.txt.
- Commits gigantes ou direto na main.
- Misturar português e inglês em nomes de código, tabelas ou colunas.

## Notas de implementação

- As imagens oficiais do MinIO não estão mais no Docker Hub nem no quay.io. Usamos `chainguard/minio` e `chainguard/minio-client`, fixadas por digest sha256. Essas imagens não têm shell.
- Airflow 3.3.2 (`apache/airflow:3.3.2-python3.12`). As dependências seguem o arquivo de constraints dessa versão.
- Gerador sintético: datas e escolhas usam `random.Random` com semente própria, não as funções de data do Faker, que consomem aleatoriedade de forma diferente entre plataformas (Windows/Python 3.14 x container Linux/Python 3.12). O teste golden em `tests/test_generator.py` protege isso.
- dbt: o salt da pseudonimização vai para o Postgres via `PGOPTIONS` (definido em `dbt/run_dbt.sh`) e é lido com `current_setting('app.pseudonymization_salt')`. Nunca colocar o salt em SQL, `env_var()` dentro de modelo ou no comando de tarefa do Airflow, porque apareceria no SQL compilado, no `dbt docs` ou na UI do Airflow.
- dbt roda num virtualenv separado na imagem (`/home/airflow/dbt-venv`). Para rodar à mão: `docker compose exec airflow-scheduler bash /opt/airflow/dbt/run_dbt.sh build`. No Git Bash do Windows, usar `MSYS_NO_PATHCONV=1` antes de comandos docker com caminhos absolutos do container.
- Schemas do dbt: `staging`, `marts` e `reference` (macro `generate_schema_name` sobrescrita). Descrições YAML com ": " no meio precisam de aspas.
