from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from agent_task_v3 import (
    ExpectedKind,
    Precondition,
    TaskV3,
    validate_task_v3,
)
from runtime.assertions import (
    AssertionEvaluator,
    AssertionRegistry,
    AssertionResultStatus,
)

from registries.goal_registry import GoalRegistry
from registries.handler_registry import HandlerRegistry
from registries.handler_resolver import HandlerRuntimeContext
from registries.target_directory import TargetDirectory
from runtime.assertions import (
    AssertionEvaluator,
    AssertionResultStatus,
)
from runtime.changeset import (
    ChangeSetEvaluationStatus,
    ChangeSetEvaluator,
)
from runtime.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceStatus,
)
from runtime.cancellation import (
    CancellationToken,
)
from runtime.execution import (
    ExecutionRuntime,
    ExecutionStatus,
)
from runtime.execution_plan import (
    ExecutionPlanner,
    PlanStatus,
)
from runtime.expected import (
    ExpectedEvaluation,
    ExpectedEvaluationStatus,
    ExpectedEvaluator,
)
from runtime.preconditions import (
    PreconditionEvaluator,
)
from runtime.task_outcome import (
    TaskOutcomeEvaluator,
)
from runtime.task_resolution import (
    TaskResolutionStatus,
    TaskResolver,
)
from runtime.task_run import (
    TaskRun,
    TaskRunStatus,
)
from runtime.task_run_state_mapper import (
    TaskRunStateMapper,
)
from runtime.validation import (
    ValidationEvaluator,
)
from runtime.execution_policy import (
    ExecutionPolicyResolver,
    RuntimeExecutionLimits,
    ExecutionPolicyStatus,
)

from runtime.task_run import (
    TaskRun,
    TaskRunStatus,
    V3TaskPhase,
)
EvidenceProducer = Callable[
    [TaskRun],
    Iterable[Evidence],
]


@dataclass(frozen=True)
class TaskRunExecutorResult:
    run: TaskRun
    completed: bool

    @property
    def outcome(self):
        return self.run.outcome


class TaskRunExecutor:
    """
    Orchestrates one complete TaskV3 execution lifecycle.

    Runtime flow:

        VALIDATING
            в†“
        RESOLVING
            в†“
        PLANNING
            в†“
        CHECKING_PRECONDITIONS
            в†“
        EXECUTING
            в†“
        POST_EXECUTION
            в†“
        EVALUATING
            в†“
        COMPLETED / FAILED

    Expected, Assertion and ChangeSet evaluations are normalized into
    ExpectedEvaluation instances before TaskOutcome evaluation.
    """

    def __init__(
        self,
        goal_registry: GoalRegistry,
        target_directory: TargetDirectory,
        handler_registry: HandlerRegistry,
        precondition_evaluator: PreconditionEvaluator,
        assertion_registry: AssertionRegistry,
        execution_runtime: ExecutionRuntime | None = None,
        runtime_execution_limits: RuntimeExecutionLimits | None = None,
    ) -> None:
        self._resolver = TaskResolver(
            goal_registry,
            target_directory,
            handler_registry,
        )

        self._precondition_evaluator = precondition_evaluator

        self._assertion_evaluator = AssertionEvaluator(
            assertion_registry
        )

        self._planner = ExecutionPlanner()

        self._execution_runtime = (
            execution_runtime
            or ExecutionRuntime()
        )
        self._execution_policy_resolver = (
            ExecutionPolicyResolver()
        )

        self._runtime_execution_limits = (
            runtime_execution_limits
            if runtime_execution_limits is not None
            else RuntimeExecutionLimits()
        )

    @staticmethod
    def _fail_run(
        run: TaskRun,
        message: str,
    ) -> TaskRunExecutorResult:
        if not run.terminal:
            run.set_v3_phase(V3TaskPhase.RESOLUTION)
            run.transition(
                TaskRunStatus.FAILED
            )

        run.outcome = None

        return TaskRunExecutorResult(
            run=run,
            completed=False,
        )

    @staticmethod
    def _record_execution_evidence(
        run: TaskRun,
    ) -> None:
        if run.evidence is None:
            return

        execution = run.execution

        if execution is None:
            return

        evidence = Evidence(
            evidence_id="evidence.execution.1",
            task_id=run.task_id,
            kind=EvidenceKind.EXECUTION,
            status=(
                EvidenceStatus.VALID
                if execution.status is ExecutionStatus.SUCCEEDED
                else EvidenceStatus.INVALID
            ),
            value={
                "status": execution.status.value,
                "completed_steps": execution.completed_steps,
                "failed_step": execution.failed_step,
            },
            provenance=EvidenceProvenance(
                source_kind="execution.runtime",
                source_id=run.task_id,
            ),
            timestamp="runtime",
        )

        if not run.evidence.contains(
            evidence.evidence_id
        ):
            run.evidence.add(evidence)

    @staticmethod
    def _record_post_execution_evidence(
        run: TaskRun,
        producers: tuple[EvidenceProducer, ...],
    ) -> str | None:
        if run.evidence is None:
            return "TaskRun does not own an EvidenceStore."

        for producer in producers:
            try:
                produced = producer(run)
            except Exception as exc:
                return (
                    "Evidence producer failed: "
                    f"{type(exc).__name__}: {exc}"
                )

            try:
                for evidence in produced:
                    run.evidence.add(evidence)
            except Exception as exc:
                return (
                    "Produced evidence could not be stored: "
                    f"{type(exc).__name__}: {exc}"
                )

        return None

    def _evaluate_expected(
        self,
        run: TaskRun,
    ) -> str | None:
        """
        Evaluate every Expected condition and normalize all supported
        Expected kinds into ExpectedEvaluation.

        A semantic failure such as NOT_SATISFIED or UNAVAILABLE is
        preserved as an evaluation result. It is NOT an infrastructure
        failure of TaskRunExecutor.
        """

        if run.evidence is None:
            return "TaskRun does not own an EvidenceStore."

        evaluations: list[
            ExpectedEvaluation
        ] = []

        for expected in run.task.expected:
            try:
                if expected.kind in (
                    ExpectedKind.STATE,
                    ExpectedKind.TEST,
                ):
                    evaluations.append(
                        ExpectedEvaluator.evaluate_one(
                            expected,
                            run.evidence,
                        )
                    )
                    continue

                if expected.kind is ExpectedKind.ASSERTION:
                    assertion_result = (
                        self._assertion_evaluator.evaluate(
                            expected.identifier,
                            expected.version,
                            run.evidence,
                        )
                    )

                    status_map = {
                        AssertionResultStatus.PASS:
                            ExpectedEvaluationStatus.SATISFIED,
                        AssertionResultStatus.FAIL:
                            ExpectedEvaluationStatus.NOT_SATISFIED,
                        AssertionResultStatus.UNAVAILABLE:
                            ExpectedEvaluationStatus.UNAVAILABLE,
                        AssertionResultStatus.ERROR:
                            ExpectedEvaluationStatus.ERROR,
                    }

                    evaluations.append(
                        ExpectedEvaluation(
                            expected_id=expected.id,
                            kind=expected.kind,
                            status=status_map[
                                assertion_result.status
                            ],
                            evidence_ids=(
                                assertion_result.evidence_ids
                            ),
                            message=(
                                assertion_result.message
                            ),
                        )
                    )
                    continue

                if expected.kind is ExpectedKind.CHANGESET:
                    changeset_result = (
                        ChangeSetEvaluator.evaluate(
                            expected,
                            run.evidence,
                        )
                    )

                    status_map = {
                        ChangeSetEvaluationStatus.SATISFIED:
                            ExpectedEvaluationStatus.SATISFIED,
                        ChangeSetEvaluationStatus.NOT_SATISFIED:
                            ExpectedEvaluationStatus.NOT_SATISFIED,
                        ChangeSetEvaluationStatus.UNAVAILABLE:
                            ExpectedEvaluationStatus.UNAVAILABLE,
                        ChangeSetEvaluationStatus.ERROR:
                            ExpectedEvaluationStatus.ERROR,
                    }

                    evaluations.append(
                        ExpectedEvaluation(
                            expected_id=expected.id,
                            kind=expected.kind,
                            status=status_map[
                                changeset_result.status
                            ],
                            evidence_ids=(
                                changeset_result.evidence_ids
                            ),
                            message=(
                                changeset_result.message
                            ),
                        )
                    )
                    continue

                evaluations.append(
                    ExpectedEvaluation(
                        expected_id=expected.id,
                        kind=expected.kind,
                        status=(
                            ExpectedEvaluationStatus.ERROR
                        ),
                        message=(
                            "Unsupported Expected kind: "
                            f"{expected.kind.value}"
                        ),
                    )
                )

            except Exception as exc:
                return (
                    "Expected evaluation infrastructure failed: "
                    f"{type(exc).__name__}: {exc}"
                )

        run.expected_evaluations = tuple(
            evaluations
        )

        return None

    @staticmethod
    def _evaluate_validation(
        run: TaskRun,
    ) -> str | None:
        if run.evidence is None:
            return "TaskRun does not own an EvidenceStore."

        try:
            results = ValidationEvaluator.evaluate_many(
                tuple(run.task.validation),
                run.evidence,
            )
        except Exception as exc:
            return (
                "Validation evaluation infrastructure failed: "
                f"{type(exc).__name__}: {exc}"
            )

        run.validation_results = results

        return None

    def execute(
        self,
        task: TaskV3,
        handlers: dict[str, Callable],
        handler_context: HandlerRuntimeContext | None = None,
        goal_preconditions: tuple[Precondition, ...] = (),
        runtime_safety_preconditions: tuple[Precondition, ...] = (),
        evidence_producers: tuple[EvidenceProducer, ...] = (),
        cancellation_token: CancellationToken | None = None,
        transaction_policy: TransactionExecutionPolicy | None = None,
    ) -> TaskRunExecutorResult:
        if not isinstance(task, TaskV3):
            raise TypeError(
                "TaskRunExecutor requires a TaskV3 instance."
            )

        if not isinstance(handlers, dict):
            raise TypeError(
                "TaskRunExecutor requires a handler dictionary."
            )
        if (
            cancellation_token is not None
            and not isinstance(
                cancellation_token,
                CancellationToken,
            )
        ):
            raise TypeError(
                "TaskRunExecutor requires a "
                "CancellationToken or None."
            )
        run = TaskRun(task)
        run.set_v3_phase(V3TaskPhase.PRECHECK)
        # ---------------------------------------------------------
        # VALIDATION
        # ---------------------------------------------------------
        run.set_v3_phase(V3TaskPhase.PRECHECK)
        run.transition(
            TaskRunStatus.VALIDATING
        )

        validation_result = validate_task_v3(task)

        if getattr(
            validation_result,
            "issues",
            None,
        ):
            return self._fail_run(
                run,
                "TaskV3 failed local semantic validation.",
            )

        # ---------------------------------------------------------
        # RESOLUTION
        # ---------------------------------------------------------
        run.set_v3_phase(V3TaskPhase.RESOLUTION)
        run.transition(
            TaskRunStatus.RESOLVING
        )

        resolution = self._resolver.resolve(
            task,
            handler_context,
        )

        run.resolution = resolution

        if (
            resolution.status
            is not TaskResolutionStatus.RESOLVED
        ):
            return self._fail_run(
                run,
                (
                    "Task resolution failed: "
                    f"{resolution.status.value}: "
                    f"{resolution.message}"
                ),
            )

        # ---------------------------------------------------------
        # PLANNING
        # ---------------------------------------------------------
        run.set_v3_phase(V3TaskPhase.PLANNING)
        run.transition(
            TaskRunStatus.PLANNING
        )

        plan = self._planner.build(
            resolution
        )

        run.execution_plan = plan

        if plan.status is not PlanStatus.READY:
            return self._fail_run(
                run,
                f"Planning failed: {plan.message}",
            )
        handler_policy = (
            resolution.handler_spec.execution_policy
            if resolution.handler_spec is not None
            else None
        )

        policy_resolution = (
            self._execution_policy_resolver.resolve(
                task.execution_policy,
                self._runtime_execution_limits,
                handler_policy=handler_policy,
                transaction_policy=transaction_policy,
            )
        )

        if (
            policy_resolution.status
            is not ExecutionPolicyStatus.READY
        ):
            return self._fail_run(
                run,
                (
                    "Execution policy resolution failed: "
                    f"{policy_resolution.message}"
                ),
            )

        run.effective_execution_policy = (
            policy_resolution.policy
        )
        # ---------------------------------------------------------
        # PRECONDITIONS
        # ---------------------------------------------------------
        run.set_v3_phase(V3TaskPhase.PRECHECK)
        run.transition(
            TaskRunStatus.CHECKING_PRECONDITIONS
        )

        preconditions = (
            self._precondition_evaluator.evaluate(
                task,
                goal_preconditions=(
                    goal_preconditions
                ),
                runtime_safety_preconditions=(
                    runtime_safety_preconditions
                ),
            )
        )

        run.preconditions = preconditions

        if not preconditions.satisfied:
            return self._fail_run(
                run,
                "Execution blocked by unsatisfied preconditions.",
            )

        # ---------------------------------------------------------
        # EXECUTION
        # ---------------------------------------------------------
        run.set_v3_phase(V3TaskPhase.EXECUTION)
        run.transition(
            TaskRunStatus.EXECUTING
        )

        execution = self._execution_runtime.execute(
            plan,
            preconditions,
            handlers,
            run.effective_execution_policy,
            cancellation_token=cancellation_token,
        )

        run.execution = execution

        if execution.status is not ExecutionStatus.SUCCEEDED:
            run.outcome = TaskOutcomeEvaluator.evaluate(
                execution=run.execution,
            )

            mapping = TaskRunStateMapper.map(
                execution.status
            )

            if (
                execution.status
                in {
                    ExecutionStatus.FAILED,
                    ExecutionStatus.INFRASTRUCTURE_ERROR,
                }
            ):
                if not run.terminal:
                    run.set_v3_phase(V3TaskPhase.RESOLUTION)
                    run.transition(
                        TaskRunStatus.FAILED
                    )

            if mapping.task_status is not None:
                run.set_task_status(
                    mapping.task_status
                )

            return TaskRunExecutorResult(
                run=run,
                completed=False,
            )

        self._record_execution_evidence(
            run
        )
        # ---------------------------------------------------------
        # POST EXECUTION
        # ---------------------------------------------------------
        run.set_v3_phase(V3TaskPhase.POST_EXECUTION)
        run.transition(
            TaskRunStatus.POST_EXECUTION
        )

        evidence_error = (
            self._record_post_execution_evidence(
                run,
                evidence_producers,
            )
        )

        if evidence_error is not None:
            return self._fail_run(
                run,
                evidence_error,
            )

        # ---------------------------------------------------------
        # EVALUATION
        # ---------------------------------------------------------

        run.transition(
            TaskRunStatus.EVALUATING
        )
        run.set_v3_phase(
            V3TaskPhase.VALIDATION
        )
        expected_error = (
            self._evaluate_expected(run)
        )

        if expected_error is not None:
            return self._fail_run(
                run,
                expected_error,
            )
        run.set_v3_phase(
            V3TaskPhase.VALIDATION
        )
        validation_error = (
            self._evaluate_validation(run)
        )

        if validation_error is not None:
            return self._fail_run(
                run,
                validation_error,
            )

        # TaskOutcome owns the semantic final decision.
        # Expected/Validation failures are NOT infrastructure failures.
        outcome = TaskOutcomeEvaluator.evaluate(
            execution=run.execution,
            expected_evaluations=(
                run.expected_evaluations
            ),
            validation_results=(
                run.validation_results
            ),
        )

        run.outcome = outcome

        if not outcome.succeeded:
            run.set_v3_phase(V3TaskPhase.RESOLUTION)
            run.transition(
                TaskRunStatus.FAILED
            )

            return TaskRunExecutorResult(
                run=run,
                completed=False,
            )
        run.set_v3_phase(V3TaskPhase.COMPLETE)
        run.transition(
            TaskRunStatus.COMPLETED
        )

        return TaskRunExecutorResult(
            run=run,
            completed=True,
        )


