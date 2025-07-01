import pandas as pd
df = pd.read_csv("companies.csv")
df["ClassName"] = df["ClassName"].apply(lambda x: f"CSS:{x}")
df.to_csv("companies.csv", index=False) 
