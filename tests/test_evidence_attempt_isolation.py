from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from agent_task_v3 import (
    GoalKind,
    TaskGoal,
    TaskIntent,
    TaskOperation,
    TaskScope,
    TaskTarget,
    TargetKind,
    TaskV3,
)

from registries.goal_registry import (
    GoalRegistry,
    GoalSpec,
)

from registries.handler_registry import (
    HandlerApplicability,
    HandlerRegistry,
    HandlerSpec,
)

from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)

from runtime.assertions import AssertionRegistry

from runtime.execution_policy import (
    RuntimeExecutionLimits,
)

from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
)

from runtime.task_run_executor import (
    TaskRunExecutor,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


def make_task(task_id: str) -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp",
        ),
    )

    goal = TaskGoal(
        identifier=GOAL_ID,
        kind=GoalKind.OUTCOME,
        version=GOAL_VERSION,
        parameters={},
    )

    intent = TaskIntent(
        operation=TaskOperation.CHANGE,
        target=target,
        goal=goal,
    )

    return TaskV3(
        schema_version=3,
        task_id=task_id,
        description="Verify evidence isolation between attempts.",
        intent=intent,
    )


def make_executor() -> TaskRunExecutor:
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract="Add the generic component API.",
            owner="PROJECT",
        )
    )

    target_directory = TargetDirectory()

    target_directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="simulation_zero",
            scope="SimulationZero-Cpp",
        )
    )

    handler_registry = HandlerRegistry()

    handler_registry.register(
        HandlerSpec(
            handler_id=HANDLER_ID,
            goal_identifier=GOAL_ID,
            goal_version=GOAL_VERSION,
            applicability=HandlerApplicability(
                operations=(TaskOperation.CHANGE,),
            ),
        )
    )

    return TaskRunExecutor(
        goal_registry,
        target_directory,
        handler_registry,
        PreconditionEvaluator(
            PreconditionRegistry()
        ),
        AssertionRegistry(),
        runtime_execution_limits=RuntimeExecutionLimits(
            max_attempts=3,
            max_workers=2,
        ),
    )


def make_evidence_producer(label: str):
    def producer(run):
        from runtime.evidence import (
            Evidence,
            EvidenceKind,
            EvidenceProvenance,
            EvidenceStatus,
        )

        yield Evidence(
            evidence_id="evidence.attempt.1",
            task_id=run.task_id,
            kind=EvidenceKind.TEST,
            status=EvidenceStatus.VALID,
            value={
                "attempt": label,
                "task_id": run.task_id,
            },
            provenance=EvidenceProvenance(
                source_kind="test.attempt",
                source_id=label,
            ),
            timestamp=label,
        )

    return producer


def test_each_task_run_has_its_own_evidence_store() -> None:
    executor = make_executor()

    result_1 = executor.execute(
        make_task("attempt-1"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        evidence_producers=(
            make_evidence_producer("run-1"),
        ),
    )

    result_2 = executor.execute(
        make_task("attempt-2"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        evidence_producers=(
            make_evidence_producer("run-2"),
        ),
    )

    assert result_1.completed
    assert result_2.completed

    assert result_1.run.evidence is not None
    assert result_2.run.evidence is not None

    assert result_1.run.evidence is not result_2.run.evidence

    assert result_1.run.evidence.count() == 2
    assert result_2.run.evidence.count() == 2


def test_same_evidence_id_can_exist_in_different_task_runs() -> None:
    executor = make_executor()

    result_1 = executor.execute(
        make_task("attempt-1"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        evidence_producers=(
            make_evidence_producer("run-1"),
        ),
    )

    result_2 = executor.execute(
        make_task("attempt-2"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        evidence_producers=(
            make_evidence_producer("run-2"),
        ),
    )

    evidence_1 = result_1.run.evidence.get(
        "evidence.attempt.1"
    )

    evidence_2 = result_2.run.evidence.get(
        "evidence.attempt.1"
    )

    assert evidence_1 is not None
    assert evidence_2 is not None

    assert evidence_1 is not evidence_2
    assert evidence_1.task_id == "attempt-1"
    assert evidence_2.task_id == "attempt-2"


def test_evidence_values_remain_bound_to_their_original_attempt() -> None:
    executor = make_executor()

    result_1 = executor.execute(
        make_task("attempt-1"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        evidence_producers=(
            make_evidence_producer("run-1"),
        ),
    )

    result_2 = executor.execute(
        make_task("attempt-2"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        evidence_producers=(
            make_evidence_producer("run-2"),
        ),
    )

    evidence_1 = result_1.run.evidence.get(
        "evidence.attempt.1"
    )

    evidence_2 = result_2.run.evidence.get(
        "evidence.attempt.1"
    )

    assert evidence_1 is not None
    assert evidence_2 is not None

    assert evidence_1.value == {
        "attempt": "run-1",
        "task_id": "attempt-1",
    }

    assert evidence_2.value == {
        "attempt": "run-2",
        "task_id": "attempt-2",
    }


def test_adding_evidence_to_one_attempt_does_not_affect_another() -> None:
    executor = make_executor()

    result_1 = executor.execute(
        make_task("attempt-1"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    result_2 = executor.execute(
        make_task("attempt-2"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
    )

    assert result_1.run.evidence is not None
    assert result_2.run.evidence is not None

    from runtime.evidence import (
        Evidence,
        EvidenceKind,
        EvidenceProvenance,
        EvidenceStatus,
    )

    extra = Evidence(
        evidence_id="evidence.extra.1",
        task_id="attempt-1",
        kind=EvidenceKind.STATE,
        status=EvidenceStatus.VALID,
        value={
            "extra": True,
        },
        provenance=EvidenceProvenance(
            source_kind="test",
            source_id="isolation",
        ),
        timestamp="extra",
    )

    result_1.run.evidence.add(extra)

    assert result_1.run.evidence.count() == 2
    assert result_2.run.evidence.count() == 1

    assert result_2.run.evidence.get(
        "evidence.extra.1"
    ) is None


def test_terminal_attempt_keeps_its_evidence_after_next_run() -> None:
    executor = make_executor()

    result_1 = executor.execute(
        make_task("attempt-1"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        evidence_producers=(
            make_evidence_producer("run-1"),
        ),
    )

    assert result_1.completed
    assert result_1.run.terminal
    assert result_1.run.evidence is not None

    evidence_1 = result_1.run.evidence.get(
        "evidence.attempt.1"
    )

    assert evidence_1 is not None

    result_2 = executor.execute(
        make_task("attempt-2"),
        handlers={
            HANDLER_ID: lambda step: None,
        },
        evidence_producers=(
            make_evidence_producer("run-2"),
        ),
    )

    assert result_2.completed
    assert result_2.run.terminal
    assert result_2.run.evidence is not None

    assert result_1.run.evidence.get(
        "evidence.attempt.1"
    ) is evidence_1

    assert (
        result_1.run.evidence.get(
            "evidence.attempt.1"
        ).task_id
        == "attempt-1"
    )
