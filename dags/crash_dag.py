from datetime import datetime, timedelta
from airflow.decorators import dag, task
import sys

sys.path.insert(0, '/opt/airflow/src')


# dag do pipeline de acidentes — trigger manual, dataset estatico
@dag(
    dag_id='crash_pipeline',
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'retries': 2,
        'retry_delay': timedelta(minutes=5)
    },
    description='ETL pipeline - Australian road crash data',
    schedule=None,
    start_date=datetime(2026, 5, 14),
    catchup=False,
    tags=['crash', 'etl']
)
def crash_pipeline():

    # le o xlsx e salva como parquet
    @task
    def extract():
        from extract_data import extract_crash_data
        extract_crash_data()

    # limpa dados sujos e normaliza em 6 tabelas
    @task
    def transform():
        from transform_data import transform_data
        transform_data()

    # cria tabelas no postgres e insere os dados
    @task
    def load():
        from load_data import load_data
        load_data()

    extract() >> transform() >> load()


crash_pipeline()
