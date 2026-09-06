#!/usr/bin/env python3
"""Apply one B2.5-P14 controlled defect to the working tree.

The P14 negative controls have to modify *real governing state*: the actual
simulation service, the actual explanation service, the actual projection
registry. Inlining those mutations as heredocs inside a workflow makes them
invisible to review and impossible to run locally, so they live here as named,
single-purpose transformations.

Each mutation asserts its own anchor before writing. A control that silently
became a no-op because the code moved would produce a green gate that measured
nothing -- which is the exact failure mode the P14 falsifiers exist to rule out.
The caller restores the pristine file afterwards and checks ``git diff
--exit-code``, so nothing here needs an undo path.

Usage::

    python scripts/ci/_b25_p14_controlled_defect.py apply <defect-name>
    python scripts/ci/_b25_p14_controlled_defect.py list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SIMULATION_SERVICE = REPO_ROOT / "backend/app/simulation/service.py"
EXPLANATION_SERVICE = REPO_ROOT / "backend/app/explanation/service.py"
PROFILE_REGISTRY = REPO_ROOT / "contracts/trust-api/projection-profiles.v1.yaml"
PRODUCTION_DOCKERFILE = REPO_ROOT / "backend/Dockerfile"
EXPLANATION_CONSERVATION = REPO_ROOT / "backend/app/explanation/conservation.py"
EXPLANATION_TEMPLATES = REPO_ROOT / "backend/app/explanation/templates.py"
SIMULATION_PERSISTENCE = REPO_ROOT / "backend/app/simulation/persistence.py"
REQUESTER_IDENTITY = REPO_ROOT / "backend/app/simulation/requester_identity.py"
CONSTRUCTION_AUTHORITY = REPO_ROOT / "backend/app/core/construction_authority.py"

DEFAULT_LLM_PROFILE_ID = "llm_explanation_projection_safe"


def _replace_once(path: Path, anchor: str, replacement: str, *, what: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(anchor) != 1:
        raise SystemExit(
            f"controlled defect '{what}' cannot be applied: the anchor "
            f"{anchor!r} appears {text.count(anchor)} times in {path.name}. "
            "The control must be repaired rather than allowed to no-op."
        )
    path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")


def platform_write() -> None:
    """Gate 9: put a platform-write client one import away from B2.8."""
    _replace_once(
        SIMULATION_SERVICE,
        "import uuid\n",
        "import uuid\n\nfrom app.services import platform_connections  # NC-P14-01\n",
        what="platform_write",
    )


def second_solver_caller() -> None:
    """Gate 6: give the solver a caller outside the admission conjunction."""
    _replace_once(
        EXPLANATION_SERVICE,
        "from typing import Any, Mapping",
        "from typing import Any, Mapping\n\n"
        "from app.simulation.solver import allocate_budget  # NC-P14-02",
        what="second_solver_caller",
    )


def _load_registry() -> dict:
    return yaml.safe_load(PROFILE_REGISTRY.read_text(encoding="utf-8"))


def _write_registry(document: dict) -> None:
    PROFILE_REGISTRY.write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
    )


def remove_required_profile() -> None:
    """P14-G1: delete one of the four required projection profiles."""
    document = _load_registry()
    before = len(document["profiles"])
    document["profiles"] = [
        profile
        for profile in document["profiles"]
        if profile["profile_id"] != "optimization_projection_safe"
    ]
    if len(document["profiles"]) != before - 1:
        raise SystemExit(
            "controlled defect 'remove_required_profile' cannot be applied: "
            "optimization_projection_safe was already absent"
        )
    _write_registry(document)


def untrusted_label_in_llm_profile() -> None:
    """P14-G2: seat a provider-controlled label in the default LLM projection."""
    document = _load_registry()
    for profile in document["profiles"]:
        if profile["profile_id"] == DEFAULT_LLM_PROFILE_ID:
            profile["fields"].append(
                {
                    "path": "untrusted_display_data.display_text",
                    "position": "display_only",
                    "trust_class": "untrusted_display_label",
                }
            )
            _write_registry(document)
            return
    raise SystemExit(
        "controlled defect 'untrusted_label_in_llm_profile' cannot be applied: "
        f"{DEFAULT_LLM_PROFILE_ID} is missing from the registry"
    )


def narrow_contract_copy_layer() -> None:
    """Gate 4: make the production image ship a policy the tree does not declare.

    A Dockerfile edit is invisible to every host-run gate, which is exactly why
    Gate 4 names it as its active falsifier: the container resolves one contract
    while the tests adjudicate another, and nothing on the host can tell.
    """

    _replace_once(
        PRODUCTION_DOCKERFILE,
        "COPY contracts/trust-api /app/contracts/trust-api\n",
        "COPY contracts/trust-api/trust-envelope.v2.yaml"
        " /app/contracts/trust-api/trust-envelope.v2.yaml\n",
        what="narrow_contract_copy_layer",
    )


def weaken_narrative_derivation() -> None:
    """Exit Gate 2: weaken the semantic safety *relation*, not a phrase list.

    Corrective IV replaced the open-world causal denylist with a closed
    derivation law: a narrative is admissible only as the exact join of
    registered frame instances. This control weakens that relation from equality
    to prefix acceptance, which is the smallest change that re-opens a position
    for an arbitrary proposition -- an attacker appends one sentence to a
    perfectly conserved narrative and the artifact is accepted again.

    Nothing here removes a regex or a listed phrase, which is what the directive
    requires of this falsifier: the gate must go red because the conservation
    relation was weakened, not because an example stopped being recognised.
    """

    anchor = (
        "    if result.narrative != expected_narrative:\n"
        '        violations.append("narrative_not_derived_from_claims")\n'
    )
    replacement = (
        "    if not result.narrative.startswith(expected_narrative):  # NC-P14-08\n"
        '        violations.append("narrative_not_derived_from_claims")\n'
    )
    _replace_once(
        EXPLANATION_CONSERVATION,
        anchor,
        replacement,
        what="weaken_narrative_derivation",
    )


def admit_a_causal_narrative_frame() -> None:
    """Exit Gate 2, second falsifier: admit one causal proposition to the corpus.

    The closed corpus is the boundary now, so the corpus adjudicator has to be
    load-bearing too. This seats a frame that asserts a causal relation and
    requires the frame sweep to refuse it at load -- the failure mode being a
    corpus that quietly grows a sentence nobody adjudicated.
    """

    anchor = (
        "    NarrativeTemplate(\n"
        '        template_id="policy.policy_state.v1",\n'
    )
    replacement = (
        "    NarrativeTemplate(  # NC-P14-09\n"
        '        template_id="causal.invented.v1",\n'
        "        claim_kind=CLAIM_STATUS,\n"
        '        source_path="schema_version",\n'
        '        text="This revenue was caused by {value}.",\n'
        '        value_grammar="opaque_id",\n'
        "    ),\n"
        "    NarrativeTemplate(\n"
        '        template_id="policy.policy_state.v1",\n'
    )
    _replace_once(
        EXPLANATION_TEMPLATES,
        anchor,
        replacement,
        what="admit_a_causal_narrative_frame",
    )


def caller_authored_requester_identity() -> None:
    """Corrective V Exit Gate 1: let the caller name itself again.

    The entering protected-main tree accepted
    ``requested_by='attacker:not-a-real-caller'`` because the field was text a
    writer chose. The repair makes it a *derivation* of an authenticated
    credential, performed twice by two authorities that cannot both be the
    caller: the request-entry boundary derives it, and the database re-derives
    it from the row's own foreign keys and refuses any disagreement.

    This control severs the application half -- ``persist_simulation_request``
    starts trusting an environment-supplied identity instead of the verified
    principal -- while leaving the credential lookup, the foreign keys and the
    guard intact. The suite must still go red, because the database's own
    derivation disagrees. That is the point: the two halves are each other's
    falsifier, and a control that broke only one of them would prove nothing.
    """

    anchor = (
        '                        "requested_by": requester.requested_by,\n'
        '                        "agent_client_id": requester.agent_client_id,\n'
    )
    replacement = (
        '                        "requested_by": "attacker:not-a-real-caller",'
        "  # NC-P14-10\n"
        '                        "agent_client_id": requester.agent_client_id,\n'
    )
    _replace_once(
        SIMULATION_PERSISTENCE,
        anchor,
        replacement,
        what="caller_authored_requester_identity",
    )


def unauthenticated_requester() -> None:
    """Corrective V Exit Gate 1: accept a credential without verifying it.

    ``authenticate_simulation_requester`` is the library-boundary answer to the
    audits' finding that no caller authentication existed at all. This control
    removes the constant-time secret comparison while leaving the prefix lookup,
    the revocation check and the liveness checks in place -- so a caller who
    knows only a token *prefix* is admitted. Knowing eight characters is not
    proving custody of a credential, and the suite must say so.
    """

    anchor = (
        "        if not verify_machine_token(\n"
        "            presented_token, str(token_hash), "
        'str(hash_algorithm or "sha256")\n'
        "        ):\n"
    )
    replacement = "        if False:  # NC-P14-11\n"
    _replace_once(
        REQUESTER_IDENTITY,
        anchor,
        replacement,
        what="unauthenticated_requester",
    )


def canonical_bootstrap_is_authoritative() -> None:
    """Corrective V Exit Gate 13: re-open the construction-authority question.

    The phase's answer is that ``db/schema/canonical_schema.sql`` is a
    structural reference and never a production construction route, and the
    physical expression of that is a runtime refusal keyed on the one marker a
    pg_dump cannot forge -- an ``alembic_version`` row. This control makes the
    refusal accept an unconstructed database, which is exactly the state a
    canonical bootstrap leaves behind: structurally identical, with the generic
    API principal's INSERT restored, both dedicated causal authorities holding
    nothing, and the frame corpus empty.
    """

    anchor = (
        "    if not revisions:\n"
        "        raise ConstructionAuthorityError(\n"
    )
    replacement = (
        "    if not revisions:  # NC-P14-12\n"
        '        return "unconstructed"\n'
        "    if False:\n"
        "        raise ConstructionAuthorityError(\n"
    )
    _replace_once(
        CONSTRUCTION_AUTHORITY,
        anchor,
        replacement,
        what="canonical_bootstrap_is_authoritative",
    )


DEFECTS = {
    "platform_write": platform_write,
    "second_solver_caller": second_solver_caller,
    "remove_required_profile": remove_required_profile,
    "untrusted_label_in_llm_profile": untrusted_label_in_llm_profile,
    "narrow_contract_copy_layer": narrow_contract_copy_layer,
    "weaken_narrative_derivation": weaken_narrative_derivation,
    "admit_a_causal_narrative_frame": admit_a_causal_narrative_frame,
    "caller_authored_requester_identity": caller_authored_requester_identity,
    "unauthenticated_requester": unauthenticated_requester,
    "canonical_bootstrap_is_authoritative": canonical_bootstrap_is_authoritative,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "list"))
    parser.add_argument("defect", nargs="?")
    args = parser.parse_args()

    if args.action == "list":
        for name in sorted(DEFECTS):
            print(name)
        return 0

    if not args.defect:
        parser.error("apply requires a defect name")
    try:
        mutation = DEFECTS[args.defect]
    except KeyError:
        parser.error(f"unknown defect {args.defect!r}; known: {sorted(DEFECTS)}")
    mutation()
    print(f"[b25-p14] applied controlled defect: {args.defect}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
