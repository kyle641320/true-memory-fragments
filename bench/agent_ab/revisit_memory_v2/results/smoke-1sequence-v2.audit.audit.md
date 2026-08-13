# Audit

pass: **False**; valid sequences: **0/1**; issues: `[]`

```json
{
  "first_visit": {
    "CONTROL": {
      "n": 1,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 12,
      "source_bytes": 262,
      "prompt_tokens": 268,
      "completion_tokens": 42,
      "latency_seconds": 12.31171995215118,
      "memory_hits": 0,
      "memory_adoptions": 0
    },
    "TMF_MEMORY": {
      "n": 1,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 12,
      "source_bytes": 262,
      "prompt_tokens": 268,
      "completion_tokens": 42,
      "latency_seconds": 2.65000544115901,
      "memory_hits": 0,
      "memory_adoptions": 0
    }
  },
  "fresh_revisit": {
    "CONTROL": {
      "n": 1,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 12,
      "source_bytes": 262,
      "prompt_tokens": 271,
      "completion_tokens": 42,
      "latency_seconds": 2.505884200334549,
      "memory_hits": 0,
      "memory_adoptions": 0
    },
    "TMF_MEMORY": {
      "n": 1,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 0,
      "source_bytes": 0,
      "prompt_tokens": 267,
      "completion_tokens": 41,
      "latency_seconds": 2.5214247964322567,
      "memory_hits": 1,
      "memory_adoptions": 1
    }
  },
  "unknown_region": {
    "CONTROL": {
      "n": 1,
      "correct_rate": 0.0,
      "citation_rate": 0.0,
      "source_lines": 4,
      "source_bytes": 98,
      "prompt_tokens": 175,
      "completion_tokens": 27,
      "latency_seconds": 2.3067498952150345,
      "memory_hits": 0,
      "memory_adoptions": 0
    },
    "TMF_MEMORY": {
      "n": 1,
      "correct_rate": 0.0,
      "citation_rate": 0.0,
      "source_lines": 4,
      "source_bytes": 98,
      "prompt_tokens": 172,
      "completion_tokens": 24,
      "latency_seconds": 2.370324932038784,
      "memory_hits": 0,
      "memory_adoptions": 0
    }
  },
  "mutation_revisit": {
    "CONTROL": {
      "n": 1,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 12,
      "source_bytes": 262,
      "prompt_tokens": 272,
      "completion_tokens": 42,
      "latency_seconds": 2.496272748336196,
      "memory_hits": 0,
      "memory_adoptions": 0
    },
    "TMF_MEMORY": {
      "n": 1,
      "correct_rate": 1.0,
      "citation_rate": 1.0,
      "source_lines": 6,
      "source_bytes": 127,
      "prompt_tokens": 217,
      "completion_tokens": 40,
      "latency_seconds": 3.829646535217762,
      "memory_hits": 1,
      "memory_adoptions": 0
    }
  }
}
```
