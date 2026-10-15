# Pi-inspired agent runtime integration

**Goal:** Extend the existing Python agent with durable branching sessions, steering/follow-up input, executable extensions, restricted tool composition and SDK/RPC access.

**Architecture:** Keep the existing ReAct loop and permission/confirmation pipeline. Add a local session store and turn-scoped control hooks, then expose the same execution path to extensions and programmatic clients. Do not bind restored sessions to a particular model or revert working-tree files when branching.

**Constraints:** Python 3.12; preserve existing comments, tools and provider configuration. Keep new UI text in JSON. Tests before implementation; local incremental commits, no automatic push. Run implementation directly in the current checkout; unrelated untracked notes remain untouched.

## Tasks and verification

- [x] Durable sessions: store append-only message nodes and context checkpoints atomically in SQLite; restore by working directory, retain branches on checkout and preserve pre-compaction history. Test restart, cross-project isolation, tool boundaries and competing writers.
- [x] Steering: Enter during a run is delivered after the complete current model/tool batch; Alt+Enter queues an independent follow-up. Test final-response races, full tool batches, cancellation and real terminal input.
- [x] Extensions: load explicitly configured Python extensions; register tools and lifecycle/context/tool hooks without importing project code implicitly. Route extension tools through existing permissions. Test blocked/mutated calls, context transformation and cleanup.
- [x] Codemode: expose bounded, restricted scripts that can compose registered tools and return selected output. Preserve per-tool permissions and interruption. Test denied operations, execution/output limits and results filtering.
- [x] SDK/RPC: expose one reusable session API and JSONL subprocess transport, sharing tools, session store and events with CLI. Test prompt, resume, steering, errors and cancellation in a subprocess.
- [x] Final validation: relevant regression suite, complete project pytest run with any unrelated failures identified, lint/diff checks, documentation and local commits.

## Validation results

- Complete `pytest -q`: 607 passed, 2 skipped, 2 failed. Both failures were Docker Hub image-pull timeouts in `test_alembic_upgrade_head_smoke_real_db` and `test_docker_compose_health_smoke`.
- The CI-style suite excluding those two infrastructure smoke tests: 608 passed, 2 skipped, 2 deselected after adding cancellation coverage.
- Final affected-area regression: 188 passed; subsequent RPC immediate-cancellation regression plus both subprocess entrypoints: 3 passed.
- Ruff on `src tests`, mypy on all 188 source files, Bandit on the new runtime/session modules and `git diff --check` passed.
- Built a wheel and verified inclusion of runtime modules and packaged JSON files.
- Model responses in terminal and RPC tests use deterministic test providers; these tests do not claim live-model quality or remote deployment validation.
