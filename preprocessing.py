import pandas as pd
import glob
from pathlib import Path

# Import your centralized global paths for the Fixation Reports
from config import DATA_DIR, READING_FR_DIR, GONOGO_FR_DIR

# Define the clean output directories relative to the global project root
CLEAN_READING_FR_DIR = DATA_DIR / "reading_clean" / "FR"
CLEAN_GONOGO_FR_DIR = DATA_DIR / "gonogo_clean" / "FR"

class EyeLinkPreprocessor:
    """Preprocesses EyeLink Fixation Reports to remove blink artifacts and hardware noise."""
    
    def __init__(self, input_dir: Path, output_dir: Path):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def clean_fixation_report(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies duration boundaries and blink-artifact rejection to fixations."""
        dur_col = "CURRENT_FIX_DURATION"
        if dur_col not in df.columns:
            return df

        # 1. Discard absolute outliers (< 50 ms and > 1500 ms)
        mask_valid_duration = (df[dur_col] >= 50) & (df[dur_col] <= 1500)
        
        # 2. Identify short fixations (< 100 ms)
        mask_short_fix = df[dur_col] < 100
        
        # 3. Identify blinks in adjacent saccades
        prev_blink = df.get("PREVIOUS_SAC_CONTAINS_BLINK", pd.Series(False, index=df.index)).astype(bool)
        next_blink = df.get("NEXT_SAC_CONTAINS_BLINK", pd.Series(False, index=df.index)).astype(bool)
        
        # A fixation is an artifact if it is short AND adjacent to a blink
        mask_blink_artifact = mask_short_fix & (prev_blink | next_blink)
        
        return df[mask_valid_duration & ~mask_blink_artifact].copy()

    def process_directory(self, file_suffix: str = "_fr"):
        """Iterates through specific text files in the input directory, cleans them, and exports."""
        files = glob.glob(str(self.input_dir / f"*{file_suffix}*"))
        
        for file_path in files:
            path_obj = Path(file_path)
            delim = '\t' if path_obj.suffix == '.txt' else ','
            
            try:
                df = pd.read_csv(file_path, delimiter=delim, encoding='latin1', low_memory=False)
            except Exception as e:
                print(f"Error reading {path_obj.name}: {e}")
                continue
                
            df_clean = self.clean_fixation_report(df)
            
            export_path = self.output_dir / path_obj.name
            df_clean.to_csv(export_path, sep=delim, index=False, encoding='latin1')

def main():
    print("--- Starting Upstream Data Preprocessing ---")
    
    # Process Go/NoGo Fixations 
    gonogo_processor = EyeLinkPreprocessor(GONOGO_FR_DIR, CLEAN_GONOGO_FR_DIR)
    gonogo_processor.process_directory("_fr")
    
    # Process Reading Fixations
    reading_processor = EyeLinkPreprocessor(READING_FR_DIR, CLEAN_READING_FR_DIR)
    reading_processor.process_directory("_fr")
    
    print("--- Preprocessing Complete ---")

if __name__ == "__main__":
    main()