import polars as pl

df = pl.read_parquet("data/processed/gold/features.parquet")

df = df.sort("timestamp")

n = df.height

train = df.slice(0, int(n * 0.7))
val   = df.slice(int(n * 0.7), int(n * 0.15))
test  = df.slice(int(n * 0.85), int(n * 0.15))

train.write_parquet("data/splits/train.parquet")
val.write_parquet("data/splits/val.parquet")
test.write_parquet("data/splits/test.parquet")