import pandas as pd

df = pd.read_csv("top5-players.csv")
df = df.drop_duplicates()
df = df.dropna()

print(df.shape)
print(df.isna().sum())
df.to_csv("top5-players-clean.csv", index=False)