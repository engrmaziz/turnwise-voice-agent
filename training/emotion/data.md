# Emotion corpora licenses

Acted-emotion datasets train a 3-class mapper (calm / frustrated / distressed). They are not a clinic-call distribution. The audio model stays off (`emotion_model_enabled` false) until ADR-011 and a call-like calibration file exist.

Wav files belong in `training/emotion/raw/`, which is gitignored. This repo does not redistribute either corpus.

## CREMA-D

- Source: https://github.com/CheyneyComputerScience/CREMA-D
- License file: https://github.com/CheyneyComputerScience/CREMA-D/blob/master/LICENSE.txt
- Database license: Open Data Commons Open Database License (ODbL) 1.0, http://opendatacommons.org/licenses/odbl/1.0/
- Contents license: Open Data Commons Database Contents License (DbCL) 1.0, http://opendatacommons.org/licenses/dbcl/1.0/

Research and commercial use of the database are allowed under ODbL share-alike. `scripts/download_emotion.py --dataset crema` records that license string and will not start training without it. Fetch into the gitignored directory; do not commit wavs.

## RAVDESS

- Source: https://zenodo.org/records/1188976
- License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0), https://creativecommons.org/licenses/by-nc-sa/4.0/

Non-commercial. A product or paid demo needs a separate commercial license from the authors. The download script exits 2 unless `--research-nc` is passed, and training is `skipped` when that flag is absent.
