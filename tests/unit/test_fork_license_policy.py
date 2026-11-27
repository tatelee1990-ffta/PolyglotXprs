"""Licence policy for the models this fork offers.

The fork offers only models under permissive open-source licences, so it can
be used privately, commercially or within an organisation without further
agreements. Upstream
aTrain also offers models under research-only or non-commercial licences
(CrisperWhisper). This test fails if a merge from upstream brings such a model
back into models.json, so the decision to offer it has to be made explicitly.
"""

import json
from importlib.resources import files

# SPDX identifiers that allow internal use, modification and redistribution.
# Attribution-only obligations (CC-BY-4.0) are met by the SBOM and licence files.
ALLOWED_LICENCES = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC-BY-4.0",
}


def shipped_models() -> dict:
    return json.loads(files("aTrain_core.data").joinpath("models.json").read_text())


def test_every_model_has_an_allowed_licence():
    disallowed = {
        name: info.get("license")
        for name, info in shipped_models().items()
        if info.get("license") not in ALLOWED_LICENCES
    }
    assert not disallowed, (
        "models.json offers models whose licence is not on the fork's allow list: "
        f"{disallowed}. Remove them or extend ALLOWED_LICENCES after a licence review."
    )


def test_crisperwhisper_is_not_offered():
    assert not any("crisper" in name.lower() for name in shipped_models())
