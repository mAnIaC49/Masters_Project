"""
Main execution entry point for the replication pipeline.
"""
from pipeline.loader import GoNoGoLoader
from pipeline.stats import GoNoGoStats


def main():
  print("Starting Replication Pipeline...\n")

  # 1. Load, filter cohort, apply RT corrections, and segment probe windows
  loader = GoNoGoLoader()
  df_windowed = loader.run()

  if df_windowed.empty:
    print("Pipeline halted: No valid data processed.")
    return

  # 2. Generate thesis benchmark verification tables (Tables 1 & 2)
  go_nogo_stats = GoNoGoStats(df_windowed)
  go_nogo_stats.export_benchmarks()

  # 3. Run the Repeated-Measures ANOVA and Post-Hoc Tests
  go_nogo_stats.run_inferential_statistics()

  # 4. Run the LME for Go-NOGO behavioral measures
  go_nogo_stats.run_lme_model()

  print("\nPipeline execution completed successfully.")


if __name__ == "__main__":
  main()