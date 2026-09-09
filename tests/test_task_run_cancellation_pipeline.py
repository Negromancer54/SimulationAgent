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
    TaskV3,
    TargetKind,
)

from registries.goal_registry import (
    GoalRegistry,
    GoalSpec,
)
from registries.handler_registry import (
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

from runtime.assertions import (
    AssertionRegistry,
)
from runtime.cancellation import (
    CancellationToken,
)
from runtime.execution import (
    ExecutionResult,
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlan,
    PlanStatus,
)
from runtime.preconditions import (
    PreconditionEvaluator,
    PreconditionRegistry,
)
from runtime.execution_policy import (
    RuntimeExecutionLimits,
)
from runtime.task_run import (
    TaskPhase,
    TaskStatus,
)
from runtime.task_run_executor import (
    TaskRunExecutor,
)


def make_task() -> TaskV3:
    return TaskV3(
        schema_version=3,
        task_id="task-run-cancellation-pipeline-test",
        description="TaskRun cancellation pipeline test.",
        intent=TaskIntent(
            operation=TaskOperation.CHANGE,
            target=TaskTarget(
                kind=TargetKind.PROJECT,
                identifier="project",
                scope=TaskScope(
                    project="SimulationZero-Cpp"
                ),
            ),
            goal=TaskGoal(
                kind=GoalKind.OUTCOME,
                identifier="test.goal",
                version=1,
                parameters={},
            ),
        ),
    )


def make_executor(
    execution_runtime=None,
) -> TaskRunExecutor:
    goal_registry = GoalRegistry()

    goal_registry.register(
        GoalSpec(
            identifier="test.goal",
            kind=GoalKind.OUTCOME,
            version=1,
        )
    )

    target_directory = TargetDirectory()

    target_directory.register(
        TargetRecord(
            kind=TargetKind.PROJECT,
            identifier="project",
            scope="SimulationZero-Cpp",
        )
    )

    handler_registry = HandlerRegistry()

    handler_registry.register(
        HandlerSpec(
            handler_id="handler.test",
            goal_identifier="test.goal",
            goal_version=1,
        )
    )

    precondition_registry = PreconditionRegistry()

    return TaskRunExecutor(
        goal_registry=goal_registry,
        target_directory=target_directory,
        handler_registry=handler_registry,
        precondition_evaluator=PreconditionEvaluator(
            precondition_registry
        ),
        assertion_registry=AssertionRegistry(),
        execution_runtime=execution_runtime,
        runtime_execution_limits=RuntimeExecutionLimits(),
    )


def test_cancelled_before_execution_reaches_task_run():
    token = CancellationToken()
    token.cancel()

    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1

    result = make_executor().execute(
        make_task(),
        handlers={
            "handler.test": handler,
        },
        cancellation_token=token,
    )

    assert result.completed is False
    assert result.run.execution is not None

    assert (
        result.run.execution.status
        is ExecutionStatus.CANCELLED
    )

    assert result.run.task_status is (
        TaskStatus.CANCELLED
    )

    assert result.run.phase is (
        TaskPhase.EXECUTING
    )

    assert result.run.outcome is not None
    assert calls == 0


def test_cancellation_token_is_forwarded_to_execution_runtime():
    class RecordingRuntime:
        def __init__(self):
            self.received_token = None

        def execute(
            self,
            plan,
            preconditions,
            handlers,
            policy=None,
            cancellation_token=None,
        ):
            self.received_token = cancellation_token

            return ExecutionResult(
                plan=plan,
                status=ExecutionStatus.CANCELLED,
                completed_steps=(),
                failed_step=None,
                step_results=(),
                message="cancelled by test runtime",
                policy=policy,
                schedule=None,
            )

    runtime = RecordingRuntime()
    token = CancellationToken()

    result = make_executor(
        execution_runtime=runtime,
    ).execute(
        make_task(),
        handlers={
            "handler.test": lambda step: None,
        },
        cancellation_token=token,
    )

    assert runtime.received_token is token

    assert result.completed is False
    assert result.run.execution is not None

    assert (
        result.run.execution.status
        is ExecutionStatus.CANCELLED
    )

    assert result.run.task_status is (
        TaskStatus.CANCELLED
    )


def test_cancellation_does_not_enter_post_execution():
    token = CancellationToken()
    token.cancel()

    post_execution_called = False

    def producer(run):
        nonlocal post_execution_called
        post_execution_called = True
        return ()

    result = make_executor().execute(
        make_task(),
        handlers={
            "handler.test": lambda step: None,
        },
        evidence_producers=(
            producer,
        ),
        cancellation_token=token,
    )

    assert result.completed is False
    assert result.run.task_status is (
        TaskStatus.CANCELLED
    )

    assert result.run.phase is (
        TaskPhase.EXECUTING
    )

    assert post_execution_called is False


def test_without_cancellation_token_existing_success_path_is_unchanged():
    calls = 0

    def handler(step):
        nonlocal calls
        calls += 1

    result = make_executor().execute(
        make_task(),
        handlers={
            "handler.test": handler,
        },
    )

    assert result.completed is True
    assert result.run.task_status is (
        TaskStatus.SUCCEEDED
    )

    assert result.run.phase is (
        TaskPhase.COMPLETED
    )

    assert calls == 1


def test_invalid_cancellation_token_is_rejected():
    try:
        make_executor().execute(
            make_task(),
            handlers={
                "handler.test": lambda step: None,
            },
            cancellation_token=object(),
        )
    except TypeError:
        return

    raise AssertionError(
        "Invalid cancellation token must be rejected."
    )


TESTS = [
    test_cancelled_before_execution_reaches_task_run,
    test_cancellation_token_is_forwarded_to_execution_runtime,
    test_cancellation_does_not_enter_post_execution,
    test_without_cancellation_token_existing_success_path_is_unchanged,
    test_invalid_cancellation_token_is_rejected,
]


def main():
    print("=" * 70)
    print("TASK RUN CANCELLATION PIPELINE TESTS")
    print("=" * 70)

    passed = 0

    for test in TESTS:
        try:
            test()
            print(
                f"[PASS] {test.__name__}"
            )
            passed += 1
        except Exception as exc:
            print(
                f"[FAIL] {test.__name__}"
            )
            print(
                f"       {type(exc).__name__}: {exc}"
            )

    print()
    print(
        f"Tests: {passed}/{len(TESTS)}"
    )

    if passed == len(TESTS):
        print(
            "TASK RUN CANCELLATION PIPELINE: PASS"
        )
    else:
        print(
            "TASK RUN CANCELLATION PIPELINE: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())