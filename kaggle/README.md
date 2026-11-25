# Kaggle GPU Runners (Wan 2.2 TI2V-5B & ACE-Step 1.5)

Notebooks in this folder run on Kaggle's free `2×T4` GPU quota (~30 h/week, phone-verified) and **save each output as it finishes** so session timeouts never discard completed shots or music candidates.

- `wan22_i2v.ipynb`: Runs `Wan-AI/Wan2.2-TI2V-5B-Diffusers` at `24 fps` using motion-only prompts from `storyboard.json` and keyframe PNGs, writing `/kaggle/working/outputs/shots/shot_XX.mp4`.
- `acestep_music.ipynb`: Runs `ACE-Step 1.5` (MIT license) to generate 3 instrumental score candidates (`candidate_1.wav`..`candidate_3.wav`) from `music_cue` metadata (`tempo_bpm`, `key`, `duration_s`) and `caption`.
- `push_and_run.py`: Packages `storyboard.json` + `outputs/keyframes/*.png` as a private Kaggle dataset and pushes both GPU notebooks via `KAGGLE_API_TOKEN`.

Download completed outputs into `kaggle/outputs/shots/` and `kaggle/outputs/music/` before running `make shots` and `make music`.

