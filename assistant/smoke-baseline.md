# Smoke Baseline

Updated: February 15, 2026

## Suite

Command:

```bash
make test-smoke
```

Expected artifact:

- `smoke-results.json`

## Baseline Expectations

Total tests: `29`

1. `cli_startup` -> pass
2. `config_read_write` -> pass
3. `session_create_resume` -> pass
4. `chat_response_profiles_deterministic` -> pass
5. `note_capture_and_tasks` -> pass
6. `feedback_record_and_list` -> pass
7. `feedback_invalid_label_rejected` -> pass
8. `signals_extraction_privacy_controls` -> pass
9. `signals_skill_first_triage_matrix` -> pass
10. `memory_crud_and_filters` -> pass
11. `memory_retrieve_ranking_and_benchmark` -> pass
12. `memory_summarize_traceability_and_benchmark` -> pass
13. `memory_policy_privacy_controls` -> pass
14. `memory_qa_redteam_harness` -> pass
15. `autopilot_dry_run` -> pass
16. `autopilot_run_and_trace` -> pass
17. `schedule_lifecycle_and_due_run` -> pass
18. `reminder_lifecycle_and_controls` -> pass
19. `skills_runtime_list_and_inspect` -> pass
20. `skills_validation_pass_and_block` -> pass
21. `skills_provenance_admission_modes` -> pass
22. `skills_obfuscation_validation_hardening` -> pass
23. `sandbox_profile_and_escalation` -> pass
24. `policy_engine_gating_and_allowlists` -> pass
25. `delegation_contract_v1_matrix` -> pass
26. `coordinator_planner_registry_v1_matrix` -> pass
27. `quality_matrix_guardrails` -> pass
28. `traces_filtering_and_correlation` -> pass
29. `provider_fallback` -> pass

## Notes

- The smoke suite is deterministic by default.
- Network-dependent provider calls are not required for smoke pass.
- Any intended behavior change should update this file and the suite checks in
  `tools/smoke-test.sh`.
