# Continuous integration

Every push and pull request to the repository runs an automated check on
GitHub Actions. If this check fails, the change should not be merged until
it is fixed.

## What runs

The workflow is defined in `.github/workflows/ci.yml`. It runs on a
`windows-latest` GitHub runner, because the software (and the `mcculw` DAQ
driver it depends on) targets Windows, and the pixi environment is only
defined for the `win-64` platform.

The job runs these steps in order:

1. **Checkout** the repository.
2. **Set up the environment** with [pixi](https://pixi.sh), using the
   dependencies in `pixi.toml` and the locked versions in `pixi.lock`. The
   environment is cached between runs.
3. **Lint**: `pixi run ruff check software/src`
4. **Test**: `pixi run test`, which runs `pytest software/tests`

If any step fails, the run is marked as failed, and later steps do not run.

## Running the same checks locally

Run the same commands locally before you push, so CI failures are caught
early:

```
pixi run ruff check software/src
pixi run test
```

You can run one test tier on its own with pytest markers:

```
pixi run pytest -m unit
pixi run pytest -m integration
```

The repository also has a `.pre-commit-config.yaml`. If you install
[pre-commit](https://pre-commit.com), ruff and a few file-hygiene checks
(trailing whitespace, line endings, YAML/JSON validity, large files) run
automatically on each commit. Note that it includes `no-commit-to-branch`,
which blocks direct commits to `main`, so work on a branch.

## What the tests cover

Tests live in `software/tests/` and are split into tiers. See
`software/tests/README.md` for full details.

| Tier          | Folder         | Runs in CI | What it does                                                      |
|---------------|----------------|------------|-------------------------------------------------------------------|
| `unit`        | `unit/`        | Yes        | Pure logic, no hardware, no GUI, no real I/O                     |
| `integration` | `integration/` | Yes        | Real components wired together, with serial/ADC hardware faked    |
| `system`      | not created    | No         | Full app + real hardware; done by hand as a bench checklist       |

GitHub-hosted runners have no display and no DAQ board or ESP32 attached, so
anything that needs DearPyGUI's viewport or real hardware cannot run in CI.
Code that talks to hardware must be tested through fakes (see `FakeADC` in
`software/tests/conftest.py` and `test_worker_hardware_boundary.py` for the
pattern).

## Adding tests

- Put new test files in `software/tests/unit/` or
  `software/tests/integration/`, named `test_*.py`. pytest picks them up
  automatically, and nothing needs to change in the workflow.
- Mark them with `@pytest.mark.unit` or `@pytest.mark.integration`.
- Import modules the same way the app does (`from core.event_bus import
  EventBus`, not `from src.core...`). `software/src` is put on the path by
  the `pythonpath` setting in `pyproject.toml`.
- Do not import `mcculw` or `dearpygui` at the top of a test, or the test will fail on
  the runner. Fake the hardware boundary instead.

## Adding dependencies

CI installs exactly what is in `pixi.toml` and `pixi.lock`. If you add a
package, add it with `pixi add <package>` and commit both files. Otherwise
the code works on your machine but fails in CI with an `ImportError`.

## Checking results

Open the **Actions** tab of the GitHub repository to see each run. Pull
requests also show the check status at the bottom of the page. Click a
failed step to see the full lint or pytest output.

## Known gaps

- `.github/workflows/docs.yml` exists but is empty, so CI does not build or
  check the documentation. The docs are built separately by Read the Docs
  (`.readthedocs.yaml`).
- `firmware/test/` contains no tests, so the ESP32 firmware is not checked
  by CI.
- The workflow does not exclude `system`-marked tests. If system tests are
  added, change the test command to `pytest software/tests -m "not system"`
  or CI will try to run them.
