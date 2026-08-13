.DEFAULT_GOAL := help
.PHONY: help sync test cov mutants notebook lab view worksheet calibrate run-v0 clean

# Every target is a thin wrapper around a single command — nothing here is
# required. `make` is a convenience; the underlying commands are in the README
# and work on their own for anyone without it.
#
# The no-key targets run with ANTHROPIC_API_KEY unset and the env-file lookup
# pointed at nothing, which is the reviewer's environment. That is the gate, so
# it is what the default targets exercise.

NOKEY := env -u ANTHROPIC_API_KEY LODGIFY_ENV_FILE=/nonexistent

help:  ## Show this help
	@grep -E '^[a-z0-9-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

sync:  ## Install everything (the only setup step)
	uv sync

test:  ## Run the test suite with no API key present — this is the gate
	$(NOKEY) uv run pytest -q

cov:  ## Test suite with a coverage report
	$(NOKEY) uv run pytest -q --cov=lodgify_challenge --cov-report=term-missing

mutants:  ## Mutation testing — grades whether the tests would catch a bug
	@rm -rf mutants
	@$(NOKEY) uv run mutmut run >/dev/null 2>&1 || true
	@ln -sfn ../data mutants/data
	@$(NOKEY) uv run mutmut run >/dev/null 2>&1 || true
	@$(NOKEY) uv run mutmut results

notebook:  ## Execute evals.ipynb offline and save its outputs
	$(NOKEY) uv run jupyter execute --inplace evals.ipynb

lab:  ## Open the notebook interactively
	uv run jupyter lab evals.ipynb

view:  ## Browse the committed .eval logs
	uv run inspect view --log-dir logs

worksheet:  ## Rebuild the human labelling worksheet from the frozen run
	$(NOKEY) uv run python scripts/make_labelling_worksheet.py

calibrate:  ## Judge agreement against data/gold_labels.jsonl
	$(NOKEY) uv run python scripts/report_calibration.py

# --- targets below spend money -----------------------------------------------

run-v0:  ## SPENDS MONEY: generate copy for every fixture and score it (~$0.30)
	uv run python scripts/run_eval.py

clean:  ## Remove generated artefacts (never touches logs/ or data/)
	rm -rf mutants .pytest_cache .coverage htmlcov
