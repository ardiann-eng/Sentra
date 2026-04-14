import pandas as pd
from sentra_engine import detect_seasonality

# Provide an artificial trend of 12 months with a tiny variation
data = {
    "date": pd.date_range("2023-01-01", periods=12, freq="M"),
    "interest": [50, 52, 51, 55, 60, 65, 58, 54, 50, 48, 51, 53] # peak in around June
}
df = pd.DataFrame(data)

# artificially expand it to 52 weeks to pass the 26 points length check
expanded = []
for i in range(52):
    month_data = df.iloc[i // 4 % 12]['interest']
    date = pd.Timestamp('2023-01-01') + pd.Timedelta(weeks=i)
    expanded.append({'date': date, 'interest': month_data})
    
df_full = pd.DataFrame(expanded)
res = detect_seasonality(df_full)

print("Peak months:", res['peak_months'])
print("Active months:", res['active_months'])
print("Is seasonal:", res['is_seasonal'])
