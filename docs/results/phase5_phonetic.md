# Phase 5 phonetic sweep

n=500 Zipformer-ASR golden rows. Catalog: `data/doctors.txt`.

| min | margin | correct | resolved | eligible |
|---|---|---|---|---|
| 0.75 | 0.03 | 50 | 51 | 55 |
| 0.75 | 0.05 | 50 | 51 | 55 |
| 0.75 | 0.08 | 45 | 45 | 55 |
| 0.82 | 0.03 | 46 | 46 | 55 |
| 0.82 | 0.05 | 46 | 46 | 55 |
| 0.82 | 0.08 | 45 | 45 | 55 |
| 0.9 | 0.03 | 42 | 42 | 55 |
| 0.9 | 0.05 | 42 | 42 | 55 |
| 0.9 | 0.08 | 42 | 42 | 55 |

Winner: min=`0.75` margin=`0.03` correct=50 resolved=51. Starting point 0.82/0.05 is kept when tied. Production updates only when this cell beats the starting point on **correct** ids.
