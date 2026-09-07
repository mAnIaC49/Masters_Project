# Eye-Tracking & Behavioral Analysis Replication Pipeline

A modular Python framework to process and replicate attentional state analyses (On-Task, Mind Wandering, Mind Blanking) across Go/No-Go and Natural Reading tasks.

---

## 1. Directory Layout

The pipeline expects your code directory (`My codes/`) and the raw experiment datasets (`Data/`, `comp_mw/`, `Model/`) to sit under a common parent folder (e.g., `Neeraj/` or `Prof. Sumitash/`):

```text
<Root Directory Project>/
│
├── Data/
│   ├── gonogo/
│   │   ├── TR/                   # Go/No-Go Trial reports (gonogo_tr__XX.txt)
│   │   ├── FR/                   # Fixation reports (gonogo_fr_XX.txt)
│   │   └── IAR/                  # Interest Area reports (gonogo_iar__XX.txt)
│   │
│   └── reading/
│       ├── trial_report/         # Sentence trial reports (*_tr.txt)
│       ├── Fixation_report/      # Fixation reports (*_fr.txt)
│       └── Interest_Area_Report/ # Word-level IA reports (*_iar.txt)
│
├── comp_mw/                      # Questionnaires & comprehension metrics
├── Model/                        # LME model CSV matrices and scripts
│
└── My codes/                     # This replication repository
    ├── config.py                 # Central project paths & parameters
    ├── run_pipeline.py           # Main execution script
    ├── README.md
    └── pipeline/
        ├── __init__.py
        ├── loader.py             # Ingestion, dynamic P11 filtering, & RT corrections
        └── stats.py              # Summary metrics & error rates

```

---

## 2. Configuration (`config.py`)

- All global parameters and file settings are centralized in `config.py`.
- This program first tries to find the `Data/` directory in the same directory that `config.py` is in, and then iteratively scans for parent nodes one after another for the `Data/` directory. This is done to accomodate for change in location of the `Data/` directory w.r.t `config.py`.
- It then defines paths for locations where the data files exist. These data files include Trial Reports, Fixation Reports, and Interest Area Reports of eye tracker data collected during GONOGO task, and Reading task.
- It then stores certain constants associated with the Hardware or the outputted files. A constant of particular interest would be `HARDWARE_LATENCY_MS`. If you observe the trial reports of the go no go task, you will notice that each *unresponded* no-go trial is *1032 ms* or *1033 ms* long while it should actually be *1000 ms* long. This is a physical display refresh delay that occurs between your Display PC sending a visual command and the stimulus monitor physically rendering it.
- It then defines task specific parameters.
- In the end it defines the path for the directory containing the results of the Comprehension Test and the Mind Wandering Questionnaire.

---

## 3. Data Ingestion & Cohort Filtering (`loader.py`)
- It first imports all the necessary constants from `config.py`.
- It then defines a `GoNoGoLoader` class:
    - The object created on instantiating this class stores two dictionaries; `valid_participants` and `excluded_participants`. Both these dictionaries have the participant identifiers like '01', '02' as the key stored as a string, however the values will be a pandas dataframe containing the participant's data and Dictionary containing the reason for exclusion respectively.
    - The object also contains the function `discover_and_filter_cohort()`. This is where the actual filtering takes place. It first creates a list of all gonogo TR files and stores it as `tr_files`. It then iterates through each of the files, strips practice trials, extracts the probe response column, checks for unique responses, and then excludes participants that have responded to have had only one mental state.
    - The `apply_rt_corrections()` function contained in the object removes the hardware latency from all trials and then removes the 500 ms of feedback on unresponded go trials. Even though there is a column 'REACTION_TIME', in the data, Divyansh probably chose to calculate it using the IP_DURATION column as REACTION_TIME column registers data only if the participant presses a button whereas IP_DURATION registers even on unresponded trials.
    - The `segment_by_probes()` function takes in the data of a participant, iterates through each probe trials, extracts rows before it as per the decided window, and stores this dataframe in a list called `windows`.
    - The `run()` function uses the above functions and filters the data, applies RT Correction, extracts the probe segmentation window data from each valid participant and then appends it to one single master list.

---

## 4. Statistics (`stats.py`)
- It defines a GoNoGoStats class which does statistical analysis on the data from the Go/No-Go task:
    - The class is instantiated by giving a segmented and cleaned `pandas Dataframe`.
    - It then defines a function `calculate_probe_distribution()` which calculates the proportions of different mental states as reported by the participants during the Go/No-Go task.
    - The `calculate_behavioral_measures()` function first iterates through the data of each participant, and then calculates the mean, standard deviation, coeffecient of variance of reaction time in Go trials, percentage of Go-Omission error and No-Go commission error within each mental state for each participant. It then creates an overall summary statistics consisting of the average of the mean reaction time, Coefficient of Variance of reaction time in Go trials, percentage of Go-Omission error and No-Go commission error across participants.
    - The `export_benchmarks()` function uses the results of the statistics and then exports a csv file for the output of `calculate_probe_distribution()` and of `calculate_behavioral_measures()`.
