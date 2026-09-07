"""
Data ingestion, automated cohort variance filtering, latency corrections,
and backward probe segmentation for the Go/No-Go task.
"""
import glob
from pathlib import Path
from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd

from config import (
    GONOGO_TR_DIR,
    EYELINK_ENCODING,
    DELIMITER,
    HARDWARE_LATENCY_MS,
    FEEDBACK_SCREEN_MS,
    UNRESPONDED_THRESHOLD_MS,
    GONOGO_PRACTICE_TRIALS_DROP,
    GONOGO_PROBE_INTERVAL,
    GONOGO_PROBE_WINDOW_SIZE,
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

        # 2. Remove 500 ms feedback screen on unresponded Go timeouts (>= 1500 ms)
        df["RT_corrected"] = np.where(
            df["IP_DURATION"] >= UNRESPONDED_THRESHOLD_MS,
            df["RT_corrected"] - FEEDBACK_SCREEN_MS,
            df["RT_corrected"],
        )

        # 3. Create a new variable that stores information on whether the participant responded
        df['response_made'] = np.where(
            df['go_nogo_sequence'] == 1,
            np.where(df['IP_DURATION'] < 1500, 1, 0),  # Go Trial Rule (Misses are ~1533 ms)
            np.where(df['IP_DURATION'] < 1032, 1, 0)   # No-Go Trial Rule (Correct withholds are ~1032 ms)
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