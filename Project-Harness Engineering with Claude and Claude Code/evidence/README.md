# Evidence index

One folder per system. Each system was set up from the `solution/` directory of the final exercise of its project in the course repo, in its own virtual environment (`pip install -e ".[dev]"`), and its tests were run there. Systems 1 and 2 were run live against the course API proxy; Systems 3 and 4 were run end to end offline. Except for the first attempt kept below, runs used Python's UTF-8 mode, and run IDs and log times are UTC. Logs show only relative paths and `pytest` ran with `--no-header`. Machine details (OS, Python build, user and host names, absolute paths) are intentionally left out.

| System | Folder | pytest | Run artifacts |
|---|---|---|---|
| 1. Claims intake | `system1_agentic_loop/` | `pytest_S1.log`: 30 passed | `summary.md` (run `20261102_043419`, 8 claims, $0.1046), traces `claim_04_neighbor_injury.jsonl` (routed) and `claim_01_kitchen_fire.jsonl` (backstop escalation); `run-all-blocked-by-api-credit.log` is an earlier attempt rejected for lack of credit |
| 2. Retail context | `system2_context_strategy/` | `pytest_S2.log`: 30 passed (after the run) | `budget.json`, `eval.jsonl`, `eval_control.jsonl`, `context.md`, `case_facts_call.json` (run `20261102-043652`); `offline-baseline.log` is the earlier heuristic-counter measurement |
| 3. Claude Code config | `system3_claude_config/` | `pytest_S3.log`: 35 passed | `validator_output.txt` (`OK`), `claude_dir_structure.txt`, `claude-config-structure.txt`, `evidence_rule_{react,api,tests,skill,claude,review}.md` |
| 4. Shift monitor | `system4_orchestration/` | `pytest_S4.log`: 33 passed | `shift_run_output.txt`, `run-shift-windowed.log`, `hot_state.json`, `hot_state_size.txt`, `scratchpad_line.jsonl`, `extras.log`, `fork_demo/` (offline, recorded response) |

`system4_orchestration/scratchpad_line.jsonl` has three lines, one per `run-shift` invocation: the first attempt, the README-style rerun (`shift_run_output.txt`) and the windowed run (`run-shift-windowed.log`). `extras.py` is the small helper that produced `extras.log` and `fork_demo/`; it uses only the solution's public API.

`system4_orchestration/first-try-default-encoding/` holds the first attempt (`hot_state.json` with garbled text, and the `pytest.log` that still showed 33 passed), kept for reflection answers 19 and 20.

System 1 note: 6 of the 8 claims were escalated by the deterministic backstop because the model ended its turn without a terminal tool (see reflection answer 4). This is reported as observed, not tuned.

The reflection brief is `../my-reflection-brief.md`.
