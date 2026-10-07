"""
Data ingestion, automated cohort variance filtering, latency corrections,
and backward probe segmentation for the Go/No-Go task.
"""
import glob
from pathlib import Path
from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd
import nltk
from nltk.tokenize import word_tokenize

from config import (
    PROJECT_ROOT,
    APPLY_Y_CENTROID_CORRECTION,
    GONOGO_TR_DIR,
    EYELINK_ENCODING,
    DELIMITER,
    HARDWARE_LATENCY_MS,
    MENTAL_STATES,
    FEEDBACK_SCREEN_MS,
    UNRESPONDED_THRESHOLD_MS,
    GONOGO_PRACTICE_TRIALS_DROP,
    GONOGO_PROBE_INTERVAL,
    GONOGO_PROBE_WINDOW_SIZE,
    READING_TR_DIR,
    READING_IAR_DIR,
    READING_FR_DIR,
    READING_PRACTICE_TRIALS_DROP,
    READING_MAX_FIXATION_DURATION_MS
)

class GoNoGoLoader:
    """Modular data loader and processor for Go/No-Go EyeLink trial reports."""

    def __init__(self, tr_dir: Optional[Union[str, Path]] = None):
        # Fall back to centralized config path if none provided
        self.tr_dir = Path(tr_dir).resolve() if tr_dir else GONOGO_TR_DIR

        if not self.tr_dir.exists():
            raise FileNotFoundError(f"Go/No-Go TR directory not found: {self.tr_dir}")

        self.valid_participants: Dict[str, pd.DataFrame] = {}
        self.excluded_participants: Dict[str, dict] = {}

    def discover_and_filter_cohort(self) -> None:
        """
        Scans all trial reports in TR, strips the practice block, and excludes 
        participants with zero mental state variance across probes as was a
        case specified by Divyansh.
        """
        pattern = str(self.tr_dir / "gonogo_tr__*.txt")
        tr_files = sorted(glob.glob(pattern))

        if not tr_files:
            raise FileNotFoundError(f"No trial report text files found in {self.tr_dir}")

        for fpath in tr_files:
            pid = Path(fpath).stem.replace("gonogo_tr__", "")

            # EyeLink reports require tab-delimiter and latin1 encoding
            df = pd.read_csv(fpath, delimiter=DELIMITER, encoding=EYELINK_ENCODING)

            # 1. Strip the initial practice trials
            df_exp = df.iloc[GONOGO_PRACTICE_TRIALS_DROP:].reset_index(drop=True)

            # 2. Locate the probe response column
            probe_col = 'probe_accuracy'
            if probe_col not in df_exp.columns:
              raise KeyError(
                  f"Required mental state column '{probe_col}' not found in {fpath}."
                  f' Available columns: {list(df_exp.columns)}'
              )

            # 3. Dynamic variance check: inspect probes every 15 trials (14, 29, 44, ...)
            probe_indices = range(GONOGO_PROBE_INTERVAL - 1, len(df_exp), GONOGO_PROBE_INTERVAL)
            reported_states = set(df_exp.iloc[probe_indices][probe_col].dropna().unique())

            # Exclude participants lacking variance across mental states (e.g. Participant 11)
            if len(reported_states) <= 1:
                self.excluded_participants[pid] = {
                    "reason": "Zero mental state variance across probes",
                    "unique_states": [int(s) for s in reported_states],
                }
            else:
                self.valid_participants[pid] = df_exp

    @staticmethod
    def apply_rt_corrections(df: pd.DataFrame) -> pd.DataFrame:
        """
        Subtracts hardware latency and strips the 500 ms feedback screen
        from timed-out Go trials.
        """
        df = df.copy()

        # 1. Base display refresh latency adjustment (33 ms)
        df["RT_corrected"] = df["IP_DURATION"] - HARDWARE_LATENCY_MS

        # 2. Remove 500 ms feedback screen on unresponded Go trials
        # Identify unresponded Go trials using the native task rules
        is_go_trial = (df["go_nogo_sequence"] == 1)
        is_timeout = (df["go_nogo_probe_accuracy"] == 2)

        df["RT_corrected"] = np.where(
            is_go_trial & is_timeout,
            df["RT_corrected"] - FEEDBACK_SCREEN_MS,
            df["RT_corrected"],
        )

        return df

    @staticmethod
    def segment_by_probes(df: pd.DataFrame, pid: str) -> pd.DataFrame:
        """
        Slices the preceding 10 trials mapped backward from each probe.
        """
        windows: List[pd.DataFrame] = [] #This is a new way of defining list by specifying the data type
        probe_indices = range(GONOGO_PROBE_INTERVAL - 1, len(df), GONOGO_PROBE_INTERVAL)

        for p_idx in probe_indices:
            probe_state = df.iloc[p_idx]["probe_accuracy"]
            start_idx = p_idx - (GONOGO_PROBE_WINDOW_SIZE - 1)

            # Window of 10 trials ending at the probe
            window = df.iloc[start_idx : p_idx + 1].copy()

            # Create new variables and 'broadcast' the same values for all 10 rows
            window["participant_id"] = pid 
            window["probe_id"] = p_idx
            window["mental_state"] = probe_state
            windows.append(window)

        return pd.concat(windows, ignore_index=True) if windows else pd.DataFrame()

    def run(self) -> pd.DataFrame:
        """
        Executes ingestion, filtering, RT correction, and backward probe windowing.
        Returns a single combined DataFrame across all valid participants.
        """
        self.discover_and_filter_cohort()

        all_cohort_windows: List[pd.DataFrame] = []
        for pid, df_exp in self.valid_participants.items():
            df_corrected = self.apply_rt_corrections(df_exp)
            df_segmented = self.segment_by_probes(df_corrected, pid)
            all_cohort_windows.append(df_segmented)

        if not all_cohort_windows:
            return pd.DataFrame()

        return pd.concat(all_cohort_windows, ignore_index=True)



class ReadingLoader:
    """
    Ingests and processes Reading Task data from EyeLink reports.
    Applies Y-axis drift correction and dynamically extracts word metrics via NLTK.
    """
    def __init__(self):
        self.reading_text_file = PROJECT_ROOT / "data" / "the_reading_text.csv"

        # Explicitly exclude participants with technical limitations as per the thesis
        self.excluded_participants = ["7", "13"]
        
        self.df_trials = pd.DataFrame()
        self.processed_data = pd.DataFrame()

    def load_reading_sentences(self) -> pd.DataFrame:
        """Loads the base sentence and probe sequence data if needed for later mapping."""
        if self.reading_text_file.exists():
            return pd.read_csv(self.reading_text_file)
        print(f"Warning: Missing reading text file: {self.reading_text_file}")
        return pd.DataFrame()

    def calculate_y_drift_offsets(self, df_fr_p: pd.DataFrame, df_iar_p: pd.DataFrame) -> Dict[int, float]:
        """Calculates trial-by-trial vertical centroid offsets for Y-axis calibration."""
        y_offsets = {}
        for trial in df_fr_p["TRIAL_INDEX"].unique():
            iar_trial = df_iar_p[df_iar_p["TRIAL_INDEX"] == trial]
            fr_trial = df_fr_p[df_fr_p["TRIAL_INDEX"] == trial]

            if iar_trial.empty or fr_trial.empty:
                y_offsets[trial] = 0.0
                continue

            min_top = iar_trial["IA_TOP"].min() if "IA_TOP" in iar_trial.columns else 0 # highest point in the interest area (word)
            max_bottom = iar_trial["IA_BOTTOM"].max() if "IA_BOTTOM" in iar_trial.columns else 0 # lowest point in the interest area
            height_center = (min_top + max_bottom) / 2.0 # center of the interest area
            ia_height = max_bottom - min_top

            fix_y_col = "CURRENT_FIX_Y"
            if fix_y_col not in fr_trial.columns:
                y_offsets[trial] = 0.0
                continue

            valid_fix = fr_trial[
                (fr_trial[fix_y_col] >= (min_top - ia_height)) &
                (fr_trial[fix_y_col] <= (max_bottom + ia_height))
            ]

            if valid_fix.empty:
                y_offsets[trial] = 0.0
            else:
                fix_min = valid_fix[fix_y_col].min()
                fix_max = valid_fix[fix_y_col].max()
                fix_center = fix_min + (fix_max - fix_min) / 2.0
                y_offsets[trial] = round(height_center - fix_center, 2)

        return y_offsets

    def load_trial_reports(self) -> pd.DataFrame:
        """Loads trial reports to capture mental state probes."""
        tr_files = glob.glob(str(READING_TR_DIR / "*_tr.txt"))
        df_list = []

        for fpath in tr_files:
            pid = Path(fpath).stem.split("_")[0]
            
            # Skip excluded participants
            if pid in self.excluded_participants:
                continue
            df = pd.read_csv(fpath, delimiter=DELIMITER, encoding=EYELINK_ENCODING, low_memory=False)
            df["participant_id"] = pid

            # Map the custom experiment variable to standard TRIAL_INDEX for merging
            if "Trial_Index_" in df.columns:
                df["TRIAL_INDEX"] = df["Trial_Index_"]
            elif "INDEX" in df.columns:
                df["TRIAL_INDEX"] = df["INDEX"]

            df = df[df["TRIAL_INDEX"] > READING_PRACTICE_TRIALS_DROP].copy() # drop practice trials.
            df_list.append(df)

        self.df_trials = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
        return self.df_trials


    def extract_lexical_properties(self, df: pd.DataFrame) -> pd.DataFrame:
        """Dynamically calculates Word Length and Word Frequency from fixation strings."""
        label_col = "IA_LABEL" if "IA_LABEL" in df.columns else "CURRENT_FIX_INTEREST_AREA_LABEL"
        
        if label_col not in df.columns:
            return df
            
        # Tokenize to extract the core word, ignoring punctuation
        df['tokens'] = df[label_col].astype(str).apply(word_tokenize)
        df['lexicon'] = df['tokens'].apply(lambda x: x[0] if x else None)
        df.drop(columns=['tokens'], inplace=True)

        # Calculate base metrics
        df['WL'] = df['lexicon'].str.len()
        word_freq = df['lexicon'].value_counts() # because every time the word repeats, its a different interest area.
        df['WF'] = df['lexicon'].map(word_freq)

        # Standardize scaling for LME models (-1 to 1)
        for col in ["WL", "WF"]:
            if col in df.columns:
                centered = df[col] - df[col].mean()
                max_dev = centered.abs().max()
                df[f"{col}_norm"] = centered / max_dev if max_dev != 0 else centered
                
        return df

    def load_and_merge_reading_cohort(self, window_size: int = 4) -> pd.DataFrame:
        """Executes full loading, offset calibration, backward propagation, and NLP extraction."""
        if self.df_trials.empty:
            self.load_trial_reports()

        iar_files = glob.glob(str(READING_IAR_DIR / "*_iar.txt"))
        cohort_dfs = []

        for iar_path in iar_files:
            pid = Path(iar_path).stem.split("_")[0]
            
            # Skip excluded participants
            if pid in self.excluded_participants:
                continue
                
            df_iar_p = pd.read_csv(iar_path, delimiter=DELIMITER, encoding=EYELINK_ENCODING, low_memory=False)
            df_iar_p["participant_id"] = pid
            
            # Ensure the Interest Area Report uses the custom sequence
            if "Trial_Index_" in df_iar_p.columns:
                df_iar_p["TRIAL_INDEX"] = df_iar_p["Trial_Index_"]

            if APPLY_Y_CENTROID_CORRECTION:
                fr_path = READING_FR_DIR / f"{pid}_fr.txt"
                if fr_path.exists():
                    df_fr_p = pd.read_csv(fr_path, delimiter=DELIMITER, encoding=EYELINK_ENCODING, low_memory=False)
                    
                    # Ensure the Fixation Report uses the custom sequence
                    if "Trial_Index_" in df_fr_p.columns:
                        df_fr_p["TRIAL_INDEX"] = df_fr_p["Trial_Index_"]
                        
                    y_corrections = self.calculate_y_drift_offsets(df_fr_p, df_iar_p)
                    df_iar_p["Y_OFFSET"] = df_iar_p["TRIAL_INDEX"].map(y_corrections).fillna(0.0)
                else:
                    df_iar_p["Y_OFFSET"] = 0.0

            p_tr = self.df_trials[self.df_trials["participant_id"] == pid].sort_values("TRIAL_INDEX")
            probe_trials = p_tr[p_tr["probe_accuracy"].isin(MENTAL_STATES.keys())]

            df_iar_p["Attentional_State"] = np.nan
            df_iar_p["Probe_Trial_ID"] = np.nan

            for _, probe_row in probe_trials.iterrows():
                probe_idx = probe_row["TRIAL_INDEX"]
                state_label = MENTAL_STATES.get(probe_row["probe_accuracy"])

                start_window = max(1, probe_idx - window_size + 1)
                mask = (df_iar_p["TRIAL_INDEX"] >= start_window) & (df_iar_p["TRIAL_INDEX"] <= probe_idx)
                df_iar_p.loc[mask, "Attentional_State"] = state_label
                df_iar_p.loc[mask, "Probe_Trial_ID"] = probe_idx

            cohort_dfs.append(df_iar_p)

        full_df = pd.concat(cohort_dfs, ignore_index=True) if cohort_dfs else pd.DataFrame()
        if full_df.empty:
            return full_df

        full_df = self.extract_lexical_properties(full_df)

        tft_col = "IA_DWELL_TIME" if "IA_DWELL_TIME" in full_df.columns else "TFT"
        fft_col = "IA_FIRST_FIXATION_DURATION" if "IA_FIRST_FIXATION_DURATION" in full_df.columns else "FFT"

        if tft_col in full_df.columns:
            valid_mask = (full_df[tft_col] >= 50) & (full_df[tft_col] <= READING_MAX_FIXATION_DURATION_MS)
            full_df = full_df[valid_mask].copy()
            full_df["log_TFT"] = np.log(full_df[tft_col])
            
        if fft_col in full_df.columns:
            full_df.loc[full_df[fft_col] > 0, "log_FFT"] = np.log(full_df[full_df[fft_col] > 0][fft_col])

        self.processed_data = full_df
        return self.processed_data