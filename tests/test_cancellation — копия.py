from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from runtime.cancellation import (
    CancellationToken,
)


def test_token_starts_not_requested():
    token = CancellationToken()

    assert token.requested is False


def test_cancel_marks_token_requested():
    token = CancellationToken()

    token.cancel()

    assert token.requested is True


def test_cancel_is_idempotent():
    token = CancellationToken()

    token.cancel()
    token.cancel()
    token.cancel()

    assert token.requested is True


def test_reset_clears_cancellation():
    token = CancellationToken()

    token.cancel()
    assert token.requested is True

    token.reset()

    assert token.requested is False


def test_new_tokens_are_independent():
    first = CancellationToken()
    second = CancellationToken()

    first.cancel()

    assert first.requested is True
    assert second.requested is False


def test_cancellation_token_does_not_execute_or_stop_code_by_itself():
    token = CancellationToken()

    calls = 0

    def operation():
        nonlocal calls
        calls += 1

    token.cancel()

    operation()

    assert calls == 1
    assert token.requested is True


TESTS = [
    test_token_starts_not_requested,
    test_cancel_marks_token_requested,
    test_cancel_is_idempotent,
    test_reset_clears_cancellation,
    test_new_tokens_are_independent,
    test_cancellation_token_does_not_execute_or_stop_code_by_itself,
]


def main():
    print("=" * 70)
    print("CANCELLATION TESTS")
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
            "CANCELLATION: PASS"
        )
    else:
        print(
            "CANCELLATION: FAIL"
        )

    print("=" * 70)

    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())