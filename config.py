"""
Global constants, project paths, hardware offsets, and experimental parameters.
"""

from pathlib import Path

# 1. Dynamically locate 'Data' by searching current directory and upwards
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = None

for parent in [PROJECT_ROOT, *PROJECT_ROOT.parents]:
  candidate = parent / "Data"
  if candidate.exists():
    DATA_DIR = candidate
    break

if DATA_DIR is None:
    raise FileNotFoundError(
        f"Could not find a 'Data' folder anywhere above {PROJECT_ROOT}"
    )



# 2. Task-Specific Directories
GONOGO_DIR = DATA_DIR / "gonogo"
GONOGO_TR_DIR = GONOGO_DIR / "TR"
GONOGO_FR_DIR = GONOGO_DIR / "FR"
GONOGO_IAR_DIR = GONOGO_DIR / "IAR"

READING_DIR = DATA_DIR / "reading"
READING_TR_DIR = READING_DIR / "trial_report"
READING_FR_DIR = READING_DIR / "Fixation_report"
READING_IAR_DIR = READING_DIR / "Interest_Area_Report"



# 3. Hardware and file format Constants
HARDWARE_LATENCY_MS = 32  # Latency correction: IP_DURATION - 32

# File Ingestion Constants
EYELINK_ENCODING = "latin1"
DELIMITER = "\t"
MENTAL_STATES = {
    1: "On-Task (OT)",
    2: "Mind Wandering (MW)",
    3: "Mind Blanking (MB)",
}



# 4. GONOGO Experimental Parameters
GONOGO_PRACTICE_TRIALS_DROP = 20  # Practice block trials to discard
GONOGO_PROBE_INTERVAL = 15  # Probes occur every 15 trials
GONOGO_PROBE_WINDOW_SIZE = 10  # Preceding trial window length
STIMULUS_TIMEOUT_MS = 1000  # Stimulus presentation timeout limit
FEEDBACK_SCREEN_MS = 500  # "Too slow" feedback screen duration
UNRESPONDED_THRESHOLD_MS = 1500  # Split separating timeouts from keypresses



# 5. Reading Experimental Parameters
READING_PRACTICE_TRIALS_DROP = 4        # Drop first 4 practice trials
READING_TOTAL_PROBES_EXPECTED = 37      # Total probes across 182 experimental trials
READING_PRIOR_WINDOWS = [2, 3, 4]       # Backward evaluation windows
READING_MAX_FIXATION_DURATION_MS = 1500 # Discard individual word fixations > 1500 ms
APPLY_Y_CENTROID_CORRECTION = True      # Apply vertical drift correction

# 6. Survey Directory
SURVEY_DIR = PROJECT_ROOT.parent / "comp_mw"