.PHONY: docs-check verify-resources generate-indexes check-indexes check-all install-hooks uninstall-hooks assistant-init assistant-doctor assistant-run-dry

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

install-hooks:
	@ln -sf ../../tools/pre-commit .git/hooks/pre-commit
	@echo "Pre-commit hook installed."

uninstall-hooks:
	@rm -f .git/hooks/pre-commit
	@echo "Pre-commit hook removed."

assistant-init:
	python3 ./tools/gaia-assistant.py init

assistant-doctor:
	python3 ./tools/gaia-assistant.py doctor

assistant-run-dry:
	python3 ./tools/gaia-assistant.py run --mode single --dry-run
