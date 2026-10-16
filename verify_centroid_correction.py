import pandas as pd
from pathlib import Path

# Load your preserved verification dataset
# (Update the path if you saved it in a different directory)
file_path = Path("reading_pipeline_exports/final_reading_cohort_corrected_2.xlsx")
df = pd.read_excel(file_path)

# Calculate the total summation of both metrics
baseline_total = df["IA_DWELL_TIME"].sum()
corrected_total = df["TFT_CORRECTED"].sum()

# Calculate the exact amount of reclaimed fixation time
difference = corrected_total - baseline_total
percent_increase = (difference / baseline_total) * 100

print(f"Baseline IA_DWELL_TIME Total: {baseline_total:,.2f} ms")
print(f"Corrected TFT_CORRECTED Total:  {corrected_total:,.2f} ms")
print(f"Total Data Reclaimed:         {difference:,.2f} ms ({percent_increase:.2f}% increase)")