# SimulationAgent — Task V3 Final Specification

**Статус:** FINAL — Architecture Baseline
**Назначение:** формальный контракт Task V3 до начала реализации
**Предыдущий стабильный контракт:** Task V2
**Область:** Semantic Task Model, Goal Resolution, Handler Resolution, Preconditions, Execution, Expected, Evidence, Validation, Result

---

# 1. Назначение Task V3

Task V3 определяет формальный контракт между:

* человеком или внешним клиентом, формирующим задачу;
* SimulationAgent;
* project/domain integration;
* runtime;
* механизмами исполнения;
* механизмами проверки результата.

Task V3 должен отделять:

* семантическое намерение;
* адресуемую цель;
* ожидаемый результат;
* условия начала;
* способ исполнения;
* доказательства;
* проверку достаточности доказательств;
* итог выполнения.

Task V3 не должен зависеть от SimulationZero на уровне базовой модели.

---

# 2. Главный архитектурный принцип

Task описывает **что требуется**, а не полный алгоритм того, как это сделать.

Полный жизненный цикл:

```text
Task
  ↓
Structural Validation
  ↓
Target Resolution
  ↓
Goal Resolution
  ↓
Handler Resolution
  ↓
Execution Plan
  ↓
Precondition Evaluation
  ↓
Execution
  ↓
Evidence Collection
  ↓
Expected Evaluation
  ↓
Validation
  ↓
TaskResult
```

---

# 3. Структура Task

Логическая структура:

```text
Task
├── schema_version
├── task_id
├── description
├── intent
├── preconditions
├── expected
├── validation
└── execution_policy
```

Дополнительные поля V2, обеспечивающие переходный compatibility layer, могут существовать отдельно, пока V2 полностью не мигрирован.

---

# 4. `description`

`description` — человеческое описание задачи.

Требования:

* свободный текст;
* предназначен прежде всего для человека;
* не является машинным источником семантики;
* не должен использоваться как единственный способ определения операции или цели.

Пример:

```text
"Добавить универсальный API компонентов в World."
```

---

# 5. `intent`

`intent` — формальное машинное намерение.

Структура:

```text
TaskIntent
├── operation
├── target
└── goal
```

`intent` не содержит:

* edits;
* expected state;
* validation rules;
* execution policy;
* rollback policy;
* shell commands.

---

# 6. `operation`

`TaskIntent.operation` является закрытым набором:

```text
CHANGE
VERIFY
INSPECT
MIGRATE
```

Семантика:

### CHANGE

Изменить состояние проекта/системы.

### VERIFY

Доказать определённое состояние или поведение без изменения.

### INSPECT

Исследовать или получить информацию.

### MIGRATE

Преобразовать существующее состояние с сохранением необходимых инвариантов.

Более мелкие категории вроде `FIX`, `ADD_FEATURE`, `REFACTOR` не являются частью operation-level taxonomy V3.

---

# 7. `target`

Target является структурированным адресом, а не поисковым запросом.

```text
TaskTarget
├── kind
├── identifier
└── scope
```

`kind`:

```text
PROJECT
FILE
SYMBOL
SUBSYSTEM
TEST
```

`scope`:

```text
scope
├── project
├── path
└── namespace
```

Target не должен содержать поисковую стратегию.

Поиск и разрешение адреса выполняются Target Resolution.

---

# 8. `goal`

Goal описывает семантический результат, который требуется получить.

```text
TaskGoal
├── kind
├── identifier
├── version
└── parameters
```

`GoalKind`:

```text
OUTCOME
STATE
ASSERTION
```

### OUTCOME

Описывает требуемый результат деятельности.

### STATE

Описывает требуемое состояние.

### ASSERTION

Описывает логический факт, который должен быть выполнен/доказан.

`GoalKind` классифицирует логическую природу результата, а не предметную область.

---

# 9. `GoalSpec.identifier`

`identifier` является стабильным ключом зарегистрированной цели.

Он не является свободным текстом.

```text
GoalRegistry
    ↓
GoalSpec
```

Неизвестный Goal ID не интерпретируется эвристически.

Неизвестная цель:

```text
RESOLUTION.UNKNOWN_GOAL
```

---

# 10. `GoalSpec`

```text
GoalSpec
├── identifier
├── kind
├── version
├── parameter_schema
└── semantic_contract
```

`GoalSpec` описывает:

* смысл цели;
* допустимую версию;
* схему параметров;
* семантический контракт.

`GoalSpec` не содержит конкретную реализацию исполнения.

---

# 11. `GoalRegistry`

`GoalRegistry` принадлежит SimulationAgent.

Он разделяет:

```text
Core Goals
Project Goals
```

Например:

```text
SimulationAgent
├── Core Goal Registry
└── Project Goal Registry
       └── SimulationZero
```

Полноценная plugin framework не является обязательной частью V3.

---

# 12. `GoalHandler`

GoalHandler реализует конкретную цель.

```text
GoalSpec
    ↕
GoalBinding
    ↓
GoalHandler
```

Task не содержит handler ID.

Handler выбирается runtime на основании:

* совместимости;
* capabilities;
* applicability;
* specificity.

---

# 13. Несколько handlers

Один GoalSpec может иметь несколько handlers.

```text
GoalSpec
├── Handler A
├── Handler B
└── Handler C
```

Выбор:

```text
1. Compatibility
2. Capability
3. Applicability
4. Specificity
5. Deterministic tie-break
```

Произвольный числовой priority не является основным механизмом выбора.

---

# 14. `ApplicabilityProfile`

`ApplicabilityProfile` декларативно описывает область применимости handler.

```text
ApplicabilityProfile
├── GoalConstraint?
├── OperationConstraint?
├── TargetConstraint?
├── ProjectConstraint?
├── EnvironmentConstraint?
├── CapabilityConstraint?
└── ParameterConstraintSet
```

Универсальный:

```text
field + operator + Any value
```

не используется.

Executable predicates запрещены.

---

# 15. Specificity

Specificity является **частичным порядком**.

Handler A специфичнее B тогда, когда:

```text
Applicability(A) ⊂ Applicability(B)
```

Числового `specificity_score` нет.

Результат сравнения:

```text
LESS_SPECIFIC
EQUIVALENT
MORE_SPECIFIC
INCOMPARABLE
```

Если несколько максимальных handlers:

* эквивалентные по применимости → допускается stable `handler_id` tie-break;
* несравнимые → `RESOLUTION.HANDLER_AMBIGUOUS`.

`handler_id` не должен скрывать архитектурную неоднозначность.

---

# 16. Environment

Environment описывает фактическую runtime/project environment.

```text
Environment
├── MachineEnvironment
└── ProjectEnvironment
```

Типовые свойства:

```text
OS
Architecture
Toolchain
Runtime
Project Environment
```

Версии представлены отдельным типом `Version`, а не свободными строками для сравнения.

Environment является состоянием runtime, а не identity.

---

# 17. Capability

Capability отвечает:

> что текущему Agent технически доступно и разрешено делать.

Capability — не синоним физической возможности машины.

```text
CapabilityRegistry
    ↓
CapabilityID
```

Примеры:

```text
filesystem.read
filesystem.write
process.execute
git.read
git.write
network.access
```

Handler объявляет необходимые capabilities.

Runtime сравнивает их с Granted Capability Set.

---

# 18. `EnvironmentConstraint` и `CapabilityConstraint`

EnvironmentConstraint описывает свойства среды.

CapabilityConstraint описывает требуемые capabilities.

Capability используется прежде всего при compatibility filtering.

Applicability не должна зависеть от конкретных пользовательских путей или машинных деталей, если они не являются явной частью project-specific contract.

---

# 19. `ResolutionContext`

Runtime формирует:

```text
ResolutionContext
├── task
├── goal
├── target
├── project
├── environment
└── capabilities
```

Handler applicability проверяется относительно этого контекста.

---

# 20. `ExecutionPlan`

После resolution создаётся производный runtime-объект:

```text
ExecutionPlan
├── actions
├── dependencies
├── selected_handler
├── preconditions
├── expected
├── validation
└── effective_execution_policy
```

ExecutionPlan:

* не является частью семантической модели Task;
* не сериализуется как обязательная часть входного Task;
* является результатом runtime planning.

---

# 21. Preconditions

Preconditions — обязательные условия до начала execution.

Источники:

```text
Task Preconditions
Goal Preconditions
Runtime Safety Preconditions
```

Effective set:

```text
EffectivePreconditions
=
Task Preconditions
AND
Goal Preconditions
AND
Runtime Safety Preconditions
```

Precondition не определяет семантику Goal.

---

# 22. Applicability ≠ Preconditions

Applicability:

> может ли данный handler реализовать задачу?

Precondition:

> можно ли начинать это конкретное исполнение сейчас?

Например:

```text
Windows
MSVC >= 2022
SimulationZero
```

→ applicability.

```text
repository.clean
workspace.unlocked
target.exists
```

→ preconditions.

---

# 23. Конфликт Preconditions

Task не может ослабить обязательное требование GoalSpec или runtime safety requirement.

Если Task явно задаёт несовместимое условие:

```text
PRECONDITION.CONFLICT
```

и execution не начинается.

Такой конфликт является ошибкой формирования/resolution Task, а не результатом частичного execution.

---

# 24. Проверка Preconditions

Каждая precondition атомарна.

```text
preconditions[]
```

имеет implicit AND semantics.

Результаты:

```text
SATISFIED
FAILED
UNAVAILABLE
ERROR
```

Если хотя бы одна обязательная precondition не `SATISFIED`:

```text
execution = NOT_STARTED
```

Precondition failure до мутации не требует rollback.

---

# 25. ExecutionPolicy

ExecutionPolicy управляет рамками исполнения, но не его семантикой.

```text
ExecutionPolicy
├── TimeoutPolicy
├── RetryPolicy
├── ParallelismPolicy
├── ResourcePolicy
├── FailurePolicy
└── RollbackPolicy
```

---

# 26. Timeout

Timeout является deadline runtime.

Он не гарантирует физически мгновенное завершение внешнего процесса.

Возможны отдельные результаты:

```text
EXECUTION.TIMEOUT
EXECUTION.PROCESS_TERMINATION_FAILED
```

---

# 27. Retry

По умолчанию:

```text
max_attempts = 1
```

Retry допускается только для retry-safe действий, явно поддержанных runtime/handler.

Ошибка `RETRYABLE` не означает, что retry обязательно будет произведён.

Retry определяется пересечением:

```text
Failure Recoverability
+
ExecutionPolicy
+
Handler Safety
```

---

# 28. Parallelism

ExecutionPlan определяет зависимости.

ExecutionPolicy только ограничивает степень параллелизма.

```text
Plan dependencies
        ↓
Scheduler
        ↓
max_workers from Policy
```

Policy не может нарушить причинные зависимости Plan.

---

# 29. Resource limits

ResourcePolicy задаёт допустимые пределы:

```text
CPU
Memory
Process Count
Disk
I/O
```

Если платформа не предоставляет строгой гарантии ограничения, семантика соответствующего параметра должна быть best-effort.

---

# 30. FailurePolicy

Базовые режимы:

```text
ABORT
ROLLBACK
CONTINUE
```

`CONTINUE` не нарушает dependency graph.

При наличии зависимости:

```text
A → B
```

и failure A, B не может быть выполнен только потому, что policy разрешает продолжение.

---

# 31. RollbackPolicy

Rollback является политикой, а не механизмом.

Policy говорит:

> нужно ли требовать rollback.

Transaction layer решает:

> как именно его выполнить.

Для transactional mutating tasks rollback по умолчанию обязателен.

---

# 32. EffectiveExecutionPolicy

Effective policy является пересечением ограничений:

```text
EffectiveExecutionPolicy
=
Task Policy
∩
Runtime Safety Limits
∩
Handler Constraints
∩
Transaction Constraints
```

Task может ограничить исполнение сильнее, но не может расширить capabilities или обойти runtime safety.

---

# 33. Expected

Expected является набором атомарных postconditions.

```text
ExpectedCondition
├── id
├── kind
├── identifier
├── version
└── parameters
```

В первой версии поддерживаются:

```text
STATE
ASSERTION
TEST
CHANGESET
```

---

# 34. Expected semantics

Каждый элемент `Expected[]` выражает одно логическое утверждение.

Список имеет implicit AND:

```text
Expected[0]
AND
Expected[1]
AND
...
AND
Expected[N]
```

Порядок элементов семантического значения не имеет.

Все обязательные conditions по возможности оцениваются независимо.

Произвольные вложенные:

```text
OR
NOT
XOR
expression trees
```

не входят в V3.

---

# 35. STATE

STATE — встроенный механизм проверки наблюдаемого свойства.

```text
STATE
├── target
├── property
├── operator
└── expected_value
```

`StateProperty`:

```text
StateProperty
├── identifier
├── version
├── value_type
├── target_kind
├── supported_operators
└── observation_semantics
```

Каждое property регистрируется в:

```text
StatePropertyRegistry
```

Конкретные условия STATE отдельно не регистрируются.

---

# 36. StateProvider

Provider предоставляет фактическое значение property.

```text
StateProperty
    ↓
StateProvider
    ↓
observed value
```

Один provider может предоставлять множество properties.

Provider является read-only.

Результаты чтения:

```text
FOUND
NOT_FOUND
UNAVAILABLE
ERROR
```

---

# 37. ASSERTION

ASSERTION применяется для сложной логики, которая не сводится к простому:

```text
property operator value
```

Структура:

```text
AssertionSpec
├── identifier
├── version
├── parameter_schema
├── semantic_contract
└── observations
```

Реализация:

```text
AssertionSpec
    ↓
AssertionEvaluator
```

Evaluator:

* read-only;
* deterministic;
* не управляет execution;
* не управляет materialization;
* не выполняет rollback.

---

# 38. TEST

TEST является отдельным Expected kind.

```text
Expected.TEST
    ↓
TestRegistry
    ↓
TestSpec
    ↓
TestRuntime
    ↓
TestResult
```

Task указывает:

```text
test_id
parameters
expected_status
```

Task не содержит test command.

TestSpec версионируется.

---

# 39. TestResult

Минимальные семантические статусы:

```text
PASSED
FAILED
SKIPPED
BLOCKED
INFRASTRUCTURE_ERROR
```

Важно:

```text
test failure
≠
infrastructure failure
```

`Expected.TEST = PASSED` считается выполненным только при получении соответствующего PASS.

---

# 40. TEST как Expected и TEST как Evidence

Тест может иметь две разные роли.

### Как Expected

```text
Expected:
    TEST ZERO-CORE-11 = PASSED
```

Тест сам является требуемым результатом.

### Как Validation evidence

```text
Expected:
    some semantic condition

Validation:
    use ZERO-CORE-11 as evidence
```

Это не смешивается.

---

# 41. CHANGESET

CHANGESET описывает требуемое отношение между состоянием проекта до и после Task.

```text
ChangeSetExpectation
├── mode
├── required[]
├── allowed[]
└── forbidden[]
```

Режимы:

```text
CONSTRAINED
EXACT
```

`CONSTRAINED`:

```text
required ⊆ actual
actual ∩ forbidden = ∅
actual ⊆ allowed        // если allowed задан
```

`EXACT` требует полного соответствия.

---

# 42. ChangeRecord

```text
ChangeRecord
├── old_path
├── new_path
└── kind
```

`ChangeKind`:

```text
ADDED
MODIFIED
DELETED
RENAMED
```

Rename является одной логической change record.

CHANGESET работает со структурированными изменениями, а не с текстом raw diff.

---

# 43. Relation к Task V2 `expected_paths`

`expected_paths` сохраняется как V2 compatibility mechanism.

V2:

```text
expected_paths
    ↓
existing changed-path validation
```

V3:

```text
Expected.CHANGESET
    ↓
ChangeObserver
    ↓
ChangeSetEvaluator
```

V3 не ломает V2 ради унификации.

В дальнейшем общая change infrastructure может обслуживать оба уровня.

---

# 44. Evidence

Evidence является самостоятельной runtime-сущностью конкретного `TaskRun`.

```text
TaskRun
└── EvidenceStore
```

Evidence не является частью входного Task.

Evidence:

* immutable;
* typed;
* привязано к execution context;
* содержит provenance/source;
* имеет observation metadata.

---

# 45. Evidence sources

Базовые типы:

```text
STATE_OBSERVATION
TEST_RESULT
CHANGESET_OBSERVATION
ASSERTION_RESULT
```

Источник может быть:

```text
StateProvider
TestRuntime
ChangeObserver
AssertionEvaluator
```

---

# 46. Evidence и Artifact

```text
Evidence ≠ Artifact
```

Evidence — факт/наблюдение.

Artifact — файл или другой сохраняемый объект.

Artifact может быть использован как источник evidence, но эти понятия не объединяются.

---

# 47. Evidence freshness

Evidence должно быть связано с конкретным TaskRun / execution context.

Timestamp сам по себе недостаточен.

Validation может требовать:

```text
PRE_EXECUTION
POST_EXECUTION
VALIDATION
```

или иной явно определённый lifecycle scope.

Старое evidence не может считаться свежим evidence текущего TaskRun без соответствующего разрешения policy.

---

# 48. Expected и Validation

Это два независимых слоя, работающих над Evidence.

Правильная схема:

```text
                    Evidence
                   /        \
                  ↓          ↓
          Expected Eval   Validation
                  \          /
                   ↓        ↓
                    Final Decision
```

Expected отвечает:

> выполнено ли требование?

Validation отвечает:

> достаточно ли доказательства, чтобы это требование можно было признать установленным в рамках contract?

Validation не меняет semantic meaning Expected.

---

# 49. Validation

Validation — read-only verification layer.

```text
Validation
    ↓
Evidence requirements
    ↓
Evidence
    ↓
Validation evaluation
```

Validation может:

* использовать уже существующее evidence;
* потребовать новое evidence;
* использовать TestRuntime;
* проверять freshness;
* проверять достаточность evidence;
* сопоставлять несколько evidence.

Validation не изменяет проект.

---

# 50. Validation ≠ Expected

```text
Expected
    = requirement

Evidence
    = observed fact

Validation
    = verification/evidence sufficiency policy
```

Validation не должна дублировать Expected без необходимости.

---

# 51. Ациклический контракт Evidence / Expected / Validation

Это обязательный инвариант:

```text
Execution
    ↓
Evidence
    ├──→ Expected Evaluation
    └──→ Validation
              ↓
        Final Task Decision
```

Недопустимы циклы вида:

```text
Validation → Expected → Validation
```

или:

```text
Expected → Validation → Expected
```

Validation не является источником семантики Expected.

---

# 52. Task success

Task считается успешным только при выполнении:

```text
ALL required Expected = SATISFIED
AND
ALL required Validation = VALID
```

При этом:

```text
Expected FAIL
≠
Validation INSUFFICIENT
```

и:

```text
Validation INSUFFICIENT
≠
Expected FALSE
```

---

# 53. Preconditions и Expected

Precondition является условием **до** execution.

Expected является условием **после** execution.

Они не взаимозаменяемы.

```text
Precondition
    ↓
Execution
    ↓
Expected
```

---

# 54. Preconditions и Validation

```text
Precondition
    → можно ли начинать?

Validation
    → достаточно ли доказано выполнение?
```

Precondition failure прекращает execution.

Validation failure происходит после результата.

---

# 55. Target Resolution

Target является адресом, но должен быть разрешён runtime.

Результаты должны различать:

```text
resolved
not found
ambiguous
stale
unavailable
error
```

Неразрешённый target не должен автоматически интерпретироваться как другой target.

Особенно важно сохранить корректность при:

* virtual target;
* materialized target;
* representation changes;
* stale references.

---

# 56. ExecutionPolicy и Expected

ExecutionPolicy не может изменить:

* Goal;
* Expected semantics;
* Validation semantics.

Например retry, timeout или continue policy не превращают failing Expected в passing Expected.

---

# 57. Cancellation

`CANCELLED` — не обычный failure.

Но cancellation после начала мутации **не отменяет transaction guarantees**.

Например:

```text
TaskStatus = CANCELLED
Rollback = SUCCESS
Integrity = PRESERVED
```

или:

```text
TaskStatus = CANCELLED
Rollback = FAILED
Integrity = DEGRADED
```

---

# 58. Task Status

`TaskStatus`:

```text
PENDING
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

Статус не содержит фазу или причину failure.

---

# 59. Task Phase

`TaskPhase`:

```text
PRECHECK
RESOLUTION
PLANNING
CHECKPOINT
EXECUTION
POST_EXECUTION
EXPECTED_EVALUATION
VALIDATION
ROLLBACK
COMPLETE
```

Phase показывает положение Task в pipeline.

Она не является частью semantic success/failure taxonomy.

---

# 60. FailureCode

FailureCode организован по namespace:

```text
TASK.*
RESOLUTION.*
PLANNING.*
PRECONDITION.*
EXECUTION.*
EXPECTED.*
VALIDATION.*
ROLLBACK.*
INFRASTRUCTURE.*
```

Примеры:

```text
TASK.INVALID
TASK.MISSING_FIELD

RESOLUTION.UNKNOWN_GOAL
RESOLUTION.UNKNOWN_TARGET
RESOLUTION.HANDLER_UNAVAILABLE
RESOLUTION.HANDLER_AMBIGUOUS

PRECONDITION.FAILED
PRECONDITION.UNAVAILABLE
PRECONDITION.ERROR
PRECONDITION.CONFLICT

PLANNING.FAILED

EXECUTION.FAILED
EXECUTION.TIMEOUT
EXECUTION.CANCELLED
EXECUTION.PROCESS_TERMINATION_FAILED

EXPECTED.NOT_SATISFIED
EXPECTED.UNAVAILABLE
EXPECTED.ERROR

VALIDATION.INVALID
VALIDATION.INSUFFICIENT
VALIDATION.ERROR

ROLLBACK.FAILED

INFRASTRUCTURE.ERROR
```

---

# 61. Failure ≠ Exception

Доменные результаты:

```text
Expected condition is false
Precondition is false
Test failed
```

не являются unexpected exceptions.

Implementation/runtime exception может быть представлен как structured failure с диагностикой underlying error.

---

# 62. Recoverability

Failure instance может иметь:

```text
NON_RECOVERABLE
RETRYABLE
USER_ACTION_REQUIRED
ROLLBACK_REQUIRED
```

Recoverability не определяется только `FailureCode`.

Она зависит также от:

* handler;
* execution state;
* operation safety;
* policy.

`RETRYABLE` не означает автоматический retry.

---

# 63. TaskIntegrity

`TaskIntegrity`:

```text
PRESERVED
DEGRADED
UNKNOWN
```

### PRESERVED

Целостность подтверждённо сохранена.

### DEGRADED

Гарантия восстановления не выполнена.

### UNKNOWN

Состояние невозможно надёжно установить.

---

# 64. Rollback

Rollback является отдельной результатной осью.

Примеры:

```text
Task:
    FAILED
Rollback:
    SUCCESS
Integrity:
    PRESERVED
```

и:

```text
Task:
    FAILED
Rollback:
    FAILED
Integrity:
    DEGRADED
```

`ROLLBACK_FAILED` не должен превращать всё в новый искусственный TaskStatus.

---

# 65. TaskResult

Концептуально:

```text
TaskResult
├── status
├── phase
├── failure
├── integrity
├── attempts
├── expected_results[]
├── validation_results[]
├── rollback_result
└── diagnostics
```

`TaskResult.success` является производным итогом выполнения contract.

---

# 66. Финальный lifecycle

```text
PENDING
   ↓
RUNNING
   ↓
PRECHECK
   ↓
RESOLUTION
   ↓
PLANNING
   ↓
CHECKPOINT
   ↓
EXECUTION
   ↓
POST_EXECUTION
   ↓
EXPECTED_EVALUATION
   ↓
VALIDATION
   ↓
SUCCEEDED
```

Failure path:

```text
RUNNING
   ↓
failure
   ↓
ROLLBACK
   ↓
FAILED / CANCELLED
```

с независимым:

```text
TaskIntegrity
```

---

# 67. Полный архитектурный контур

```text
                           TASK
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
       Intent           Preconditions       Expected
          │                  │                  │
     ┌────┴────┐             │           ┌──────┴────────┐
 Operation   Target          │          STATE ASSERTION
                │             │          TEST  CHANGESET
                ▼             │
         Target Resolver      │
                │             │
                └──────┬──────┘
                       ▼
                  Goal Resolver
                       │
                       ▼
                    GoalSpec
                       │
                       ▼
                Handler Resolver
                       │
             Applicability /
              Capabilities
                       │
                       ▼
                 GoalHandler
                       │
                       ▼
                ExecutionPlan
                       │
              Effective Policy
                       │
                       ▼
                Preconditions
                       │
                  satisfied
                       │
                       ▼
                    Execute
                       │
                       ▼
                 EvidenceStore
                  /    |     \
                 /     |      \
              STATE   TEST   CHANGESET
                 \     |      /
                  \    |     /
                   \   |    /
                     ASSERTION
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      Expected Evaluation     Validation
             │                   │
             └─────────┬─────────┘
                       ▼
                   TaskResult
```

---

# 68. Архитектурные инварианты V3

1. Runtime representation не является semantic identity Task.
2. Target является адресом, а не поисковым запросом.
3. Goal определяет семантическое намерение.
4. Expected определяет postcondition.
5. Validation определяет достаточность доказательств.
6. Evidence представляет фактически наблюдённые данные.
7. Handler реализует Goal, но не определяет конечный успех Task.
8. ExecutionPlan является производным runtime-объектом.
9. Preconditions должны быть подтверждены до execution.
10. ExecutionPolicy ограничивает execution, но не меняет семантику.
11. Applicability определяет пригодность handler.
12. Preconditions определяют возможность начать конкретное execution.
13. Specificity является partial order, а не числовым рейтингом.
14. Unknown Goal/Target не разрешается эвристически.
15. Expected conditions атомарны.
16. `Expected[]` имеет implicit AND semantics.
17. Validation и Expected образуют ациклическую модель.
18. Evidence текущего TaskRun не подменяется старым evidence без явного разрешения freshness policy.
19. Retry не должен повторять небезопасную мутацию.
20. Rollback policy и rollback mechanism разделены.
21. Task policy не может расширить runtime safety или capabilities.
22. Cancellation после начала мутации не отменяет transaction guarantees.
23. Failure не определяет автоматически integrity.
24. Rollback failure приводит к отдельному degraded integrity state.
25. V2 compatibility mechanisms сохраняются до безопасной миграции.

---

# 69. Что сознательно НЕ входит в Task V3

Следующие системы не являются частью данного semantic contract:

* полноценный plugin framework;
* scheduler implementation;
* конкретный ECS/ECS-like runtime;
* конкретный Git implementation;
* конкретная shell/CLI implementation;
* distributed execution;
* arbitrary expression language;
* arbitrary predicates;
* numeric handler priority;
* dynamic arbitrary Python code inside contracts;
* representation/materialization engine SimulationZero;
* production resource sandboxing implementation.

Они могут появиться позже как runtime/integration layers, не ломая Task V3.

---

# 70. Граница между Task V2 и Task V3

Task V2 уже предоставляет стабильный рабочий pipeline:

```text
validation
checkpoint
edit
diff
diff validation
build
run
rollback
TaskResult
JSON
```

Task V3 не отменяет этот baseline.

V3 добавляет semantic layer:

```text
Intent
Goal
Target
Expected
Validation
Preconditions
ExecutionPolicy
Evidence
Resolution
Planning
```

Миграция должна идти постепенно.

---

# 71. Архитектурный статус

После решений 5.1–5.29 и аудиторских уточнений Task V3 считается:

```text
SEMANTIC MODEL: CLOSED
ARCHITECTURAL CONTRADICTIONS: NONE KNOWN
CORE BOUNDARIES: DEFINED
V2 COMPATIBILITY STRATEGY: DEFINED
```

Следующий этап:

```text
TASK V3 FINAL SPECIFICATION
        ↓
JSON Schema
        ↓
Python model
        ↓
validation
        ↓
runtime integration
        ↓
tests
```

До изменения спецификации новые runtime-концепции не должны добавляться просто ради расширения архитектуры.

Новые требования сначала проходят отдельный architecture review и только после этого изменяют V3 contract.
