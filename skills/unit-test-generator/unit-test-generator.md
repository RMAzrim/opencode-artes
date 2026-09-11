---
id: unit-test-generator
name: unit-test-generator
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: unit-test-generator
file_path: skills/unit-test-generator.md
name: Unit Test Generator
category: testing
tags: [jest, pytest, go-test, mocking, coverage]
author: opencode-core
version: 1.0.0
description: Generate automated unit test suites (Jest, Pytest, Go test) with complete mocking.
---

# Unit Test Generator

## Prerequisites & Dependencies
- Language runtime matching the project: Node.js 18+ (Jest/Vitest), Python 3.10+ (pytest, pytest-mock), or Go 1.21+
- Coverage tooling configured in the project (`c8`/Istanbul, `pytest-cov`, or `go test -cover`)
- Existing test conventions (directory layout, config files) so new tests match the repo setup

## Execution Steps
1. Inventory the units under test and classify their dependencies: pure logic, I/O (DB, HTTP, filesystem), time, and randomness.
2. Derive test cases per unit: happy path, boundary values, invalid inputs, error propagation, and state transitions.
3. Replace external dependencies with mocks/stubs; assert interactions (call count, arguments) only where they are part of the unit's contract.
4. Write tests using the project's framework with arrange-act-assert structure and behavior-describing test names.
5. Run the suite with coverage; add cases until all public branches are exercised, without testing implementation internals.
6. Ensure determinism: seed randomness, inject clocks instead of real time, and keep tests order-independent.

```python
import pytest
from unittest.mock import MagicMock
from orders.service import OrderService

def test_place_order_charges_and_persists():
    payments, repo = MagicMock(), MagicMock()
    svc = OrderService(payments=payments, repo=repo)

    order = svc.place_order(user_id=7, items=[("sku-1", 2)], price=10)

    payments.charge.assert_called_once_with(user_id=7, amount=20)
    repo.save.assert_called_once_with(order)
    assert order.total == 20

def test_place_order_propagates_payment_failure():
    payments = MagicMock()
    payments.charge.side_effect = RuntimeError("declined")
    svc = OrderService(payments=payments, repo=MagicMock())

    with pytest.raises(RuntimeError, match="declined"):
        svc.place_order(user_id=7, items=[("sku-1", 1)], price=5)
```

```bash
pytest --cov=orders --cov-report=term-missing -q
```
