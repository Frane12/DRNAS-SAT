# DRNAS automaton development

The user has chosen **one continuing automaton: DRNAS CORE**.

- Develop the automaton in `core/` on the continuing `development/drnas-core` branch. Increase its version and update its changelog. Do not create another numbered solver series or permanent experimental branch unless the user explicitly requests that change.
- Keep existing experiments as historical evidence. New functionality belongs in an existing kernel or a module of CORE with a shared interface, budget and proof contract.
- Do not merge into or rewrite `main` without a separate user request. A draft pull request is a review surface, not an instruction to merge.
- The primary goal is broader verified reasoning and transfer between methods; speed is secondary. CDCL fallback is an unresolved structural case and must never count as a CORE success. Reference solvers belong only in benchmarks.
- Every SAT model must satisfy the original CNF. Every UNSAT result needs separately checked evidence. Distinguish standard DRUP/DRAT from custom symbolic/capacity certificates. Audit exhaustion is unresolved.
- Keep source/proof provenance, a single monotonic solve budget, bounded kernels and an external timeout. Shared clauses must be justified; reconstruction state remains local to its kernel.
- Before changing a kernel, run `bash core/build.sh` and `python3 core/tests.py` after the change. For capability/performance claims, freeze the source and harness before generating a fresh paired panel. Report regressions as well as gains; do not tune on the same panel and call it blind.
- The vendored source hashes in `core/provenance.json` identify the imported baseline. Prefer changes in adapters; if a vendor file changes, record the patch and update provenance explicitly.

Unrelated repository tasks are outside this development convention.
