# Computational methods

## Scope

The executable object is a two-date, two-household reduced economy with synthetic parameters. It computes first-round incidence and direct demand, public cash and balance-sheet accounts, installed capacity, future service and opportunity, five cases A–E, analytical minima, conditional gate frontiers, a finite allocation problem and sensitivity grids. It does not solve the parent heterogeneous-agent New Keynesian equilibrium, estimate parameters, assign probabilities to long-run scenarios, or simulate every chapter.

## Inputs and domains

config/benchmark.json and config/scenarios.json are the only economic inputs. config/tolerances.json declares numeric comparison tolerances; text fields, units, keys, row sets, fractions and classifications are exact. Parameters and allocations are validated before generation. Prices are normalized as documented in docs/example_EN.tex; marginal spending coefficients are local affine responses rather than identities tying initial consumption to income.

## Calculation and verification

Generation imports no frozen references. It writes a new destination, records source and configuration hashes, runs the test suite, produces outputs and independent observations, and then invokes verification. reference/manifest.json freezes the expected files. The verifier checks schemas, composite keys, row sets, exact fields, finite numbers and values under the declared tolerance. A successful run is sealed by run_report.json and COMPLETE.json; verify is read-only.

## Independent checks

The P3 layer uses rational arithmetic and formulas separate from the production engine. Fourteen groups cover domains, household and public accounts, A–E, counterparties, exact frontiers, capacity corners, minima, fiscal limits, optimization vertices and three finite Chapter 16 result families. The 1,929 aggregate heterogeneous units are checks within a finite grid, not independent economies or a proof of global equilibrium.

## Platform protocol

Windows uses CPython 3.12 in a fresh virtual environment and bundled Windows AMD64 wheels. Linux uses linux/amd64, a base image pinned by digest, bundled Linux wheels and separate runtime and documentation targets. After preparation, calculation uses BOOK_REPRO_OFFLINE=1; Docker additionally uses --network none. The Python guard denies socket resolution and connections without altering the host firewall.

Cross-platform comparison uses the same keys and numeric tolerance as frozen-reference verification. CSV values, units, labels, classifications and exact P3 JSON values are compared. Generated LaTeX tables and SVG descriptions must have identical UTF-8 content after normalizing only line endings. PDF binaries need not match across systems because metadata and rendering can differ; source coordinates, tables, labels, page counts and visual output are checked.

## Document construction

build-docs consumes a verified current run and compiles docs/example_EN.tex. Numerical calculation does not need TeX or Poppler. Native construction needs latexmk, pdflatex and pdfinfo; visual inspection uses pdftoppm. The delivered documentation image supplies these tools. Manuscript correspondence is optional, requires an identified v22 source supplied separately, and never modifies it.

## Whole-book coverage

config/coverage.json and docs/coverage_by_chapter.md distinguish analytical support located, finite computational checks, reproduced numeric results, conceptual explanations and unimplemented modules. A located proof is not presented as an independent re-derivation. The only reproduced numerical application is the reduced example; module-level links to Chapters 7, 10, 11, 12 and 16 do not turn the package into a full-book simulation.

## Distribution contract

config/distribution_inclusion.json is an exact-file allowlist. package verifies a current run and document, copies only listed files, adds the autonomous example, writes per-file checksums and creates one deterministic-root ZIP. verify-package rejects unsafe paths, duplicate members, internal-material names, nested archives, a full-manuscript filename, missing members and checksum differences. Generated run histories and the v22 manuscript are not source members of the distribution.

The archive checksum, source payload hash, result-run hash and document payload hash are distinct. Environment images accompany the ZIP and retain their own external manifest and checksum. Loading a bundle into a Docker store that already contains its layers is recorded as such and is not represented as physical recovery from zero.
