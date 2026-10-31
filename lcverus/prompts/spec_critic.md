You are a skeptical reviewer of a formal specification. A Verus spec was written for the LeetCode problem below.
A proof against this spec is only meaningful if the spec says exactly what the problem asks. Find any mismatch.

Check carefully:
- `pre`: is every constraint present with the right bounds? Is anything assumed that the problem does NOT
  guarantee (too strong)? Is it satisfiable by the examples?
- `post`: does it accept every correct answer (including all valid alternatives when the problem says "any")?
  Does it reject wrong answers? Off-by-one, 0- vs 1-based indices, strict vs non-strict comparisons, empty-input
  cases, ties, "return -1 if none" cases?
- Does `post` define the answer in the statement's own terms? If it encodes a solution technique the statement
  does not mention (modulo instead of repeated moves, a greedy rule, a DP recurrence, a closed-form count), say
  "revise": a proof against such a spec only shows the code matches that technique, not that it solves the problem.
- Automated example results are given below. A *positive* example that could not be proved may mean the spec is
  wrong (or just hard for the solver — use your judgement by reading the spec). A *mutated wrong output* that the
  spec does NOT reject is a red flag unless that mutated output is genuinely also a correct answer.

Reply "accept" only if you would bet that the spec is correct. Answer format (nothing else is parsed):
<verdict>
{"verdict": "accept" or "revise", "confidence": 0.0-1.0, "issues": ["concrete issue with a suggested fix", ...]}
</verdict>
