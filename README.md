# Automation, Institutions, and Economic Freedom

Reproducibility package **0.1.2** by **Vicenzo Scavino Alfaro**, Independent Researcher, Lima, Peru.

This package implements a synthetic two-date economy connecting automation, household income incidence, fiscal allocation, first-round direct demand, institutional capacity and future opportunity. Cases A–E, conditional frontiers, allocation bounds and sensitivity calculations make these connections explicit and reproducible.

## Reproduce the example

The versioned release provides the exact ZIP, the Linux AMD64 Docker image bundle, the standalone example PDF, checksums and environment inventories. Download the release assets into one directory and follow **RECEIVER_GUIDE_ES.md**. The ZIP is the canonical offline distribution.

For a source checkout, the complete, unchanged ZIP payload is in **package/**. Run commands from that directory. See [the receiver guide](package/RECEIVER_GUIDE_ES.md), [the detailed procedure](package/docs/REPRODUCTION_ES.md) and [the package README](package/README.md). The Docker bundle is a separate release asset.

Requirements are Windows AMD64 with CPython 3.12, or Docker capable of Linux AMD64 containers. The documented calculations run without network access after environment preparation. A Docker rebuild may require network access.

## What is reproduced

- Five scenarios A–E, household and public accounts, and both demand and opportunity conditions.
- Analytical thresholds, conditional regions, finite allocation bounds and parameter sensitivities.
- A standalone ten-page example with generated tables and figures.
- 350 accounting and domain checks and 14 groups of exact finite checks.

Local verification passed 91 tests on Windows and 90 tests with one expected Windows-only omission on Linux. Scientific Windows–Linux comparisons passed 25/25 checks. See [publication status](PUBLICATION_STATUS.json) for the status of remote continuous integration and archival publication.

The application uses synthetic parameters. It reproduces the reduced example accompanying manuscript v22; it does not solve the complete HANK–New Keynesian equilibrium or provide country calibration. The formal-results registry distinguishes 69 located supports from 13 supports pending location. Existing-layer Docker loading was tested; recovery from an empty Docker store was not established.

## Manuscript, citation and rights

The accompanying manuscript is *Automation, Institutions, and Economic Freedom: A Theoretical Monograph on Technological Transition and Shared Prosperity*. The full manuscript is not included. Its optional correspondence checks require a separately supplied identified v22 source.

[CITATION.cff](CITATION.cff) identifies the software. Please also acknowledge the accompanying manuscript when discussing its theoretical framework. [AI assistance](package/docs/AI_ASSISTANCE.md) and [third-party notices](package/THIRD_PARTY_NOTICES.md) are included.

The files inside **package/** are the frozen 0.1.2 payload, including the historical local-publication status recorded at packaging. The current repository and archive status is recorded separately in **PUBLICATION_STATUS.json**, preserving all original checksums. Rights currently remain as stated in [RIGHTS.md](RIGHTS.md).
