"""
Generates behavioral summary statistics and benchmark verification tables 
"""
import pandas as pd
import numpy as np
from typing import Dict
import os

from config import (
    MENTAL_STATES
)

class GoNoGoStats:
    def __init__(self, df_segmented: pd.DataFrame):
        self.df = df_segmented.copy()

    @staticmethod
    def calculate_probe_distribution(df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes total counts and percentages for On-Task (1), 
        Mind Wandering (2), and Mind Blanking (3) matching Table 1.
        """
        # Count unique probe events across participants
        # Since df is windowed (10 rows per probe), we extract unique probe identifiers per participant
        if 'probe_id' in df.columns and 'participant_id' in df.columns:
            probes_df = df[['participant_id', 'probe_id', 'mental_state']].drop_duplicates()
        else:
            raise KeyError(
                "Cannot calculate probe distribution. The required columns "
                "('probe_id', 'participant_id') are missing. Ensure the data "
                "was properly windowed by loader.py before passing it to stats.py."
            )

        # Drop duplicates so we only count 1 row per actual thought probe
        probes_df = df[['participant_id', 'probe_id', 'mental_state']].drop_duplicates()

        counts = probes_df['mental_state'].value_counts().sort_index()
        total = counts.sum()

        # Define a pandas dataframe called summary that consists of two variables 'Count' and 'Percentage'
        summary = pd.DataFrame({
            'Count': counts,
            'Percentage': (counts / total) * 100
        })
        summary.index = summary.index.map(MENTAL_STATES)
        return summary

    def calculate_behavioral_measures(self) -> pd.DataFrame:
        """
        Computes Divyansh's thesis's Table 2 benchmark metrics per attentional state:
        - Go Mean RT & Standard Deviation
        - Coefficient of Variation (COV Go %)
        - No-Go Commission Error Rate (%)
        - Go Omission Error Rate (%)
        """
        participant_rows = []

        # Group by participant first to ensure proper hierarchical aggregation
        for pid, p_df in self.df.groupby('participant_id'):
            for state_val, state_name in MENTAL_STATES.items():
                subset = p_df[p_df['mental_state'] == state_val]

                go_trials = subset[subset['go_nogo_sequence'] == 1]
                nogo_trials = subset[subset['go_nogo_sequence'] != 1]

                valid_go = go_trials[go_trials['response_made'] == 1]
                
                go_mean = valid_go['RT_corrected'].mean()
                go_std = valid_go['RT_corrected'].std()
                cov_go = (go_std / go_mean) * 100

                # This is a more concise way of calculating these errors
                commission_errors = (nogo_trials['response_made'] == 1).mean() * 100 
                omission_errors = (go_trials['response_made'] == 0).mean() * 100 

                participant_rows.append({
                    'participant_id': pid,
                    'Attentional State': state_name,
                    'Go Mean RT (ms)': go_mean,
                    'Go Std (ms)': go_std,
                    'COV Go (%)': cov_go,
                    'No-Go Commission Error (%)': commission_errors,
                    'Go Omission Error (%)': omission_errors
                })

        p_results_df = pd.DataFrame(participant_rows)

        # Average across participants for each attentional state to get Table 2 benchmarks
        final_results = []
        for state_val, state_name in MENTAL_STATES.items():
            state_subset = p_results_df[p_results_df['Attentional State'] == state_name]
            

            final_results.append({
                'Attentional State': state_name,
                'Go Mean RT (ms)': round(state_subset['Go Mean RT (ms)'].mean(), 2),
                'COV Go (%)': round(state_subset['COV Go (%)'].mean(), 2),
                'No-Go Commission Error (%)': round(state_subset['No-Go Commission Error (%)'].mean(), 2),
                'Go Omission Error (%)': round(state_subset['Go Omission Error (%)'].mean(), 2)
            })

        return pd.DataFrame(final_results)

    def export_benchmarks(self, output_dir: str = "results") -> None:
        """
        Saves Table 1 and Table 2 to disk as CSV files and a formatted text file, 
        mirroring the original study's output structure.
        """
        # Create the results directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        table1 = self.calculate_probe_distribution(self.df)
        table2 = self.calculate_behavioral_measures()
        
        # Export as CSVs for statistical software
        table1.to_csv(f"{output_dir}/table1_probe_distribution.csv")
        table2.to_csv(f"{output_dir}/table2_behavioral_benchmarks.csv", index=False)

        print(f"\n[Success] Benchmark CSVs exported to '{output_dir}/'.")