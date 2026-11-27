# PolyglotXprs

Offline multilingual transcription with speaker detection, based on
[aTrain](https://github.com/JuergenFleiss/aTrain).

> **Status: untested base build, published for testing only.** It passes the
> automated test suite but has not yet been tried on Windows or with real
> recordings. Do not use it for real or sensitive recordings yet. Test with
> synthetic or public audio.

PolyglotXprs is a fork of aTrain by the Business Analytics and Data
Science-Center, University of Graz. It is not affiliated with or endorsed by
the aTrain team. The application window still shows aTrain's name and logo;
renaming the interface is planned.

## What it does

- **Transcribes recordings entirely on your computer.** Recordings and
  transcripts never leave it.
- **Detects speakers** and labels them Speaker 1, Speaker 2 and so on.
- **Covers 99 languages** through OpenAI's Whisper models (via
  [faster-whisper](https://github.com/SYSTRAN/faster-whisper)). Accuracy varies
  by language; see Whisper's
  [per-language error rates](https://github.com/openai/whisper?tab=readme-ov-file#available-models-and-languages).
- **Exports transcripts** as text, SRT subtitles and JSON, and in formats that
  import into MAXQDA, ATLAS.ti and NVivo (see the [tutorial](docs/tutorials.md)).
- **Runs on a CPU or an NVIDIA GPU.** A GPU is much faster.

## How it differs from aTrain

- **Internal model source.** Organisations can set `ATRAIN_MODEL_SOURCE` to a
  network share or internal web server. Models are then loaded only from there,
  and Hugging Face is never contacted. See the
  [administrator guide](docs/internal-model-source.md).
- **Only permissively licensed models.** Every model offered is under MIT,
  Apache-2.0 or CC-BY-4.0. Models under non-commercial licences are removed, and
  a test prevents them from returning through updates from aTrain.
- **Planned:** more speech recognition engines (Qwen3-ASR, NVIDIA Parakeet),
  choosing the best model for each speaker's language, and a step for reviewing
  and correcting transcripts. See [docs/fork.md](docs/fork.md).

## Privacy and network use

- Audio and transcripts are processed and stored only on your computer.
- The only network access is downloading models:
  - by default, from the aTrain project's mirrors on Hugging Face, pinned to
    exact versions;
  - with `ATRAIN_MODEL_SOURCE` set, only from that source.
- Every downloaded model file is checked against a SHA-256 hash stored in this
  repository. Files that do not match are deleted.
- Once the models you need are downloaded, the app makes no network requests
  and works on a computer with no network connection.
- Telemetry in the speaker detection library is switched off.

## Installing for testing

There are no installers yet. Run it from source:

1. Install [Git](https://git-scm.com/), and
   [uv](https://docs.astral.sh/uv/getting-started/installation/), which
   installs a suitable Python by itself.
2. Clone this repository: copy its URL from the green **Code** button, then
   ```bash
   git clone <repository URL>
   cd PolyglotXprs
   ```
3. Install the dependencies (several GB, including PyTorch):
   ```bash
   uv sync --extra gui
   ```
4. Download the required models (Whisper large-v3-turbo and speaker detection):
   ```bash
   uv run aTrain init
   ```
5. Start the app:
   ```bash
   uv run aTrain start
   ```

The commands are still called `aTrain` and `aTrain_core`. Internal names are
kept unchanged so updates from aTrain can be merged easily.

On Linux, the desktop window needs some system libraries first; see the
"Linux: native GUI build dependencies" section of
[CONTRIBUTING.md](CONTRIBUTING.md).

## Command line

Transcribe a file with the default model:

```bash
uv run aTrain_core transcribe /path/to/recording.mp3
```

With options:

```bash
uv run aTrain_core transcribe /path/to/recording.mp3 \
    --model large-v3 --language en \
    --speaker-detection --speaker-count 2 \
    --device gpu --compute-type float16
```

`--language auto-detect` (the default) lets the model detect the language, and
`--speaker-count 0` (the default) detects the number of speakers. `--device` is
`cpu` (default) or `gpu`; `--compute-type` is `int8` (default), `float16` or
`float32`. Run `uv run aTrain_core transcribe --help` for all options.

Transcripts are saved in `Documents\aTrain\transcriptions` (Windows) or
`~/Documents/aTrain/transcriptions`, as plain text, text with timestamps,
MAXQDA and NVivo text formats, SRT subtitles and JSON.

Manage models:

```bash
uv run aTrain init                # download the required models
uv run aTrain_core load <MODEL>   # download one model
uv run aTrain_core remove <MODEL> # delete one model
```

### Models offered

| Model                   | Languages                | Licence    | Size    |
| ----------------------- | ------------------------ | ---------- | ------- |
| `large-v3`              | all                      | MIT        | 3.09 GB |
| `large-v3-turbo`        | all                      | MIT        | 1.62 GB |
| `large-v2`, `large-v1`  | all                      | MIT        | 3.09 GB |
| `medium`                | all                      | MIT        | 1.53 GB |
| `small`                 | all                      | MIT        | 486 MB  |
| `base`                  | all                      | MIT        | 148 MB  |
| `tiny`                  | all                      | MIT        | 78 MB   |
| `faster-distil-english` | English                  | MIT        | 1.52 GB |
| `large-norwegian`       | Norwegian, English       | Apache-2.0 | 6.18 GB |
| `large-swedish`         | Swedish                  | Apache-2.0 | 3.09 GB |
| `speaker-detection`     | used for speaker labels  | CC-BY-4.0  | 34 MB   |

## Documentation

- [docs/fork.md](docs/fork.md): what this fork changes, and its roadmap.
- [docs/internal-model-source.md](docs/internal-model-source.md): loading
  models from an internal source, for administrators.
- [docs/tutorials.md](docs/tutorials.md): importing transcripts into MAXQDA and
  NVivo.

The rest of the `docs/` folder comes from aTrain. Pages about installers, app
stores, code signing and verifying releases describe aTrain's official
packages and do not apply to this fork.

## Credits and licence

PolyglotXprs is based on aTrain by Armin Haberl, Jürgen Fleiß, Dominik Kowald
and Stefan Thalmann (Business Analytics and Data Science-Center, University of
Graz, and Know-Center Graz). If you use it in research, please cite their
paper:

> Haberl, A., Fleiß, J., Kowald, D., & Thalmann, S. (2024). Take the aTrain.
> Introducing an interface for the Accessible Transcription of Interviews.
> *Journal of Behavioral and Experimental Finance*.
> https://doi.org/10.1016/j.jbef.2024.100891

Licensed under the GNU Affero General Public License v3.0 or later, like
aTrain; see [LICENSE](LICENSE). The models have their own licences, listed
above.

The GIFs and icons in the interface are from [tenor](https://tenor.com/) and
[flaticon](https://www.flaticon.com/).
