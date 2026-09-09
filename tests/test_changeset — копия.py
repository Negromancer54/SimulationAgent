from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    ChangeKind,
    ChangeSetMode,
    ExpectedCondition,
    ExpectedKind,
)
from runtime.changeset import (
    ChangeRecord,
    ChangeSetEvaluationStatus,
    ChangeSetEvaluator,
)
from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceStore,
)


TASK_ID = "task-changeset-test"


def make_store() -> EvidenceStore:
    return EvidenceStore(TASK_ID)


def make_evidence(
    changes,
    evidence_id: str = "evidence.changes",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        task_id=TASK_ID,
        kind=EvidenceKind.CHANGESET,
        status=EvidenceStatus.VALID,
        value={
            "changes": changes,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="changeset-source",
        ),
        timestamp="2026-09-08T17:00:00+03:00",
    )


def path_change(
    kind: ChangeKind,
    path: str,
) -> dict:
    return {
        "kind": kind.value,
        "path": path,
    }


def rename_change(
    old_path: str,
    new_path: str,
) -> dict:
    return {
        "kind": ChangeKind.RENAMED.value,
        "old_path": old_path,
        "new_path": new_path,
    }


def make_expected(
    mode: ChangeSetMode,
    required=None,
    allowed=None,
    forbidden=None,
    expected_id: str = "expected.changes",
) -> ExpectedCondition:
    return ExpectedCondition(
        id=expected_id,
        kind=ExpectedKind.CHANGESET,
        identifier="project.changes",
        version=1,
        parameters={
            "mode": mode.value,
            "required": required or [],
            "allowed": allowed or [],
            "forbidden": forbidden or [],
        },
    )


def test_constrained_required_change_is_satisfied() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                path_change(
                    ChangeKind.ADDED,
                    "src/new_file.cpp",
                ),
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.CONSTRAINED,
        required=[
            path_change(
                ChangeKind.ADDED,
                "src/new_file.cpp",
            )
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.SATISFIED
    )
    assert result.satisfied


def test_constrained_missing_required_change_fails() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                path_change(
                    ChangeKind.MODIFIED,
                    "src/main.cpp",
                ),
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.CONSTRAINED,
        required=[
            path_change(
                ChangeKind.ADDED,
                "src/new_file.cpp",
            )
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.NOT_SATISFIED
    )


def test_forbidden_change_fails() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                path_change(
                    ChangeKind.DELETED,
                    "src/danger.cpp",
                ),
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.CONSTRAINED,
        forbidden=[
            path_change(
                ChangeKind.DELETED,
                "src/danger.cpp",
            )
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.NOT_SATISFIED
    )


def test_allowed_set_rejects_outside_change() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                path_change(
                    ChangeKind.MODIFIED,
                    "src/main.cpp",
                ),
                path_change(
                    ChangeKind.MODIFIED,
                    "src/other.cpp",
                ),
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.CONSTRAINED,
        allowed=[
            path_change(
                ChangeKind.MODIFIED,
                "src/main.cpp",
            ),
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.NOT_SATISFIED
    )


def test_allowed_set_accepts_subset() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                path_change(
                    ChangeKind.MODIFIED,
                    "src/main.cpp",
                ),
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.CONSTRAINED,
        allowed=[
            path_change(
                ChangeKind.MODIFIED,
                "src/main.cpp",
            ),
            path_change(
                ChangeKind.MODIFIED,
                "src/helper.cpp",
            ),
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert result.satisfied


def test_exact_changeset_is_satisfied() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                path_change(
                    ChangeKind.ADDED,
                    "src/new.cpp",
                ),
                path_change(
                    ChangeKind.MODIFIED,
                    "src/main.cpp",
                ),
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.EXACT,
        required=[
            path_change(
                ChangeKind.ADDED,
                "src/new.cpp",
            ),
            path_change(
                ChangeKind.MODIFIED,
                "src/main.cpp",
            ),
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.SATISFIED
    )


def test_exact_extra_change_fails() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                path_change(
                    ChangeKind.ADDED,
                    "src/new.cpp",
                ),
                path_change(
                    ChangeKind.MODIFIED,
                    "src/main.cpp",
                ),
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.EXACT,
        required=[
            path_change(
                ChangeKind.ADDED,
                "src/new.cpp",
            ),
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.NOT_SATISFIED
    )


def test_exact_missing_change_fails() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                path_change(
                    ChangeKind.ADDED,
                    "src/new.cpp",
                ),
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.EXACT,
        required=[
            path_change(
                ChangeKind.ADDED,
                "src/new.cpp",
            ),
            path_change(
                ChangeKind.MODIFIED,
                "src/main.cpp",
            ),
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.NOT_SATISFIED
    )


def test_rename_is_one_change_record() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                rename_change(
                    "src/old.cpp",
                    "src/new.cpp",
                )
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.EXACT,
        required=[
            rename_change(
                "src/old.cpp",
                "src/new.cpp",
            )
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert result.satisfied
    assert len(result.actual_changes) == 1
    assert (
        result.actual_changes[0].kind
        is ChangeKind.RENAMED
    )
    assert result.actual_changes[0].old_path == (
        "src/old.cpp"
    )
    assert result.actual_changes[0].new_path == (
        "src/new.cpp"
    )


def test_rename_different_destination_fails_exact_match() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [
                rename_change(
                    "src/old.cpp",
                    "src/new.cpp",
                )
            ]
        )
    )

    expected = make_expected(
        ChangeSetMode.EXACT,
        required=[
            rename_change(
                "src/old.cpp",
                "src/other.cpp",
            )
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.NOT_SATISFIED
    )


def test_empty_changeset_can_satisfy_exact_empty_expectation() -> None:
    store = make_store()

    store.add(
        make_evidence([])
    )

    expected = make_expected(
        ChangeSetMode.EXACT,
        required=[],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert result.satisfied


def test_missing_changeset_evidence_is_unavailable() -> None:
    store = make_store()

    expected = make_expected(
        ChangeSetMode.CONSTRAINED,
        required=[],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.UNAVAILABLE
    )


def test_invalid_changeset_evidence_is_ignored() -> None:
    store = make_store()

    store.add(
        Evidence(
            evidence_id="invalid",
            task_id=TASK_ID,
            kind=EvidenceKind.CHANGESET,
            status=EvidenceStatus.INVALID,
            value={
                "changes": [
                    path_change(
                        ChangeKind.ADDED,
                        "src/new.cpp",
                    )
                ]
            },
            provenance=EvidenceProvenance(
                source_kind="test",
                source_id="invalid",
            ),
            timestamp="2026-09-08T17:00:00+03:00",
        )
    )

    expected = make_expected(
        ChangeSetMode.CONSTRAINED,
        required=[
            path_change(
                ChangeKind.ADDED,
                "src/new.cpp",
            )
        ],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.UNAVAILABLE
    )


def test_malformed_changeset_evidence_returns_error() -> None:
    store = make_store()

    store.add(
        Evidence(
            evidence_id="malformed",
            task_id=TASK_ID,
            kind=EvidenceKind.CHANGESET,
            status=EvidenceStatus.VALID,
            value={
                "changes": [
                    {
                        "kind": "NOT_A_CHANGE",
                        "path": "src/file.cpp",
                    }
                ]
            },
            provenance=EvidenceProvenance(
                source_kind="test",
                source_id="malformed",
            ),
            timestamp="2026-09-08T17:00:00+03:00",
        )
    )

    expected = make_expected(
        ChangeSetMode.CONSTRAINED,
        required=[],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.ERROR
    )


def test_malformed_expected_parameters_return_error() -> None:
    store = make_store()

    expected = ExpectedCondition(
        id="expected.bad",
        kind=ExpectedKind.CHANGESET,
        identifier="project.changes",
        version=1,
        parameters={
            "required": [],
        },
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert (
        result.status
        is ChangeSetEvaluationStatus.ERROR
    )


def test_evaluation_preserves_evidence_ids() -> None:
    store = make_store()

    store.add(
        make_evidence(
            [],
            evidence_id="evidence.1",
        )
    )

    expected = make_expected(
        ChangeSetMode.EXACT,
        required=[],
    )

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    assert result.evidence_ids == (
        "evidence.1",
    )


def test_evaluation_does_not_modify_store() -> None:
    store = make_store()

    evidence = make_evidence(
        [
            path_change(
                ChangeKind.ADDED,
                "src/new.cpp",
            )
        ]
    )

    store.add(evidence)

    expected = make_expected(
        ChangeSetMode.EXACT,
        required=[
            path_change(
                ChangeKind.ADDED,
                "src/new.cpp",
            )
        ],
    )

    before = store.list()

    result = ChangeSetEvaluator.evaluate(
        expected,
        store,
    )

    after = store.list()

    assert result.satisfied
    assert before == after
    assert store.get(evidence.evidence_id) is evidence


def test_change_records_are_immutable() -> None:
    record = ChangeRecord(
        kind=ChangeKind.ADDED,
        path="src/new.cpp",
    )

    try:
        record.path = "src/other.cpp"
    except Exception:
        return

    raise AssertionError(
        "ChangeRecord was mutable."
    )


def main() -> int:
    tests = [
        test_constrained_required_change_is_satisfied,
        test_constrained_missing_required_change_fails,
        test_forbidden_change_fails,
        test_allowed_set_rejects_outside_change,
        test_allowed_set_accepts_subset,
        test_exact_changeset_is_satisfied,
        test_exact_extra_change_fails,
        test_exact_missing_change_fails,
        test_rename_is_one_change_record,
        test_rename_different_destination_fails_exact_match,
        test_empty_changeset_can_satisfy_exact_empty_expectation,
        test_missing_changeset_evidence_is_unavailable,
        test_invalid_changeset_evidence_is_ignored,
        test_malformed_changeset_evidence_returns_error,
        test_malformed_expected_parameters_return_error,
        test_evaluation_preserves_evidence_ids,
        test_evaluation_does_not_modify_store,
        test_change_records_are_immutable,
    ]

    print("=" * 70)
    print("CHANGESET EVALUATION TESTS")
    print("=" * 70)

    passed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test.__name__}")
            print(
                f"       {type(exc).__name__}: {exc}"
            )

    print()
    print(f"Tests: {passed}/{len(tests)}")

    if passed == len(tests):
        print("CHANGESET EVALUATION: PASS")
    else:
        print("CHANGESET EVALUATION: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())