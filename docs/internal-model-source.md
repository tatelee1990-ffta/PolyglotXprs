# Loading models from an internal source

For administrators. With the environment variable `ATRAIN_MODEL_SOURCE` set,
aTrain downloads models only from a source inside your organisation and never
contacts Hugging Face. Once a model is on a machine, aTrain uses it without any
network access at all.

This implements the design proposed upstream in aTrain issue #322
("Proposal: load models from an internal source").

## How it works

1. IT copies the approved models once to a file share or a plain web server.
2. `ATRAIN_MODEL_SOURCE` is set on the client machines, for example by Group
   Policy.
3. When a user downloads a model on the Models page, or runs
   `aTrain_core load <model>`, aTrain fetches exactly the files that
   `models.json` lists for that model from
   `<ATRAIN_MODEL_SOURCE>/<model>/<file>`.
4. Every file is checked against the SHA-256 hash pinned in `models.json`. A
   model with a wrong file is deleted and not used.
5. From then on the model is local. Transcription makes no network requests.

The source needs no API, directory listing or login. A wrong or compromised
source cannot change the model weights, because the hashes are pinned in the
application, not fetched from the source.

## The setting

| Value                                   | Meaning                                    |
| --------------------------------------- | ------------------------------------------ |
| unset or empty                          | upstream behaviour: download from Hugging Face |
| `\\fileserver\atrain\models`            | a network share (uses the user's Windows login) |
| `D:\aTrain-models`                      | a local or mounted folder                  |
| `https://models.example.org/atrain/`    | a static web server, HTTPS recommended     |

Only `http` and `https` URLs and folder paths are accepted. Any other URL
scheme is rejected with an error.

On Windows, set it as a user or machine environment variable. With Group
Policy: *Computer Configuration → Preferences → Windows Settings →
Environment*, variable `ATRAIN_MODEL_SOURCE`. aTrain reads the variable
when a download starts, but Windows only passes new environment variables to
programs started after the change, so users may need to sign out and in again.

## Filling the source

The layout is the same as a local aTrain models folder:

```
<ATRAIN_MODEL_SOURCE>/
├── large-v3/
│   ├── config.json
│   ├── model.bin
│   └── ...
└── speaker-detection/
    ├── config.yaml
    ├── embedding/pytorch_model.bin
    └── ...
```

The simplest way to fill it:

1. On one machine with internet access and without `ATRAIN_MODEL_SOURCE` set,
   install aTrain and download the approved models (Models page, or
   `aTrain_core load large-v3` and `aTrain_core load speaker-detection`).
   aTrain verifies them against the pinned hashes during the download.
2. Copy the model folders from `Documents\aTrain\models\` to the source.

The source only needs the models your organisation offers. If a user selects a
model that is not at the source, the download fails with a message naming the
missing file and the folder where IT should put it.

`.gitattributes` files are optional: they are copied if present and skipped
if not.

## Recommended hardening

- **Block Hugging Face for aTrain as well.** Setting `HF_HUB_OFFLINE=1` next
  to `ATRAIN_MODEL_SOURCE` makes the Hugging Face library refuse all network
  access, as a second line of defence.
- **Use HTTPS** for a web source. Integrity does not depend on it (hashes are
  pinned), but it keeps the list of models users fetch private on the network.
- **Make the source read-only** for users.
- **Restrict the models offered** to those your licence review approved. This
  fork's `models.json` only lists models under MIT, Apache-2.0 or CC-BY-4.0, and
  a test (`tests/unit/test_fork_license_policy.py`) fails if a merge from
  upstream adds a model under any other licence.

## Checking a machine

- The Models page shows "Internal source (…)" as the source of every model.
- On a machine without internet access but with the source reachable,
  download a model: it must succeed.
- Disconnect the machine from all networks and transcribe a file with a model
  that is already downloaded: it must succeed.

## Limits

- Web servers that require authentication are not supported. A network share
  uses the signed-in user's Windows login.
- There is no configuration file yet; upstream tracks one in #342.
