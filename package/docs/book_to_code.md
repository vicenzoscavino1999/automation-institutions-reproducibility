# Book-to-code correspondence

## Interpretation rule

An implemented interface means that the reduced example instantiates a narrow object used by a chapter; it does not imply that the chapter's complete equilibrium or dynamic model is simulated. Formal-result locators are in docs/coverage_by_chapter.md. Appendix A numerical correspondences are in config/book_claims.json.

In the paths below, RUN_DIR is the directory passed to --output, such as build/windows-run. Production modules are under src/book_repro.

## Chapters 1–16

| Chapter | Book object | Package status | Executable or documentary location | Boundary |
|---:|---|---|---|---|
| 1 | Automation, access and economic freedom | Conceptual explanation | METHODS.md and this map | No aggregate transition path is solved. |
| 2 | Literature, assumptions and modular method | Conceptual explanation | provenance/source_manifest.json and coverage registry | Bibliographic claims are not recomputed. |
| 3 | HANK–New Keynesian parent core | Unimplemented module | Coverage locators | No household-distribution or NK equilibrium solution. |
| 4 | Tasks, displacement, complementarity and new work | Analytical support located; unimplemented numerically | Coverage locators | No continuous task assignment simulation. |
| 5 | Adoption, diffusion and organizational capital | Analytical support located; unimplemented numerically | Coverage locators | No firm-distribution or adoption-path solution. |
| 6 | Labor reallocation and bottlenecks | Analytical support located; unimplemented numerically | Coverage locators | No search-matching or training equilibrium. |
| 7 | Direct-demand incidence | Implemented reduced interface | RUN_DIR/results/scenarios.csv; src/book_repro/model.py; src/book_repro/generation.py | First-round demand only; no equilibrium-output claim without nominal closure. |
| 8 | Competition and AI rents | Analytical support located; unimplemented numerically | Coverage locators | No oligopoly, entry or data-feedback simulation. |
| 9 | Broad ownership and citizen funds | Analytical support located; unimplemented numerically | Coverage locators | No portfolio or fund equilibrium. |
| 10 | Fiscal capture and incidence | Implemented reduced interface | config/scenarios.json; RUN_DIR/results/cash_ledger.csv | One synthetic instrument; no empirical tax incidence. |
| 11 | State capacity, corruption and capture | Implemented reduced conversion parameter | RUN_DIR/results/scenarios.csv; RUN_DIR/results/sensitivity.csv | No estimated or stochastic state-capacity process. |
| 12 | Opportunity production | Implemented reduced interface | RUN_DIR/results/analytical_conditions.csv; RUN_DIR/results/scenarios.csv | One service technology; no sector-system simulation. |
| 13 | International transmission | Unimplemented module | Coverage locators | No second-country HANK or trade-equilibrium calculation. |
| 14 | Time allocation and life after work | Unimplemented module | Coverage locators | No household time-allocation solution. |
| 15 | Integrated welfare and scenario comparison | Unimplemented module | Coverage locators | No welfare aggregation or policy optimum. |
| 16 | Reachability and two transition gates | Three finite computational complements | RUN_DIR/independent/oracle_results.json; RUN_DIR/results/conditional_gate_regions.csv | No global viability kernel, transition probability or optimal path. |

## Appendices

| Unit | Status | Package relation |
|---|---|---|
| Appendix A, worked reduced economy | Reproduced numerical result | A–E example, ledgers, frontiers, maxima, sensitivities, document and 16 optional manuscript checks. |
| Appendices B–N | Analytical support located | Labels and proof/derivation locators only; no simulation is inferred. |
| Final notation and interface tables | Conceptual explanation | Coverage record only. |

## Implemented input-output chain

~~~text
synthetic income displacement
        -> legal coverage, compliance and tax collection
        -> administration, transfer, investment and dated reserve
        -> date-0 direct-demand change
        -> projected capacity and date-1 operating input
        -> service and opportunity gate
        -> finite joint-feasibility and sensitivity results
~~~

The chain is closed inside the two-date reduced economy. It is not fed back into the HANK parent, firm adoption, international transmission, time allocation or welfare blocks.

## Tests and oracles

The suite checks configuration, calculations, ledgers, schemas, sealing, adversarial mutations, document inputs and distribution contracts. P3 oracles independently reconstruct exact accounts, counterparties, gates, corner cases and optimization vertices. The Chapter 16 groups are C16_01, C16_02 and C16_03 in RUN_DIR/independent/oracle_results.json.
