import sqlite3
import os

DB_PATH = "pl_data.db"

# File paths for Kaggle datasets
file_paths = [
    "datasets/premier_player_info.csv",
    "datasets/player_stats_2024_2025_season.csv",
    "datasets/club_stats/2024_season_club_stats.csv"
]


def _table_name(path):
    return path.replace("/", "_").replace(".", "_")


if os.path.exists(DB_PATH):
    # ── Production / Render: database already exists, just extract metadata ──
    print(f"✅ Found existing {DB_PATH}, skipping Kaggle download")
    chroma_metadata = []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for path in file_paths:
        table = _table_name(path)
        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = [row[1] for row in cursor.fetchall()]
        cursor.execute(f'SELECT * FROM "{table}" LIMIT 3')
        rows = cursor.fetchall()
        sample = [dict(zip(columns, row)) for row in rows]
        chroma_metadata.append({
            "table_name": table,
            "columns": columns,
            "sample_values": sample,
        })
    conn.close()
else:
    # ── First-time setup: download from Kaggle and build the database ──
    import kagglehub
    from kagglehub import KaggleDatasetAdapter

    datasets = {}
    for path in file_paths:
        hf_dataset = kagglehub.load_dataset(
            KaggleDatasetAdapter.HUGGING_FACE,
            "danielijezie/premier-league-data-from-2016-to-2024",
            path,
        )
        datasets[path] = hf_dataset

    chroma_metadata = []
    for table_name, ds in datasets.items():
        df = ds.to_pandas()
        meta = {
            "table_name": _table_name(table_name),
            "columns": list(df.columns),
            "sample_values": df.head(3).to_dict(orient="records"),
        }
        chroma_metadata.append(meta)

    conn = sqlite3.connect(DB_PATH)
    for table_name, ds in datasets.items():
        df = ds.to_pandas()
        sqlite_table = _table_name(table_name)
        df.to_sql(sqlite_table, conn, if_exists="replace", index=False)
    conn.close()
    print(f"✅ Built {DB_PATH} from Kaggle datasets")