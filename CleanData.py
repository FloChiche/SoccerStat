import pandas as pd

data = pd.read_csv("top5-players.csv")
data.drop_duplicates()
data.dropna()