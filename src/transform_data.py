import pandas as pd
from pathlib import Path

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

path_name = Path(__file__).parent.parent / 'data' / 'raw_crash_data.parquet'

# le o parquet e devolve o dataframe
def create_dataframe (path_name: str) -> pd.DataFrame:
    logging.info("→ Criando DataFrame do arquivo PARQUET...")
    path = path_name

    if not path.exists():
        raise FileNotFoundError(f'Arquivo não encontrado: {path}')
    
    df = pd.read_parquet(path, engine='fastparquet')
    logging.info(f"\n✓ DataFrame criado com {len(df)} linha(s)")

    return df

# converte speed limit pra numerico, texto vira null
def clean_speed_limit(df) -> pd.DataFrame:
    df['Speed Limit'] = pd.to_numeric(df['Speed Limit'], errors='coerce')

    logging.info("\n→ Coluna Speed Limit normalizada")

    return df

# padroniza o case dos tipos de estrada
def clean_road_type(df) -> pd.DataFrame:
    df['National Road Type'] = df['National Road Type'].str.title()

    logging.info("\n→ Coluna National Road Type normalizada")

    return df

# corrige texto em portugues no dataset
def clean_remoteness(df) -> pd.DataFrame:
    df['National Remoteness Areas'] = df['National Remoteness Areas'].str.replace("não registrado", "Not Registered")

    logging.info("\n→ Coluna National Remoteness Areas normalizada")

    return df

# pega so hh:mm da string de time
def clean_time(df) -> pd.DataFrame:
    df['Time'] = df['Time'].str.slice(0, 5)

    return df

# monta tabela de dimensao com os generos unicos
def build_genders(df: pd.DataFrame) -> pd.DataFrame:
    names = sorted(df['Gender'].unique())
    df_genders = pd.DataFrame({
        'gen_id': range(1, len(names) + 1),
        'gen_name': names,
    })
    logging.info(f"✓ genders: {len(df_genders)} registros")
    return df_genders


# monta tabela de dimensao com tipos de usuario
def build_road_users(df: pd.DataFrame) -> pd.DataFrame:
    names = sorted(df['Road User'].unique())
    df_road_users = pd.DataFrame({
        'rdu_id': range(1, len(names) + 1),
        'rdu_name': names,
    })
    logging.info(f"✓ road_users: {len(df_road_users)} registros")
    return df_road_users


# monta tabela de dimensao com tipos de estrada
def build_road_types(df: pd.DataFrame) -> pd.DataFrame:
    names = sorted(df['National Road Type'].unique())
    df_road_types = pd.DataFrame({
        'rdt_id': range(1, len(names) + 1),
        'rdt_name': names,
    })
    logging.info(f"✓ road_types: {len(df_road_types)} registros")
    return df_road_types


# monta tabela de dimensao com combinacoes unicas de localizacao
def build_areas(df: pd.DataFrame) -> pd.DataFrame:
    area_cols = ['State', 'National Remoteness Areas', 'SA4 Name 2016', 'National LGA Name 2017']
    df_areas = (
        df[area_cols]
        .drop_duplicates()
        .sort_values(area_cols)
        .reset_index(drop=True)
    )
    df_areas.insert(0, 'are_id', range(1, len(df_areas) + 1))
    df_areas.columns = ['are_id', 'are_state', 'are_national_remoteness_areas',
                        'are_sa4_name_2016', 'are_national_lga_name_2017']
    logging.info(f"✓ areas: {len(df_areas)} registros")
    return df_areas


# monta tabela de crashes com fks pra areas e road_types
def build_crashes(df: pd.DataFrame, df_areas: pd.DataFrame, road_type_map: dict) -> pd.DataFrame:
    area_cols_orig = ['State', 'National Remoteness Areas', 'SA4 Name 2016', 'National LGA Name 2017']
    area_cols_new = ['are_state', 'are_national_remoteness_areas', 'are_sa4_name_2016', 'are_national_lga_name_2017']

    df_unique = df.drop_duplicates(subset=['Crash ID']).copy()

    merged = df_unique.merge(
        df_areas,
        left_on=area_cols_orig,
        right_on=area_cols_new,
        how='left',
    )

    df_crashes = pd.DataFrame({
        'cra_id': merged['Crash ID'],
        'cra_are_id': merged['are_id'],
        'cra_rdt_id': merged['National Road Type'].map(road_type_map),
        'cra_year': merged['Year'],
        'cra_month': merged['Month'],
        'cra_speed_limit': merged['Speed Limit'],
        'cra_dayweek': merged['Dayweek'],
    })

    logging.info(f"✓ crashes: {len(df_crashes)} registros")
    return df_crashes


# monta tabela de persons com fks pra crashes, genders e road_users
def build_persons(df: pd.DataFrame, gender_map: dict, road_user_map: dict) -> pd.DataFrame:
    df_persons = pd.DataFrame({
        'per_id': range(1, len(df) + 1),
        'per_rdu_id': df['Road User'].map(road_user_map).values,
        'per_gen_id': df['Gender'].map(gender_map).values,
        'per_cra_id': df['Crash ID'].values,
        'per_age': df['Age'].values,
    })

    logging.info(f"✓ persons: {len(df_persons)} registros")
    return df_persons


# roda limpeza + normalizacao e salva os 6 parquets
def transform_data() -> dict[str, pd.DataFrame]:
    df = create_dataframe(path_name)
    df = clean_speed_limit(df)
    df = clean_road_type(df)
    df = clean_remoteness(df)
    df = clean_time(df)

    logging.info("\n normalização")

    df_genders = build_genders(df)
    df_road_users = build_road_users(df)
    df_road_types = build_road_types(df)
    df_areas = build_areas(df)

    gender_map = dict(zip(df_genders['gen_name'], df_genders['gen_id']))
    road_user_map = dict(zip(df_road_users['rdu_name'], df_road_users['rdu_id']))
    road_type_map = dict(zip(df_road_types['rdt_name'], df_road_types['rdt_id']))

    df_crashes = build_crashes(df, df_areas, road_type_map)
    df_persons = build_persons(df, gender_map, road_user_map)

    tables = {
        'genders': df_genders,
        'road_users': df_road_users,
        'road_types': df_road_types,
        'areas': df_areas,
        'crashes': df_crashes,
        'persons': df_persons,
    }

    data_dir = Path(__file__).parent.parent / 'data'
    for name, table_df in tables.items():
        table_df.to_parquet(data_dir / f'{name}.parquet', index=False)
        logging.info(f"  → Salvo data/{name}.parquet")

    logging.info("\n✓ Transform completo!")
    return tables


if __name__ == "__main__":
    transform_data()