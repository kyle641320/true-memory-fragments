# Audit

pass: **False**; valid sequences: **2/3**; issues: `[]`

```json
{
  "first_visit": {
    "CONTROL": {
      "n": 3,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 33,
      "source_bytes": 842,
      "prompt_tokens": 1127,
      "completion_tokens": 123,
      "latency_seconds": 10.68880426697433,
      "memory_hits": 0,
      "memory_adoptions": 0,
      "format_repairs": 0,
      "format_repair_rate": 0.0
    },
    "TMF_MEMORY": {
      "n": 3,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 33,
      "source_bytes": 842,
      "prompt_tokens": 1127,
      "completion_tokens": 123,
      "latency_seconds": 13.572889603674412,
      "memory_hits": 0,
      "memory_adoptions": 0,
      "format_repairs": 0,
      "format_repair_rate": 0.0
    }
  },
  "fresh_revisit": {
    "CONTROL": {
      "n": 3,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 33,
      "source_bytes": 842,
      "prompt_tokens": 1136,
      "completion_tokens": 123,
      "latency_seconds": 8.707505812868476,
      "memory_hits": 0,
      "memory_adoptions": 0,
      "format_repairs": 0,
      "format_repair_rate": 0.0
    },
    "TMF_MEMORY": {
      "n": 3,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 0,
      "source_bytes": 0,
      "prompt_tokens": 1155,
      "completion_tokens": 120,
      "latency_seconds": 7.6290784776210785,
      "memory_hits": 3,
      "memory_adoptions": 3,
      "format_repairs": 0,
      "format_repair_rate": 0.0
    }
  },
  "unknown_region": {
    "CONTROL": {
      "n": 3,
      "correct_rate": 0.6666666666666666,
      "citation_rate": 0.6666666666666666,
      "source_lines": 15,
      "source_bytes": 408,
      "prompt_tokens": 903,
      "completion_tokens": 125,
      "latency_seconds": 12.775648714974523,
      "memory_hits": 0,
      "memory_adoptions": 0,
      "format_repairs": 0,
      "format_repair_rate": 0.0
    },
    "TMF_MEMORY": {
      "n": 3,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 15,
      "source_bytes": 408,
      "prompt_tokens": 894,
      "completion_tokens": 216,
      "latency_seconds": 10.401250947266817,
      "memory_hits": 0,
      "memory_adoptions": 0,
      "format_repairs": 0,
      "format_repair_rate": 0.0
    }
  },
  "mutation_revisit": {
    "CONTROL": {
      "n": 3,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 33,
      "source_bytes": 841,
      "prompt_tokens": 1139,
      "completion_tokens": 123,
      "latency_seconds": 8.427404960617423,
      "memory_hits": 0,
      "memory_adoptions": 0,
      "format_repairs": 0,
      "format_repair_rate": 0.0
    },
    "TMF_MEMORY": {
      "n": 3,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 18,
      "source_bytes": 320,
      "prompt_tokens": 958,
      "completion_tokens": 117,
      "latency_seconds": 12.194168852642179,
      "memory_hits": 3,
      "memory_adoptions": 0,
      "format_repairs": 0,
      "format_repair_rate": 0.0
    }
  }
}
```
