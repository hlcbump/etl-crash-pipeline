from pathlib import Path
import pandas as pd
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_crash_data():
    raw_input_path = Path(__file__).resolve().parent.parent / 'data' / 'Crash_Data.xlsx'
    output_path = Path(__file__).resolve().parent.parent / 'data' / 'raw_crash_data.parquet'

    logging.info(f"Lendo arquivo: {raw_input_path}")
    df = pd.read_excel(raw_input_path, engine='openpyxl')

    if df.empty:
        logging.warning("Nenhum dado retornado")
        return

    # speed limit tem int e string misturados, parquet nao aceita tipos mistos
    df['Speed Limit'] = df['Speed Limit'].astype(str)
    # time vem como datetime.time do excel, fastparquet nao suporta esse tipo
    df['Time'] = df['Time'].astype(str)
    df.to_parquet(output_path, index=False)
    logging.info(f"Extraidos {len(df)} registros -> {output_path}")

if __name__ == "__main__":
    extract_crash_data()
