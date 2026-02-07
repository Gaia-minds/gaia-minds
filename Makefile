.PHONY: docs-check verify-resources generate-indexes check-indexes check-all test-smoke install-hooks uninstall-hooks assistant-init assistant-onboard assistant-auth-status assistant-doctor assistant-run-dry

docs-check:
	./tools/validate-docs.sh

verify-resources:
	python3 ./tools/verify-resources.py

generate-indexes:
	python3 ./tools/generate-indexes.py

check-indexes:
	python3 ./tools/generate-indexes.py --check

check-all: docs-check check-indexes
	@echo ""
	@echo "All checks passed."

test-smoke:
	./tools/smoke-test.sh --json-out smoke-results.json

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
