# About PolyglotXprs

> **Status: untested base build, published for testing only.** It has passed
> the automated tests but has not yet been tried on Windows or with real
> recordings. Do not use it for real or sensitive audio yet.

PolyglotXprs is a fork of [aTrain](https://github.com/JuergenFleiss/aTrain)
by the Business Analytics and Data Science-Center, University of Graz
(AGPL-3.0), for anyone who needs fully offline transcription. It runs on a
single computer as upstream does, and adds an option for organisations to load
models once from their own internal source. Every model it offers is under a
permissive open-source licence, so it can be used privately, commercially or
within an organisation without separate licence agreements. It is not
affiliated with or endorsed by the aTrain team.

The fork tracks upstream's `develop` branch and keeps its own changes small
and contained, so they can be offered back upstream where they are generally
useful.

## Changes from upstream

### Phase 1 (this branch)

- **Internal model source.** `ATRAIN_MODEL_SOURCE` points aTrain at a network
  share or plain web server; Hugging Face is then never contacted, not even for
  the reachability check. Files are verified against the hashes pinned in
  `models.json`. Implements upstream proposal #322. See
  [internal-model-source.md](internal-model-source.md).
  Code: `aTrain_core/model_source.py`, a branch in
  `load_resources.download_model()`, and the Models page in
  `aTrain/utils/models.py`.
- **CrisperWhisper removed from the model list.** Its weights are licensed for
  non-commercial research only (`LicenseRef-Nyra-NonCommercial-Research`).
  The backend code stays, so merges from upstream remain simple, but the model
  cannot be selected or downloaded.
- **Licence policy test.** `tests/unit/test_fork_license_policy.py` fails if
  `models.json` lists a model whose licence is not MIT, Apache-2.0, BSD or
  CC-BY-4.0.

### Planned

- **Phase 2: more engines.** Rebase upstream's `feature_qwen3models` branch
  (Qwen3-ASR 0.6B and 1.7B) and add NVIDIA Parakeet TDT v3 through the
  Transformers version aTrain already pins.
- **Phase 3: per-speaker-turn routing.** Detect speakers first, identify the
  language of each speaker turn, and transcribe each turn with the most
  accurate installed model for that language, falling back to Whisper
  large-v3. This also lifts the 11-language limit of the Qwen3 backend, which
  comes from its word-timestamp aligner.
- **Phase 4: review step.** A transcript review and correction view, with
  playback linked to timestamps, so a person checks each transcript before it
  is used.

## Keeping up with upstream

```bash
git remote add upstream https://github.com/JuergenFleiss/aTrain.git
git fetch upstream
git merge upstream/develop
uv run --no-sync pytest tests/unit   # includes the licence policy test
```
