import pandas as pd
import pytest

from src.transform_data import (
    clean_speed_limit,
    clean_road_type,
    clean_remoteness,
    clean_time,
    build_genders,
    build_road_users,
    build_road_types,
    build_areas,
    build_crashes,
    build_persons,
)


# Fixtures

# fixtures sao funcoes que o pytest injeta nos testes automaticamente.
# qualquer teste que tiver "raw_df" ou "cleaned_df" como parametro
# recebe o DataFrame correspondente sem precisar construir na mao.

@pytest.fixture
def raw_df():
    """Monta um DataFrame pequeno que imita o Excel original.

    Tem de tudo: crash repetido (ID 1 aparece 2x porque teve 2 pessoas),
    speed limits misturados (numero e texto), road types com casing zoado,
    e um "nao registrado" em portugues que apareceu no dataset real.
    """
    return pd.DataFrame({
        "Crash ID": [1, 1, 2, 3],
        "Gender": ["Male", "Female", "Male", "Female"],
        "Age": [25, 30, 45, 22],
        "Road User": ["Driver", "Passenger", "Driver", "Pedestrian"],
        "National Road Type": ["ARTERIAL ROAD", "arterial road", "Local Road", "local road"],
        "Speed Limit": ["80", "Unspecified", "60", "<40"],
        "State": ["NSW", "NSW", "VIC", "QLD"],
        "National Remoteness Areas": ["Major Cities", "Major Cities", "não registrado", "Inner Regional"],
        "SA4 Name 2016": ["Sydney", "Sydney", "Melbourne", "Brisbane"],
        "National LGA Name 2017": ["Parramatta", "Parramatta", "Yarra", "Logan"],
        "Year": [2020, 2020, 2021, 2019],
        "Month": [3, 3, 7, 11],
        "Dayweek": ["Monday", "Monday", "Friday", "Sunday"],
        "Time": ["14:30:00", "14:30:00", "08:15:00", "23:45:00"],
    })


@pytest.fixture
def cleaned_df(raw_df):
    """Passa o raw_df por todas as funcoes de limpeza, na mesma ordem do pipeline.

    Os testes dos builds usam essa fixture porque precisam de dados ja limpos --
    se passasse o raw_df direto, o build_road_types ia criar "ARTERIAL ROAD"
    e "Arterial Road" como tipos separados, que e exatamente o bug que o clean corrige.
    """
    df = clean_speed_limit(raw_df.copy())
    df = clean_road_type(df)
    df = clean_remoteness(df)
    df = clean_time(df)
    return df


# clean_speed_limit

# O Excel original tem speed limit como texto misturado: "80", "60" sao
# numeros, mas "Unspecified" e "<40" nao. O clean converte tudo pra numerico
# e o que nao da vira NaN (vai ser NULL no banco)

class TestCleanSpeedLimit:

    # "80" e "60" viram float 80.0 e 60.0
    def test_converts_numeric_strings(self, raw_df):
        result = clean_speed_limit(raw_df.copy())
        assert result["Speed Limit"].iloc[0] == 80.0
        assert result["Speed Limit"].iloc[2] == 60.0

    # "Unspecified" e "<40" nao sao numeros, entao viram NaN
    def test_non_numeric_becomes_nan(self, raw_df):
        result = clean_speed_limit(raw_df.copy())
        assert pd.isna(result["Speed Limit"].iloc[1])  # "Unspecified"
        assert pd.isna(result["Speed Limit"].iloc[3])  # "<40"

    # depois da limpeza a coluna inteira tem que ser numerica, senao o
    # parquet e o banco vao reclamar de tipo misto
    def test_column_dtype_is_numeric(self, raw_df):
        result = clean_speed_limit(raw_df.copy())
        assert pd.api.types.is_numeric_dtype(result["Speed Limit"])


# clean_road_type
# no dataset real aparece "ARTERIAL ROAD", "arterial road", "Arterial Road"
# pra mesma coisa. O clean padroniza tudo pra Title Case.

class TestCleanRoadType:

    # "ARTERIAL ROAD" e "arterial road" viram "Arterial Road"
    def test_normalizes_to_title_case(self, raw_df):
        result = clean_road_type(raw_df.copy())
        assert result["National Road Type"].iloc[0] == "Arterial Road"
        assert result["National Road Type"].iloc[1] == "Arterial Road"
        assert result["National Road Type"].iloc[3] == "Local Road"

    # antes do clean temos 4 valores (2 duplicados por casing),
    # depois sobram 2 tipos unicos de verdade
    def test_reduces_duplicates_after_normalization(self, raw_df):
        result = clean_road_type(raw_df.copy())
        unique_types = result["National Road Type"].unique()
        assert len(unique_types) == 2


# clean_remoteness
# apareceu "nao registrado" em portugues no meio de um dataset australiano
# foi quando a gente estava testando para lab de banc

class TestCleanRemoteness:

    # o texto em portugues tem que sumir e virar "Not Registered"
    def test_replaces_portuguese_text(self, raw_df):
        result = clean_remoteness(raw_df.copy())
        assert "não registrado" not in result["National Remoteness Areas"].values
        assert "Not Registered" in result["National Remoteness Areas"].values

    # os valores que ja estavam em ingles nao podem ser afetados
    def test_preserves_english_values(self, raw_df):
        result = clean_remoteness(raw_df.copy())
        assert "Major Cities" in result["National Remoteness Areas"].values
        assert "Inner Regional" in result["National Remoteness Areas"].values


# clean_time
# e excel manda o horario como "14:30:00" (com segundos)
# o clean corta pra "14:30" porque os segundos sao sempre 00

class TestCleanTime:

    # confere que os valores saem no formato HH:MM
    def test_extracts_hh_mm(self, raw_df):
        result = clean_time(raw_df.copy())
        assert result["Time"].iloc[0] == "14:30"
        assert result["Time"].iloc[2] == "08:15"
        assert result["Time"].iloc[3] == "23:45"

    # todos os valores tem que ter exatamente 5 caracteres (HH:MM)
    def test_all_values_have_5_chars(self, raw_df):
        result = clean_time(raw_df.copy())
        assert (result["Time"].str.len() == 5).all()


# build_genders
# pega os generos unicos do dataset e monta a tabela de dimensao
# no dataset real so tem Male e Female.

class TestBuildGenders:

    # generos devem vir ordenados alfabeticamente
    def test_extracts_unique_sorted_genders(self, cleaned_df):
        result = build_genders(cleaned_df)
        assert list(result["gen_name"]) == ["Female", "Male"]

    # IDs comecam em 1, nao em 0 (banco relacional, nao array)
    def test_ids_start_at_one(self, cleaned_df):
        result = build_genders(cleaned_df)
        assert result["gen_id"].iloc[0] == 1

    # confere que a tabela so tem as duas colunas esperadas
    def test_has_correct_columns(self, cleaned_df):
        result = build_genders(cleaned_df)
        assert list(result.columns) == ["gen_id", "gen_name"]


# build_road_users
# tipos de usuario: driver, passenger, pedestrian, cyclist, etc.
# mesma logica do genders, pega unicos, ordena, numera.

class TestBuildRoadUsers:

    # no nosso fixture tem 3 tipos: Driver, Passenger, Pedestrian
    def test_extracts_unique_sorted_users(self, cleaned_df):
        result = build_road_users(cleaned_df)
        assert list(result["rdu_name"]) == ["Driver", "Passenger", "Pedestrian"]

    # IDs sequenciais: 1, 2, 3
    def test_sequential_ids(self, cleaned_df):
        result = build_road_users(cleaned_df)
        assert list(result["rdu_id"]) == [1, 2, 3]


# build_road_types
# tipos de estrada. Aqui o ponto e que os valores tem que vir do df
# ja limpo, se vier do raw, "ARTERIAL ROAD" e "Arterial Road" seriam
# tratados como tipos diferentes.

class TestBuildRoadTypes:

    # nao pode ter o valor cru "ARTERIAL ROAD", so o limpo "Arterial Road"
    def test_uses_cleaned_values(self, cleaned_df):
        result = build_road_types(cleaned_df)
        assert "ARTERIAL ROAD" not in result["rdt_name"].values
        assert "Arterial Road" in result["rdt_name"].values

    # a quantidade de linhas tem que bater com o nunique do DataFrame
    def test_count_matches_unique_types(self, cleaned_df):
        expected = cleaned_df["National Road Type"].nunique()
        result = build_road_types(cleaned_df)
        assert len(result) == expected


# build_areas
# essa e a tabela mais interessante. Uma "area" e a combinacao de 4 colunas:
# state + remoteness + SA4 + LGA. Duas linhas com o mesmo State mas LGA
# diferente sao areas diferentes.

class TestBuildAreas:

    # no fixture temos 3 combinacoes unicas de localizacao
    def test_extracts_unique_combinations(self, cleaned_df):
        result = build_areas(cleaned_df)
        assert len(result) == 3

    # confere que os nomes das colunas foram renomeados pro padrao do banco
    def test_has_correct_columns(self, cleaned_df):
        result = build_areas(cleaned_df)
        expected_cols = ["are_id", "are_state", "are_national_remoteness_areas",
                         "are_sa4_name_2016", "are_national_lga_name_2017"]
        assert list(result.columns) == expected_cols

    # se tiver combinacao duplicada, o merge com crashes vai gerar linhas
    # fantasma -- esse teste garante que nao acontece
    def test_no_duplicate_combinations(self, cleaned_df):
        result = build_areas(cleaned_df)
        non_id_cols = result.columns[1:]
        assert not result.duplicated(subset=non_id_cols).any()


# build_crashes
# um acidente pode ter varias pessoas envolvidas (o Crash ID 1 aparece 2x
# no raw porque teve motorista e passageiro). O build pega uma linha por
# crash e mapeia as FKs pra areas e road_types

class TestBuildCrashes:

    # Crash ID 1 aparece 2x no raw, mas a tabela crashes so tem 1 linha pra ele
    def test_deduplicates_by_crash_id(self, cleaned_df):
        df_areas = build_areas(cleaned_df)
        df_road_types = build_road_types(cleaned_df)
        road_type_map = dict(zip(df_road_types["rdt_name"], df_road_types["rdt_id"]))

        result = build_crashes(cleaned_df, df_areas, road_type_map)
        assert len(result) == 3

    # se alguma FK ficou NaN, o INSERT no banco vai explodir por causa do NOT NULL
    def test_foreign_keys_are_populated(self, cleaned_df):
        df_areas = build_areas(cleaned_df)
        df_road_types = build_road_types(cleaned_df)
        road_type_map = dict(zip(df_road_types["rdt_name"], df_road_types["rdt_id"]))

        result = build_crashes(cleaned_df, df_areas, road_type_map)
        assert not result["cra_are_id"].isna().any()
        assert not result["cra_rdt_id"].isna().any()

    # schema da tabela tem que bater com o DDL do load_data.py
    def test_has_correct_columns(self, cleaned_df):
        df_areas = build_areas(cleaned_df)
        df_road_types = build_road_types(cleaned_df)
        road_type_map = dict(zip(df_road_types["rdt_name"], df_road_types["rdt_id"]))

        result = build_crashes(cleaned_df, df_areas, road_type_map)
        expected = ["cra_id", "cra_are_id", "cra_rdt_id", "cra_year", "cra_month",
                    "cra_speed_limit", "cra_dayweek"]
        assert list(result.columns) == expected


# build_persons
# cada linha do dataset original e uma pessoa envolvida num acidente.
# o build mapeia gender e road_user pra IDs e conecta com o crash_id.

class TestBuildPersons:

    # tem que manter todas as linhas -- uma por pessoa, sem dedup
    def test_one_row_per_person(self, cleaned_df):
        df_genders = build_genders(cleaned_df)
        df_road_users = build_road_users(cleaned_df)
        gender_map = dict(zip(df_genders["gen_name"], df_genders["gen_id"]))
        road_user_map = dict(zip(df_road_users["rdu_name"], df_road_users["rdu_id"]))

        result = build_persons(cleaned_df, gender_map, road_user_map)
        assert len(result) == len(cleaned_df)

    # todo per_gen_id e per_rdu_id tem que existir na tabela de dimensao,
    # senao o banco rejeita o INSERT por violacao de FK
    def test_foreign_keys_are_valid(self, cleaned_df):
        df_genders = build_genders(cleaned_df)
        df_road_users = build_road_users(cleaned_df)
        gender_map = dict(zip(df_genders["gen_name"], df_genders["gen_id"]))
        road_user_map = dict(zip(df_road_users["rdu_name"], df_road_users["rdu_id"]))

        result = build_persons(cleaned_df, gender_map, road_user_map)
        valid_gen_ids = set(df_genders["gen_id"])
        valid_rdu_ids = set(df_road_users["rdu_id"])
        assert set(result["per_gen_id"]).issubset(valid_gen_ids)
        assert set(result["per_rdu_id"]).issubset(valid_rdu_ids)

    # IDs sequenciais comecando em 1
    def test_sequential_ids(self, cleaned_df):
        df_genders = build_genders(cleaned_df)
        df_road_users = build_road_users(cleaned_df)
        gender_map = dict(zip(df_genders["gen_name"], df_genders["gen_id"]))
        road_user_map = dict(zip(df_road_users["rdu_name"], df_road_users["rdu_id"]))

        result = build_persons(cleaned_df, gender_map, road_user_map)
        assert list(result["per_id"]) == [1, 2, 3, 4]


# Integracao

# esses dois testes rodam o pipeline de transform completo (sem I/O) e
# verificam que as 6 tabelas se conectam sem furos. E basicamente o mesmo
# que o verify_load() faz no banco com aquele JOIN de 6 tabelas, so que
# aqui roda em milissegundos sem precisar de docker

class TestTransformIntegration:

    # todas as 6 tabelas tem que existir e nao podem estar vazias
    def test_all_six_tables_produced(self, cleaned_df):
        df_genders = build_genders(cleaned_df)
        df_road_users = build_road_users(cleaned_df)
        df_road_types = build_road_types(cleaned_df)
        df_areas = build_areas(cleaned_df)

        gender_map = dict(zip(df_genders["gen_name"], df_genders["gen_id"]))
        road_user_map = dict(zip(df_road_users["rdu_name"], df_road_users["rdu_id"]))
        road_type_map = dict(zip(df_road_types["rdt_name"], df_road_types["rdt_id"]))

        df_crashes = build_crashes(cleaned_df, df_areas, road_type_map)
        df_persons = build_persons(cleaned_df, gender_map, road_user_map)

        tables = {
            "genders": df_genders,
            "road_users": df_road_users,
            "road_types": df_road_types,
            "areas": df_areas,
            "crashes": df_crashes,
            "persons": df_persons,
        }

        assert len(tables) == 6
        for name, df in tables.items():
            assert not df.empty, f"Tabela {name} está vazia"

    # confere que toda FK aponta pra um ID que existe na tabela de dimensao.
    # se alguma coisa quebrar aqui, o banco ia rejeitar o INSERT com erro
    # de foreign key constraint violation -- melhor pegar aqui do que la.
    def test_referential_integrity(self, cleaned_df):
        df_genders = build_genders(cleaned_df)
        df_road_users = build_road_users(cleaned_df)
        df_road_types = build_road_types(cleaned_df)
        df_areas = build_areas(cleaned_df)

        gender_map = dict(zip(df_genders["gen_name"], df_genders["gen_id"]))
        road_user_map = dict(zip(df_road_users["rdu_name"], df_road_users["rdu_id"]))
        road_type_map = dict(zip(df_road_types["rdt_name"], df_road_types["rdt_id"]))

        df_crashes = build_crashes(cleaned_df, df_areas, road_type_map)
        df_persons = build_persons(cleaned_df, gender_map, road_user_map)

        # crashes → areas
        assert set(df_crashes["cra_are_id"]).issubset(set(df_areas["are_id"]))
        # crashes → road_types
        assert set(df_crashes["cra_rdt_id"]).issubset(set(df_road_types["rdt_id"]))
        # persons → crashes
        assert set(df_persons["per_cra_id"]).issubset(set(df_crashes["cra_id"]))
        # persons → genders
        assert set(df_persons["per_gen_id"]).issubset(set(df_genders["gen_id"]))
        # persons → road_users
        assert set(df_persons["per_rdu_id"]).issubset(set(df_road_users["rdu_id"]))
