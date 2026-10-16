import os
from pathlib import Path
from pipeline.loader import ReadingLoader
from config import PROJECT_ROOT

def main():
    # 1. Create a new output directory in the root folder
    output_dir = PROJECT_ROOT / "reading_pipeline_exports"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Initializing ReadingLoader...")
    loader = ReadingLoader()

    # 2. Execute the full pipeline (Drift Correction, Hit-Testing, NLP, Windowing)
    print("Executing full data pipeline. This may take a moment...")
    processed_cohort = loader.load_and_merge_reading_cohort(window_size=3)
    
    if processed_cohort.empty:
        print("Error: No data was processed. Check your raw data directories.")
        return

    # 3. Define the Excel export paths
    cohort_export_path = output_dir / "final_reading_cohort_corrected.xlsx"
    trials_export_path = output_dir / "reading_behavioral_trials.xlsx"

    # 4. Export the dataframes to Excel
    print(f"Exporting fully processed cohort to: {cohort_export_path}")
    processed_cohort.to_excel(cohort_export_path, index=False)


    print("Pipeline execution and export complete.")

if __name__ == "__main__":
    main()