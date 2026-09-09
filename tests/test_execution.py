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
from registries.handler_resolver import (
    HandlerRuntimeContext,
)
from registries.target_directory import (
    TargetDirectory,
    TargetRecord,
)
from runtime.execution import (
    ExecutionResult,
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlanner,
    PlanStatus,
)
from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
    PreconditionsResult,
)
from runtime.task_resolution import (
    TaskResolver,
)


GOAL_ID = "component.add_generic_api"
GOAL_VERSION = 1
HANDLER_ID = "change.handler"


def make_task() -> TaskV3:
    target = TaskTarget(
        kind=TargetKind.PROJECT,
        identifier="simulation_zero",
        scope=TaskScope(
            project="SimulationZero-Cpp"
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
        task_id="execution-test",
        description="Execute a planned task.",
        intent=intent,
    )


def make_resolution_and_plan():
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier=GOAL_ID,
            kind=GoalKind.OUTCOME,
            version=GOAL_VERSION,
            semantic_contract=(
                "Add the generic component API."
            ),
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
                operations=(TaskOperation.CHANGE,)
            ),
        )
    )

    resolver = TaskResolver(
        goal_registry,
        target_directory,
        handler_registry,
    )

    resolution = resolver.resolve(
        make_task(),
        HandlerRuntimeContext(),
    )

    plan = ExecutionPlanner().build(resolution)

    return resolution, plan


def make_satisfied_preconditions() -> PreconditionsResult:
    registry = PreconditionRegistry()
    evaluator = PreconditionEvaluator(registry)

    # No preconditions are present in this task.
    # For this runtime contract, an empty set is represented as
    # "no preconditions supplied"; execution tests below explicitly
    # use a synthetic satisfied result where needed.
    return PreconditionsResult(
        evaluations=(
        ),
        message="Synthetic satisfied preconditions for execution test.",
    )


def make_explicitly_satisfied_preconditions() -> PreconditionsResult:
    from agent_task_v3 import Precondition

    registry = PreconditionRegistry()

    registry.register(
        "runtime.ready",
        1,
        lambda precondition, context:
            __import__(
                "runtime.preconditions",
                fromlist=["PreconditionStatus"],
            ).PreconditionStatus.SATISFIED,
    )

    evaluator = PreconditionEvaluator(registry)

    precondition = Precondition(
        id="pc.runtime.ready",
        kind="STATE",
        identifier="runtime.ready",
        version=1,
        parameters={},
    )

    task = make_task()

    task = TaskV3(
        schema_version=task.schema_version,
        task_id=task.task_id,
        description=task.description,
        intent=task.intent,
        preconditions=(precondition,),
    )

    return evaluator.evaluate(task)


def test_successful_execution() -> None:
    resolution, plan = make_resolution_and_plan()

    assert resolution.resolved
    assert plan.status is PlanStatus.READY

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    result = ExecutionRuntime().execute(
        plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: handler},
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.succeeded
    assert result.completed_steps == ("step.1",)
    assert result.failed_step is None
    assert calls == ["step.1"]


def test_preconditions_are_checked_before_handler() -> None:
    _, plan = make_resolution_and_plan()

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    preconditions = make_explicitly_satisfied_preconditions()

    # Construct an explicitly failed result without invoking a handler.
    from runtime.preconditions import (
        PreconditionEvaluation,
        PreconditionScope,
        PreconditionStatus,
    )

    failed = PreconditionsResult(
        evaluations=(
            PreconditionEvaluation(
                precondition_id="pc.runtime.ready",
                scope=PreconditionScope.RUNTIME_SAFETY,
                status=PreconditionStatus.FAILED,
                message="Runtime is not ready.",
            ),
        ),
    )

    result = ExecutionRuntime().execute(
        plan,
        failed,
        {HANDLER_ID: handler},
    )

    assert result.status is ExecutionStatus.BLOCKED
    assert result.completed_steps == ()
    assert result.failed_step is None
    assert calls == []
    assert "blocked" in result.message.lower()


def test_missing_handler_is_infrastructure_error() -> None:
    _, plan = make_resolution_and_plan()

    result = ExecutionRuntime().execute(
        plan,
        make_satisfied_preconditions(),
        {},
    )

    assert (
        result.status
        is ExecutionStatus.INFRASTRUCTURE_ERROR
    )
    assert result.completed_steps == ()
    assert result.failed_step == "step.1"


def test_handler_failure_is_execution_failure() -> None:
    _, plan = make_resolution_and_plan()

    def handler(step):
        raise RuntimeError("handler failure")

    result = ExecutionRuntime().execute(
        plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: handler},
    )

    assert result.status is ExecutionStatus.FAILED
    assert result.failed_step == "step.1"
    assert result.completed_steps == ()
    assert "RuntimeError" in result.message


def test_cancelled_execution_is_distinct() -> None:
    _, plan = make_resolution_and_plan()

    def handler(step):
        raise KeyboardInterrupt()

    result = ExecutionRuntime().execute(
        plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: handler},
    )

    assert result.status is ExecutionStatus.CANCELLED
    assert result.failed_step == "step.1"
    assert result.completed_steps == ()


def test_execution_order_is_deterministic() -> None:
    _, plan = make_resolution_and_plan()

    calls_a: list[str] = []
    calls_b: list[str] = []

    def handler_a(step):
        calls_a.append(step.step_id)

    def handler_b(step):
        calls_b.append(step.step_id)

    runtime = ExecutionRuntime()

    result_a = runtime.execute(
        plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: handler_a},
    )

    result_b = runtime.execute(
        plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: handler_b},
    )

    assert result_a.status is ExecutionStatus.SUCCEEDED
    assert result_b.status is ExecutionStatus.SUCCEEDED
    assert calls_a == calls_b
    assert result_a.completed_steps == result_b.completed_steps


def test_failed_step_stops_execution() -> None:
    _, plan = make_resolution_and_plan()

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)
        raise RuntimeError("stop")

    result = ExecutionRuntime().execute(
        plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: handler},
    )

    assert result.status is ExecutionStatus.FAILED
    assert calls == ["step.1"]
    assert len(result.step_results) == 1


def test_execution_preserves_plan_identity() -> None:
    _, plan = make_resolution_and_plan()

    result = ExecutionRuntime().execute(
        plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: lambda step: None},
    )

    assert result.plan is plan


def test_execution_does_not_mutate_plan() -> None:
    _, plan = make_resolution_and_plan()

    before = plan

    ExecutionRuntime().execute(
        plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: lambda step: None},
    )

    after = plan

    assert before is after
    assert before == after


def test_invalid_plan_never_calls_handler() -> None:
    _, plan = make_resolution_and_plan()

    from runtime.execution_plan import ExecutionPlan

    invalid_plan = ExecutionPlan(
        status=PlanStatus.INVALID_RESOLUTION,
        task=plan.task,
    )

    calls: list[str] = []

    def handler(step):
        calls.append(step.step_id)

    result = ExecutionRuntime().execute(
        invalid_plan,
        make_satisfied_preconditions(),
        {HANDLER_ID: handler},
    )

    assert (
        result.status
        is ExecutionStatus.INFRASTRUCTURE_ERROR
    )
    assert calls == []


def test_empty_plan_succeeds_without_handlers() -> None:
    _, plan = make_resolution_and_plan()

    from runtime.execution_plan import ExecutionPlan

    empty_plan = ExecutionPlan(
        status=PlanStatus.READY,
        task=plan.task,
        steps=(),
    )

    result = ExecutionRuntime().execute(
        empty_plan,
        make_satisfied_preconditions(),
        {},
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.completed_steps == ()
    assert result.step_results == ()


def test_runtime_rejects_invalid_input_types() -> None:
    runtime = ExecutionRuntime()

    try:
        runtime.execute(
            object(),
            make_satisfied_preconditions(),
            {},
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Invalid plan type was accepted."
        )

    _, plan = make_resolution_and_plan()

    try:
        runtime.execute(
            plan,
            object(),
            {},
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Invalid preconditions type was accepted."
        )


def main() -> int:
    tests = [
        test_successful_execution,
        test_preconditions_are_checked_before_handler,
        test_missing_handler_is_infrastructure_error,
        test_handler_failure_is_execution_failure,
        test_cancelled_execution_is_distinct,
        test_execution_order_is_deterministic,
        test_failed_step_stops_execution,
        test_execution_preserves_plan_identity,
        test_execution_does_not_mutate_plan,
        test_invalid_plan_never_calls_handler,
        test_empty_plan_succeeds_without_handlers,
        test_runtime_rejects_invalid_input_types,
    ]

    print("=" * 70)
    print("EXECUTION RUNTIME TESTS")
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
        print("EXECUTION RUNTIME: PASS")
    else:
        print("EXECUTION RUNTIME: FAIL")

    print("=" * 70)

    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())