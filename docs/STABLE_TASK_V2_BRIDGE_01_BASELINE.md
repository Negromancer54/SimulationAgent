# Stable Task V2 + Bridge 0.1 Baseline

**Status:** STABLE
**Baseline:** Task V2 + Bridge 0.1
**Date:** 2026-09-08

## 1. Purpose

This document defines the stable baseline for the SimulationAgent development pipeline immediately before the next functional evolution of the Task contract.

No change to the Task, transaction, rollback, or Bridge architecture should be made solely because of a defect already covered by this baseline.

## 2. SimulationZero-Cpp baseline

Project:

`C:\Users\Gycha\SimulationZero-Cpp`

Git HEAD:

`70bee4cfde496831e655f9c507dd243bdd0d1421`

Repository state:

`clean`

The ComponentStorage / EntityDirectory / ComponentMask runtime currently passes the established SimulationZero test suite.

## 3. SimulationAgent baseline

Project:

`C:\Users\Gycha\SimulationAgent`

Primary runtime file:

`agent.py`

Stable reference copy:

`agent_stable_task_v2_baseline.py`

The reference copy was verified byte-for-byte against `agent.py`.

Verification:

`FC: различия не найдены`

## 4. Task V2 contract

`Task` contains:

* `task_id`
* `description`
* `edits`
* `expected_paths`

### task_id

Required non-empty string.

### description

Required non-empty string.

### edits

List of edit operations.

Supported operations:

#### create

* `path` — required non-empty string
* `content` — required string
* empty content is valid

#### replace

* `path` — required non-empty string
* `old_text` — required non-empty string
* `new_text` — required string
* empty `new_text` is valid
* `expected_count` — optional positive integer
* boolean values are not valid `expected_count` values

Multiple edits are supported.

Multiple edits targeting the same path are supported.

`create` followed by `replace` on the same path is supported.

## 5. expected_paths semantics

An empty `expected_paths` list means that no path oracle was declared.

In that case:

* changed paths are still collected;
* DIFF is still executed;
* DIFF validation is skipped;
* `diff_validated` is set to `True`;
* execution proceeds to BUILD.

When `expected_paths` is non-empty, the expected path set must match the actual changed path set.

## 6. run_task contract

`run_task()` accepts a Task V2 object.

Successful execution follows:

`PRECHECK → CHECKPOINT → EDIT → DIFF → DIFF_VALIDATION → BUILD → RUN → COMPLETE`

Failure after checkpoint follows the rollback path.

Validation failure before checkpoint remains a `PRECHECK`-stage failure.

## 7. TaskResult contract

`run_task()` returns `TaskResult`.

`fail_task()` always returns `TaskResult`, both:

* when no checkpoint exists;
* when rollback is performed.

Failure after a checkpoint records rollback status.

Rollback failure promotes the final failure code to `ROLLBACK_FAILED`.

## 8. JSON contract

`task_result_to_json()` continues to emit TaskResult JSON schema version 1.

Task V2 does not require a change to the established TaskResult JSON V1 schema.

## 9. Verified Agent tests

The following established tests passed after the Task V2 stabilization:

* Task V2 validation
* invalid Task handling
* valid create
* valid replace
* DIFF failure
* DIFF validation failure
* BUILD failure
* RUN failure
* rollback failure
* successful transaction
* transaction JSON integration
* multiple create edits
* multiple replace edits on the same path
* create + replace on different paths
* create + replace on the same path
* multi-edit failure
* expected-count failure
* rollback of multiple creates
* rollback of mixed changes
* empty `expected_paths`
* `fail_task()` return-type contract

The working tree was verified clean after the regression sequence.

## 10. Bridge 0.1 baseline

Bridge project:

`C:\Users\Gycha\SimulationAgent\bridge`

Bridge Test Contract:

**Version:** 0.1
**Schema version:** 1

Regression result:

**36 / 36 PASS**

Breakdown:

* B tests: 13
* P tests: 10
* E tests: 3
* PA tests: 10

Final checks:

* Contract validation: PASS
* PROJECT PRECHECK: PASS
* PROJECT POSTCHECK: PASS
* PROJECT FINAL POSTCHECK: PASS
* PROJECT PA FINAL POSTCHECK: PASS

## 11. Verified Bridge path

The following path is operational:

`Page API → Bridge → Native Messaging → host.py → agent.Task → run_task() → TaskResult → Bridge → Page API`

PA-01 verifies successful Task execution through the complete Bridge.

The Bridge also currently verifies:

* invalid Bridge requests;
* invalid Task propagation to Agent validation;
* sequential task execution;
* concurrent request correlation;
* mixed concurrent outcomes;
* Page API reuse;
* TaskResult integrity;
* foreign response isolation;
* late response handling after timeout.

## 12. Stable baseline rule

This baseline is considered the reference point for future development.

Changes introduced after this point must not silently redefine:

* Task V2 semantics;
* `expected_paths` semantics;
* TaskResult type guarantees;
* TaskResult JSON V1;
* transaction rollback behavior;
* Bridge 0.1 transport semantics;

unless a future contract revision explicitly requires such a change.

## 13. Next development stage

The next planned architectural stage is Task V3.

Task V3 must be designed on top of this stable baseline rather than by modifying existing V2 behavior opportunistically.
