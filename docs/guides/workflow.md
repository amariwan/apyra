# Workflow

`apyra-workflow` models workflow definitions, ordered steps, states, transitions, recovery contracts,
and a SQLAlchemy-backed repository/engine.

```python
from apyra.workflow import Workflow, WorkflowEngine

workflow = Workflow(name="process-order")
engine = WorkflowEngine(session)
await engine.start(workflow, [reserve_inventory, capture_payment])
```

Workflow steps must be retry-safe. Persist the workflow state before acknowledging external work,
use stable operation identifiers, and design compensations for side effects that cannot be rolled
back transactionally.

A database record of a transition is not an exactly-once guarantee for an external API call. Test
crashes between state persistence and side effects, recovery after restart, concurrent workers, and
terminal failure handling against the selected production database.
