"""
Generates behavioral summary statistics and benchmark verification tables 
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple
import os
from scipy.stats import f_oneway, ttest_rel
from statsmodels.stats.anova import AnovaRM
from statsmodels.stats.multitest import multipletests
import statsmodels.formula.api as smf

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

                valid_go = go_trials[go_trials['go_nogo_probe_accuracy'] == 1]
                
                go_mean = valid_go['RT_corrected'].mean()
                go_std = valid_go['RT_corrected'].std()
                cov_go = (go_std / go_mean) * 100

                # This is a more concise way of calculating these errors
                commission_errors = (nogo_trials['go_nogo_probe_accuracy'] == 1).mean() * 100 
                omission_errors = (go_trials['go_nogo_probe_accuracy'] == 2).mean() * 100 

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

        return pd.DataFrame(final_results), p_results_df


    def run_inferential_statistics(self) -> None:
        """
        Runs a Repeated-Measures ANOVA and pairwise paired t-tests with Cohen's d 
        on complete-case participant-level mean reaction times.
        """
        from statsmodels.stats.multitest import multipletests
        from statsmodels.stats.anova import AnovaRM
        from scipy.stats import ttest_rel

        # Get participant data 
        _, p_results_df = self.calculate_behavioral_measures() 
        
        if p_results_df.empty:
            print("[Warning] Participant results DataFrame is empty.")
            return

        # 1. Pivot to wide format to easily find participants with complete data
        pivot_rt = p_results_df.pivot(index='participant_id', columns='Attentional State', values='Go Mean RT (ms)')
        
        # 2. Listwise Deletion: Keep only participants who experienced ALL THREE states
        complete_cases = pivot_rt.dropna()
        valid_participants = complete_cases.index

        # 3. Filter the original long-format DataFrame to strictly these balanced participants
        balanced_df = p_results_df[p_results_df['participant_id'].isin(valid_participants)].copy()

        if balanced_df.empty or len(valid_participants) < 2:
            print(f"[Warning] Not enough complete-case participants (N={len(valid_participants)}) to run ANOVA.")
            return

        print("\n================ REPEATED-MEASURES STATISTICAL REPLICATION ================")
        print(f"Data balanced via listwise deletion. Running on N={len(valid_participants)} complete cases.\n")
        
        # 4. Repeated-Measures ANOVA
        # Statsmodels parser crashes on spaces/parentheses. Temporarily rename columns.
        anova_df = balanced_df.rename(columns={
            'Attentional State': 'Attentional_State',
            'Go Mean RT (ms)': 'Go_Mean_RT'
        })

        rm_anova = AnovaRM(
            data=anova_df,
            depvar='Go_Mean_RT',
            subject='participant_id',
            within=['Attentional_State']
        ).fit()
        print(rm_anova.summary())

        # 5. Pairwise Paired t-tests & Effect Sizes (Holm-Bonferroni Corrected)
        ot = complete_cases['On-Task (OT)']
        mw = complete_cases['Mind Wandering (MW)']
        mb = complete_cases['Mind Blanking (MB)']

        def cohens_d_paired(x, y):
            diff = x - y
            return diff.mean() / diff.std(ddof=1)

        comparisons = [
            ("OT vs MB", ot, mb),
            ("OT vs MW", ot, mw),
            ("MW vs MB", mw, mb)
        ]

        raw_p_values = []
        test_stats = []

        for name_str, state_a, state_b in comparisons:
            t_val, p_val = ttest_rel(state_a, state_b)
            d_val = cohens_d_paired(state_a, state_b)
            raw_p_values.append(p_val)
            test_stats.append((name_str, t_val, d_val))
            
        # Apply Holm-Bonferroni correction
        reject_flags, corrected_p_values, _, _ = multipletests(raw_p_values, alpha=0.05, method='holm')

        print("\n--- Pairwise Comparisons (Holm-Bonferroni Corrected) ---")
        for i, (name_str, t_val, d_val) in enumerate(test_stats):
            sig_flag = "*" if reject_flags[i] else "ns"
            print(f"Pairwise {name_str}: t = {t_val:.2f}, p_raw = {raw_p_values[i]:.5f}, p_corr = {corrected_p_values[i]:.5f} {sig_flag}, Cohen's d = {d_val:.2f}")
            
        print("===========================================================================\n")


    def run_lme_model(self) -> None:
        """
        Runs a Linear Mixed-Effects (LME) model on Go trials to compare 
        Reaction Times across mental states with random effects for participants.
        """
        # 1. Filter for Go trials with valid responses
        go_trials = self.df[(self.df['go_nogo_sequence'] == 1) & (self.df['go_nogo_probe_accuracy'] == 1)].copy()
        
        if go_trials.empty:
            print("[Warning] No valid Go trials found for LME model.")
            return

        # 2. Map the numeric mental states to their string labels to match the categorical design
        go_trials['State'] = go_trials['mental_state'].map(MENTAL_STATES)
        
        # Drop any missing RTs or States
        model_df = go_trials.dropna(subset=['RT_corrected', 'State', 'participant_id'])

        print("\n================ LINEAR MIXED-EFFECTS (LME) MODEL ================")
        print(f"Running LME on {len(model_df)} Go trials across {model_df['participant_id'].nunique()} participants.")
        
        # 3. Define the LME Formula
        # Dependent: RT_corrected
        # Fixed Effect: State (categorical, with 'On-Task (OT)' or 'Mind Wandering (MW)' as the baseline reference)
        # Random Effect (Groups): participant_id
        
        # formula = "RT_corrected ~ C(State, Treatment(reference='On-Task (OT)'))"
        formula = "RT_corrected ~ C(State, Treatment(reference='Mind Wandering (MW)'))"
        
        try:
            # 4. Fit the model using statsmodels
            lme_model = smf.mixedlm(
                formula=formula,
                data=model_df,
                groups=model_df['participant_id']
            )
            lme_results = lme_model.fit()
            print(lme_results.summary())
            
        except Exception as e:
            print(f"[Error] Failed to fit LME model: {e}")
            
        print("==================================================================\n")


    def export_benchmarks(self, output_dir: str = "results") -> None:
        """
        Saves Table 1 and Table 2 to disk as CSV files and a formatted text file, 
        mirroring the original study's output structure.
        """
        # Create the results directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        table1 = self.calculate_probe_distribution(self.df)
        table2_summary, table2_participants = self.calculate_behavioral_measures()
        
        # Export as CSVs for statistical software
        table1.to_csv(f"{output_dir}/table1_probe_distribution.csv")
        table2_summary.to_csv(f"{output_dir}/table2_behavioral_benchmarks.csv", index=False)
        table2_participants.to_csv(f"{output_dir}/table2_participant_breakdown.csv", index=False)

        print(f"\n[Success] Benchmark CSVs exported to '{output_dir}/'.")