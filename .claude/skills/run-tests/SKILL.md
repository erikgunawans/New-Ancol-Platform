---
name: run-tests
description: Run all 377+ tests across 9 services with correct PYTHONPATH isolation
---

# /run-tests

Run the full test suite for the Ancol MoM Compliance System.

Each service has its own Python namespace and requires PYTHONPATH to be set correctly.
This skill runs all 9 locally-testable services and reports pass/fail counts.

## Steps

1. Run all services:

```bash
TOTAL=0
FAIL=0
for svc in extraction-agent legal-research-agent comparison-agent reporting-agent api-gateway batch-engine email-ingest regulation-monitor gemini-agent; do
  echo "=== $svc ==="
  OUTPUT=$(PYTHONPATH=packages/ancol-common/src:services/$svc/src python3 -m pytest services/$svc/tests/ -q 2>&1)
  echo "$OUTPUT" | tail -3
  COUNT=$(echo "$OUTPUT" | tail -1 | grep -oE '^[0-9]+' | head -1)
  TOTAL=$((TOTAL + ${COUNT:-0}))
  echo "$OUTPUT" | grep -q "failed" && FAIL=$((FAIL + 1))
done
echo ""
echo "Total: $TOTAL tests across 9 services. Failed services: $FAIL"
```

2. Run ruff lint:

```bash
ruff check packages/ services/ scripts/ corpus/scripts/
```

3. Report summary with pass/fail counts per service.
