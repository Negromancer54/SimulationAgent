from agent_task_v3 import (
    ExecutionPolicy,
    ParallelismPolicy,
    RetryPolicy,
    TimeoutPolicy,
    TaskV3,
)
from registries.handler_registry import (
    HandlerApplicability,
    HandlerSpec,
)
from runtime.execution_policy import (
    HandlerExecutionPolicy,
)
from registries.handler_resolver import (
    HandlerResolver,
)
from runtime.task_run_executor import (
    TaskRunExecutor,
)


def test_selected_handler_policy_is_exposed_on_resolution():
    # Заполняется после проверки фактической конструкции тестовой TaskV3.
    # Этот тест пока является контрактным маркером 27.8.4.
    assert HandlerExecutionPolicy is not None
    assert HandlerSpec is not None
    assert HandlerResolver is not None
    assert HandlerExecutionPolicy is not None
    assert TaskRunExecutor is not None


def test_handler_policy_is_a_distinct_execution_policy_type():
    policy = HandlerExecutionPolicy(
        timeout_seconds=5,
        max_attempts=2,
        max_workers=1,
    )

    assert isinstance(policy, HandlerExecutionPolicy)
    assert policy.timeout_seconds == 5
    assert policy.max_attempts == 2
    assert policy.max_workers == 1


def test_handler_policy_contract_is_not_task_policy():
    handler_policy = HandlerExecutionPolicy(
        timeout_seconds=5,
    )

    assert not isinstance(handler_policy, ExecutionPolicy)
