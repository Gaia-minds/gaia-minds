.PHONY: docs-check verify-resources generate-indexes check-indexes check-all test-smoke test-uat uat-policy quality-matrix compatibility-matrix benchmark memory-benchmark memory-quality benchmark-trend hypothesis-validate hypothesis-run hypothesis-dry-run hypothesis-failure-fixture reliability-checkpoint reliability-checkpoint-check reliability-checkpoint-simulate-breach hardening-phase1 install-hooks uninstall-hooks assistant-init assistant-onboard assistant-auth-status assistant-doctor assistant-run-dry

HYPOTHESIS_OUTPUT_ROOT ?= /tmp/gaia-hypothesis-evals
RELIABILITY_CHECKPOINT_ROOT ?= /tmp/gaia-reliability-checkpoints

docs-check:
	./tools/validate-docs.sh

verify-resources:
	python3 ./tools/verify-resources.py

generate-indexes:
	python3 ./tools/generate-indexes.py

check-indexes:
	python3 ./tools/generate-indexes.py --check

check-all: docs-check check-indexes compatibility-matrix
	@echo ""
	@echo "All checks passed."

test-smoke:
	./tools/smoke-test.sh --json-out smoke-results.json

test-uat:
	python3 ./tools/uat-runner.py --manifest ./assistant/uat-scenarios.json --json-out ./assistant/uat-results.json

uat-policy:
	python3 ./tools/check-uat-policy.py --base-ref origin/main

quality-matrix:
	python3 ./tools/quality-matrix.py --json-out ./assistant/quality-matrix-results.json

compatibility-matrix:
	python3 ./tools/compatibility-matrix.py --baseline ./assistant/compatibility-matrix-baseline.json --matrix-out ./assistant/compatibility-matrix.md --check

benchmark:
	python3 ./tools/benchmark.py

memory-benchmark:
	python3 ./tools/memory-benchmark.py --check --json-out ./assistant/memory-retrieval-benchmark-results.json

memory-quality:
	python3 ./tools/memory-quality-matrix.py --check --json-out ./assistant/memory-quality-results.json

benchmark-trend:
	python3 ./tools/benchmark-trend.py --results ./assistant/benchmark-results.json --history ./assistant/benchmark-trend-history.json --summary ./assistant/benchmark-trend-summary.md

hypothesis-validate:
	python3 ./tools/hypothesis-pipeline.py validate --hypothesis ./assistant/hypotheses/phase3-hypothesis-pipeline-v1.json

hypothesis-run:
	python3 ./tools/hypothesis-pipeline.py run --hypothesis ./assistant/hypotheses/phase3-hypothesis-pipeline-v1.json --output-root "$(HYPOTHESIS_OUTPUT_ROOT)" --run-id local

hypothesis-dry-run:
	python3 ./tools/hypothesis-pipeline.py run --hypothesis ./assistant/hypotheses/phase3-hypothesis-pipeline-v1.json --output-root "$(HYPOTHESIS_OUTPUT_ROOT)" --run-id dry-run --dry-run

hypothesis-failure-fixture:
	python3 ./tools/hypothesis-pipeline.py run --hypothesis ./assistant/hypotheses/phase3-hypothesis-pipeline-v1-failure-fixture.json --output-root "$(HYPOTHESIS_OUTPUT_ROOT)" --run-id failure-fixture --dry-run

reliability-checkpoint:
	python3 ./tools/reliability-checkpoint.py --baseline-config ./assistant/reliability-baseline-phase3.json --output-root "$(RELIABILITY_CHECKPOINT_ROOT)" --run-id latest

reliability-checkpoint-check:
	python3 ./tools/reliability-checkpoint.py --baseline-config ./assistant/reliability-baseline-phase3.json --output-root "$(RELIABILITY_CHECKPOINT_ROOT)" --run-id latest --check

reliability-checkpoint-simulate-breach:
	python3 ./tools/reliability-checkpoint.py --baseline-config ./assistant/reliability-baseline-phase3.json --output-root "$(RELIABILITY_CHECKPOINT_ROOT)" --run-id simulated-breach --simulate-breach uat_pass_rate --check

hardening-phase1:
	python3 ./tools/phase1-hardening.py

install-hooks:
	@ln -sf ../../tools/pre-commit .git/hooks/pre-commit
	@echo "Pre-commit hook installed."

uninstall-hooks:
	@rm -f .git/hooks/pre-commit
	@echo "Pre-commit hook removed."

assistant-init:
	python3 ./tools/gaia-assistant.py init

assistant-onboard:
	python3 ./tools/gaia-assistant.py onboard

assistant-auth-status:
	python3 ./tools/gaia-assistant.py auth status

assistant-doctor:
	python3 ./tools/gaia-assistant.py doctor

assistant-run-dry:
	python3 ./tools/gaia-assistant.py run --mode single --dry-run
