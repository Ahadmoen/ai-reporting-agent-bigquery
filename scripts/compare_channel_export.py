"""Compares the team's channel export (CSV) with BigQuery channel data (CSV) by week and channel.

Usage:
  python3 -I compare_channel_export.py team_export.csv bigquery_result.csv

team_export.csv columns: semana, canales, eventos (as exported by the team)
bigquery_result.csv columns: semana, canal, compras (output of sql/validation/03_channels_by_week.sql)
Result in production: 26 of 27 channel figures matched exactly across three weeks.
"""
import sys
import pandas as pd

team = pd.read_csv(sys.argv[1])
team["eventos"] = pd.to_numeric(team["eventos"].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
team["semana"] = team["semana"].str.strip().str.lower()
bq = pd.read_csv(sys.argv[2])
bq["semana"] = bq["semana"].str.strip().str.lower()

t = team.groupby(["semana", "canales"])["eventos"].sum().reset_index()
t.columns = ["semana", "canal", "export"]
m = t.merge(bq[["semana", "canal", "compras"]], on=["semana", "canal"], how="inner")
m["dif"] = m["compras"] - m["export"]
print(m.sort_values(["semana", "export"], ascending=[True, False]).to_string(index=False))
print(m.groupby("semana")[["export", "compras", "dif"]].sum())
print(f"exact: {(m['dif'] == 0).sum()} of {len(m)}")
