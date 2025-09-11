import kagglehub
from kagglehub import KaggleDatasetAdapter
import sqlite3

# File paths for Kaggle datasets
file_paths = [
    "datasets/premier_player_info.csv",
    "datasets/player_stats_2024_2025_season.csv",
    "datasets/club_stats/2024_season_club_stats.csv"
]

datasets = {}

# Load datasets from Kaggle
for path in file_paths:
    hf_dataset = kagglehub.load_dataset(
        KaggleDatasetAdapter.HUGGING_FACE,
        "danielijezie/premier-league-data-from-2016-to-2024",
        path
    )
    datasets[path] = hf_dataset

# Build metadata for Chroma/LLM
chroma_metadata = []
for table_name, ds in datasets.items():
    df = ds.to_pandas()
    meta = {
        "table_name": table_name.replace("/", "_").replace(".", "_"),
        "columns": list(df.columns),
        "sample_values": df.head(3).to_dict(orient="records")
    }
    chroma_metadata.append(meta)

# Export DataFrames to SQLite for SQL execution
def export_to_sqlite(db_path="pl_data.db"):
    conn = sqlite3.connect(db_path)
    for table_name, ds in datasets.items():
        df = ds.to_pandas()
        sqlite_table = table_name.replace("/", "_").replace(".", "_")
        df.to_sql(sqlite_table, conn, if_exists="replace", index=False)
    conn.close()

export_to_sqlite()