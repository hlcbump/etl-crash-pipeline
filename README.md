# ETL pipeline - Australian road crash data

Reads raw crash data from an Excel file (~6,900 rows in a single flat table), cleans it up and normalizes it into 6 relational tables, then loads everything into PostgreSQL with proper constraints. Orchestrated by Apache Airflow running in Docker.

## Architecture

```
Excel (.xlsx) → Extract → Parquet → Transform → 6 Parquets → Load → PostgreSQL
```

The pipeline runs as three Airflow tasks wired sequentially: `extract >> transform >> load`. Trigger is manual since the dataset is static, scheduling would be pointless.

## Data model

Source: 1 flat Excel table where each row is a person involved in a crash. Multiple rows share the same Crash ID when more than one person was involved.

Target: 6 normalized tables in PostgreSQL (3NF):

```
┌──────────────┐     ┌──────────────┐
│   genders    │     │  road_users  │
│──────────────│     │──────────────│
│ gen_id  PK   │     │ rdu_id  PK   │
│ gen_name     │     │ rdu_name     │
└──────┬───────┘     └──────┬───────┘
       │                    │
       │    ┌───────────────────────────┐
       │    │          persons          │
       └───>│───────────────────────────│
            │ per_id      PK            │
       ┌───>│ per_rdu_id  FK→road_users │
       │    │ per_gen_id  FK→genders    │
       │    │ per_cra_id  FK→crashes    │
       │    │ per_age                   │
       │    └───────────┬───────────────┘
       │                │
       │    ┌───────────────────────────────────┐
       │    │             crashes                │
       │    │───────────────────────────────────│
       │    │ cra_id          PK                │
       │    │ cra_are_id      FK→areas          │
       │    │ cra_rdt_id      FK→road_types     │
       │    │ cra_year        SMALLINT          │
       │    │ cra_month       SMALLINT          │
       │    │ cra_speed_limit SMALLINT (NULL ok)│
       │    │ cra_dayweek     VARCHAR           │
       │    └──────┬──────────────┬─────────────┘
       │           │              │
  ┌────────────┐   │    ┌─────────────────────────────────────────────┐
  │ road_types │<──┘    │                  areas                      │
  │────────────│        │─────────────────────────────────────────────│
  │ rdt_id  PK │        │ are_id                        PK            │
  │ rdt_name   │        │ are_state                     VARCHAR(3)    │
  └────────────┘        │ are_national_remoteness_areas  VARCHAR(30)  │
                        │ are_sa4_name_2016              VARCHAR(45)  │
                        │ are_national_lga_name_2017     VARCHAR(30)  │
                        └─────────────────────────────────────────────┘
```

| table | rows | type |
|---|---|---|
| genders | 2 | dimension |
| road_users | 7 | dimension |
| road_types | 9 | dimension |
| areas | 744 | dimension |
| crashes | 6,329 | fact |
| persons | 6,868 | fact |

## Tech stack

- Python 3.13
- Apache Airflow 3 (CeleryExecutor, Docker Compose)
- PostgreSQL 16
- Pandas, for transformation and normalization
- openpyxl, for Excel reading
- SQLAlchemy + psycopg2, for database connection
- Docker & Docker Compose
- uv, for package management

## Data quality

The raw dataset had a few issues that needed cleaning before normalization:

| problem | column | fix |
|---|---|---|
| mixed int and string values | Speed Limit | 'Unspecified' and '<40' become NULL, rest cast to int |
| inconsistent casing | National Road Type | normalized to title case ("ARTERIAL ROAD" → "Arterial Road") |


## Project structure

```
├── dags/
│   └── crash_dag.py              # airflow dag
├── src/
│   ├── extract_data.py           # reads xlsx, saves as parquet
│   ├── transform_data.py         # cleans data + normalizes into 6 dataframes
│   └── load_data.py              # creates tables in postgres + inserts data
├── config/
│   └── .env                      # db credentials
├── data/
│   └── Crash_Data.xlsx           # source dataset
├── main.py                       # standalone runner (no airflow needed)
├── docker-compose.yaml
└── pyproject.toml
```

## How to run

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-username/etl-pipeline-crash.git
cd etl-pipeline-crash
uv sync
```

### 2. Start containers

```bash
echo "AIRFLOW_UID=$(id -u)" > .env
docker compose up -d
```

### 3. Create the database

```bash
docker compose exec postgres psql -U airflow -c "CREATE DATABASE crash_data;"
```

### 4. Run via airflow

Open http://localhost:8080 (user: admin, password: admin), find the `crash_pipeline` DAG and trigger it manually.

### Run locally (without airflow)

```bash
uv run main.py
```

## What i learned

This was my second ETL project. The first one (weather pipeline) pulled data from an API into a single flat table. This one is a different problem: a messy Excel file that needed to become a normalized relational model with proper foreign keys.

The transform was the hard part. Breaking one flat table into 6 related ones means you have to get every foreign key lookup right, or the load blows up. The areas table was especially annoying because its unique key is a combination of 4 columns, not just one, so a simple dictionary lookup wouldn't cut it.

I also ran into the classic "works on my machine" issue with Docker. Inside the Airflow container, `localhost` means the container itself, not my machine. The database connection needed `postgres:5432` (the Docker service name) instead of `localhost:5434`. Took me a bit to figure out why the load kept refusing to connect.
