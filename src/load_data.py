import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv(Path(__file__).parent.parent / 'config' / '.env')

DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5434')

DATA_DIR = Path(__file__).parent.parent / 'data'

DDL = """
CREATE TABLE IF NOT EXISTS genders (
    gen_id   SMALLINT    PRIMARY KEY,
    gen_name VARCHAR(15) NOT NULL
);

CREATE TABLE IF NOT EXISTS road_users (
    rdu_id   SMALLINT    PRIMARY KEY,
    rdu_name VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS road_types (
    rdt_id   SMALLINT    PRIMARY KEY,
    rdt_name VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS areas (
    are_id                        INTEGER     PRIMARY KEY,
    are_state                     VARCHAR(3)  NOT NULL,
    are_national_remoteness_areas VARCHAR(30),
    are_sa4_name_2016             VARCHAR(45),
    are_national_lga_name_2017    VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS crashes (
    cra_id          INTEGER     PRIMARY KEY,
    cra_are_id      INTEGER     NOT NULL REFERENCES areas(are_id),
    cra_rdt_id      SMALLINT    NOT NULL REFERENCES road_types(rdt_id),
    cra_year        SMALLINT    NOT NULL,
    cra_month       SMALLINT    NOT NULL,
    cra_speed_limit SMALLINT,
    cra_dayweek     VARCHAR(12) NOT NULL
);

CREATE TABLE IF NOT EXISTS persons (
    per_id     INTEGER  PRIMARY KEY,
    per_rdu_id SMALLINT NOT NULL REFERENCES road_users(rdu_id),
    per_gen_id SMALLINT NOT NULL REFERENCES genders(gen_id),
    per_cra_id INTEGER  NOT NULL REFERENCES crashes(cra_id),
    per_age    SMALLINT NOT NULL
);
"""

LOAD_ORDER = ['genders', 'road_users', 'road_types', 'areas', 'crashes', 'persons']

VERIFY_QUERY = """
SELECT 'genders' as tabela, count(*) as registros FROM genders
UNION ALL SELECT 'road_users', count(*) FROM road_users
UNION ALL SELECT 'road_types', count(*) FROM road_types
UNION ALL SELECT 'areas', count(*) FROM areas
UNION ALL SELECT 'crashes', count(*) FROM crashes
UNION ALL SELECT 'persons', count(*) FROM persons;
"""

JOIN_QUERY = """
SELECT p.per_id, g.gen_name, r.rdu_name, c.cra_year, c.cra_month,
       rt.rdt_name, a.are_state
FROM persons p
JOIN genders g    ON p.per_gen_id = g.gen_id
JOIN road_users r ON p.per_rdu_id = r.rdu_id
JOIN crashes c    ON p.per_cra_id = c.cra_id
JOIN road_types rt ON c.cra_rdt_id = rt.rdt_id
JOIN areas a      ON c.cra_are_id = a.are_id
LIMIT 10;
"""


# cria a engine de conexao com o postgres
def get_engine():
    url = f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    return create_engine(url)


# cria as 6 tabelas com ddl explicito
def create_tables(engine):
    logging.info("→ Criando tabelas...")
    with engine.begin() as conn:
        conn.execute(text(DDL))
    logging.info("✓ Tabelas criadas")


# trunca tudo antes de inserir pra garantir idempotencia
def truncate_tables(engine):
    logging.info("→ Truncando tabelas...")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE persons, crashes, areas, road_types, road_users, genders CASCADE;"))
    logging.info("✓ Tabelas truncadas")


# le os parquets e insere na ordem certa (dimensoes primeiro)
def insert_data(engine):
    logging.info("→ Inserindo dados...")
    for table_name in LOAD_ORDER:
        df = pd.read_parquet(DATA_DIR / f'{table_name}.parquet')
        df.to_sql(name=table_name, con=engine, if_exists='append', index=False)
        logging.info(f"  ✓ {table_name}: {len(df)} registros inseridos")


# roda queries de verificacao pra confirmar que deu certo
def verify_load(engine):
    logging.info("→ Verificando carga...")

    with engine.connect() as conn:
        result = conn.execute(text(VERIFY_QUERY))
        logging.info("\n  contagem por tabela:")
        for row in result:
            logging.info(f"    {row[0]:12s} → {row[1]} registros")

        logging.info("\n  join completo (10 primeiras linhas):")
        result = conn.execute(text(JOIN_QUERY))
        for row in result:
            logging.info(f"    {row}")

    logging.info("\n✓ Load completo!")


# executa o load inteiro: ddl, truncate, insert, verificacao
def load_data():
    engine = get_engine()
    create_tables(engine)
    truncate_tables(engine)
    insert_data(engine)
    verify_load(engine)


if __name__ == "__main__":
    load_data()
