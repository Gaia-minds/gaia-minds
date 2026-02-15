# Specialist Registry Contract v1

Updated: February 15, 2026

## Purpose

Define a deterministic specialist registry schema and ranking contract used by
Phase 4 coordinator planning (`#162`).

## Schema

```json
{
  "schema_version": 1,
  "specialists": [
    {
      "specialist_id": "research",
      "display_name": "Research Specialist",
      "capabilities": ["file_read", "memory_read", "network_request"],
      "risk_envelope": "low|medium|high|critical",
      "cost_hint": "low|medium|high",
      "latency_hint": "low|medium|high",
      "base_confidence": 0.0
    }
  ]
}
```

Field rules:

- `specialist_id`: unique, lowercase identifier.
- `capabilities`: normalized capability tokens (`file_read`, `file_write`, etc.).
- `risk_envelope`: maximum task risk this specialist can accept.
- `cost_hint`: coarse cost guidance for deterministic tie-breaking.
- `latency_hint`: coarse latency guidance for deterministic tie-breaking.
- `base_confidence`: normalized `0.0..1.0` confidence prior.

## Ranking Contract

For each coordinator task packet, rank specialists by deterministic score:

1. capability fit (`required_capabilities` overlap ratio)
2. confidence prior (`base_confidence`)
3. cost/latency adjustments (`low` > `medium` > `high`)
4. risk compatibility penalty when `task.risk_level` exceeds specialist
   `risk_envelope`
5. stable lexical tie-break on `specialist_id`

Output requirements per ranked candidate:

- `specialist_id`
- `score`
- `capability_fit`
- `estimated_confidence`
- `risk_compatible`

## Coordinator Output Coupling

Coordinator planner (`coordinator.plan.v1`) must emit:

- bounded subtask packets (`max_subtasks` enforced)
- ranked specialist candidates per task
- evaluator invocation output (`delegation.contract.v1`) per task

Planner task packet requirements for evaluator invocation:

- `task_id`
- `intent_class`
- `risk_level`
- `estimated_confidence`
- `required_capabilities`
- `available_capabilities`
- `candidate_specialists`
- `policy_decision`
- sandbox approval flags and fallback strategy

## Fixture Coverage

Deterministic fixtures and harness:

- `assistant/coordinator-planner-fixtures.json`
- `tools/coordinator-planner-check.sh`

Coverage guarantees:

- stable decomposition ordering and task ids
- deterministic specialist ranking order
- evaluator invocation on coordinator-produced task packets
- safety override propagation (`deny`/`fallback` paths)
