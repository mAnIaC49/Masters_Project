# Eye-Tracking & Behavioral Analysis Replication Notes

This file contains my findings during my attempt to replicate Divyansh's and Naman's work on this project.

---

## Replication of Divyansh's work

### Go No-Go


#### Calculation of Go Omission and No-Go Comission Errors
Divyansh's code for calculating these errors in `gonogo_overall_statistic.ipynb` divides the number of trials where the error has occured with the total number of trials instead of dividing it by the total number of go trials or no-go trials. This has led to and underestimation of such errors.

#### Calculation of Coeffecient of Variation
For each mental state, Divyansh has calculated the coeffecient of variation across participants which beats the whole point of using this metric. Instead I have calcuated it for each mental state seperately for each participant and then averaged it across participants.

#### Inferential Statistics
Divyansh has applied a standard (independent) one-way ANOVA on reaction time in the different states. However, since each condition has the same participants, the values in the three states are not truely independent. Also, he has done this on trial level data rather than averaging them by participant first. By treating thousands of individual trials as completely independent observations, the degrees of freedom exploded, making the test hyper-sensitive.

I have instead run a Repeated Measures ANOVA. This wasnt necessary as we would fit a Linear Mixed Effects Model later on, which is a better test for our data, but since Divyansh has conducted an ANOVA, I decided to do it too inorder to check how my results compared to his. I got a p-value of `0.2571`, which is not significant. Further pairwise comparisons don't show significant differences between the three states either.

I first ran a Linear Mixed Effect Model by first keeping On-Task as the baseline and then Mind Wandering as baseline. This is because each time I run it, the baseline condition is compared with the other two conditions, but excludes the comparision of the other two conditions. Running it twice gives me the result of comparing all 3 pairs of conditions. This comparision showed:
- When a participant's mind goes blank, their reaction time drops significantly by ~24.87 ms compared to being on-task `p < 0.001`.
- When a participant's mind wanders, their reaction time only drops by ~2.9 ms compared to being on-task, which is not statistically significant `p = 0.356`. 
- Reaction times are significantly faster (by ~21.97 ms) during mind blanking compared directly to mind wandering `p < 0.001`. 

How do we explain this difference in findings between the results we got from Repeated Measures ANOVA and Linear Mixed Effects model?
- RM ANOVA requires balanced data, i.e. all three conditions (states) must be present in all participants. On removinh the participants who did not experience all three states, 5 of the participants were excluded from this analysis.
- RM ANOVA used participant level mean reaction-time while LME used trial level reaction time. Collapsing thousands of trials down to 10 participants × 3 means = 30 numbers essentially throws away most of your statistical power.

LME's conclusion matches the visible pattern in your raw descriptive means. This along with higher statistical power supports LME's results over ANOVA's.
