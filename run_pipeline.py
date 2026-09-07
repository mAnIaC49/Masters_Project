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
  stats = GoNoGoStats(df_windowed)
  stats.export_benchmarks()

  print("\nPipeline execution completed successfully.")


if __name__ == "__main__":
  main()