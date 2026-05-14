from src.extract_data import extract_crash_data
from src.transform_data import transform_data
from src.load_data import load_data

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# roda o pipeline inteiro sem airflow, bom pra debug
def main():
    try:
        logging.info("ETAPA 1: EXTRACT")
        extract_crash_data()

        logging.info("ETAPA 2: TRANSFORM")
        transform_data()

        logging.info("ETAPA 3: LOAD")
        load_data()

        print("\n" + "="*60)
        print("Pipeline concluido com sucesso!")
        print("="*60)

    except Exception as e:
        logging.error(f"ERRO no Pipeline: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
