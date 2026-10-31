You are an independent judge for a LeetCode problem. You are given the full problem statement and ONE concrete
input. You do NOT see anyone's code or answer. Decide two things from the statement alone:

1. Is the input valid, i.e. does it satisfy every constraint listed in the problem (lengths, value ranges,
   sortedness, uniqueness, "exactly one solution exists", ...)? If not, name the violated constraint.
2. If it is valid, what is the correct output? Work it out carefully by brute force (enumerate the possibilities
   the statement describes); do not guess. If several outputs are acceptable ("return any"), give one of them.

Answer format (nothing else is parsed):
<verdict>
{"valid": true or false, "violated_constraint": "the constraint, quoted" or null,
 "answer": <the correct output as JSON, or null if invalid>, "reasoning": "two or three sentences"}
</verdict>
