# Automation, Institutions, and Economic Freedom — reproducibility package 0.1.2

This package reproduces the synthetic two-date example associated with manuscript v22. It computes incidence, first-round direct demand, public accounts, installed capacity, future opportunity, cases A–E, analytical minima, conditional frontiers, a finite allocation problem, and sensitivity results. It does not solve the parent HANK–New Keynesian equilibrium, estimate parameters, simulate every chapter, or validate a country.

Spanish readers should begin with RECEIVER_GUIDE_ES.md. The canonical detailed procedure is docs/REPRODUCTION_ES.md.

## Files supplied alongside the ZIP

- automation-institutions-reproducibility-0.1.2.zip: source, frozen references, wheels, and standalone example.
- automation-institutions-reproducibility-0.1.2-linux-amd64-images.tar.gz: Docker runtime and documentation images.
- ENVIRONMENT_MANIFEST.json: exact Docker tags, image IDs, digests, platforms, and bundle hash.
- DEBIAN_PACKAGES.tsv: package inventory generated from the delivered images.
- SHA256SUMS.txt: transport-integrity hashes for the external release files. These checksums detect changes; they are not an independent signature of authorship.

## Main Windows workflow

Requirements: Windows AMD64, CPython 3.12, and the Python launcher available as py -3.12. Start in the newly extracted ZIP root. Use a new environment and a new run destination. Clear variables that could redirect imports to another checkout:

~~~powershell
Get-FileHash -Algorithm SHA256 PATH_TO_DELIVERED_ZIP
Remove-Item Env:PYTHONPATH,Env:PYTHONHOME,Env:BOOK_REPRO_ROOT -ErrorAction SilentlyContinue
py -3.12 --version
.\bootstrap_windows.ps1 -VenvPath .venv-0.1.2
$env:BOOK_REPRO_OFFLINE = "1"
$env:BOOK_REPRO_ROOT = (Get-Location).Path
$python = ".\.venv-0.1.2\Scripts\python.exe"
& $python -m book_repro verify-package --archive PATH_TO_DELIVERED_ZIP
& $python -m book_repro reproduce --output build\windows-run
& $python -m book_repro verify --run build\windows-run
& $python -m book_repro coverage --output build\coverage-structural.json
~~~

reproduce already runs the required test suite. python -m book_repro test is an optional diagnostic, not an additional step in the minimum sequence. Outputs such as results/ and independent/ are below the selected run directory—for example, build/windows-run/results and build/windows-run/independent.

## Main Linux/Docker workflow

Use a Docker engine capable of Linux containers; no particular Docker context name is universal. Verify the external bundle hash, load it, and consult ENVIRONMENT_MANIFEST.json for the effective image identities. From the extracted ZIP root:

~~~powershell
Get-FileHash -Algorithm SHA256 PATH_TO_DELIVERED_DOCKER_BUNDLE
docker load --input PATH_TO_DELIVERED_DOCKER_BUNDLE
docker image inspect book-repro-runtime:0.1.2
docker image inspect book-repro-docs:0.1.2
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-runtime:0.1.2 `
  python -m book_repro reproduce --output /work/build/linux-run
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-runtime:0.1.2 `
  python -m book_repro verify --run /work/build/linux-run
~~~

The mounted-source mode above is the public workflow: /work/build is the same host build directory. Running code incorporated at image-build time is a distinct diagnostic mode and is not mixed into this sequence. Rebuilding images from Dockerfile is an alternative that can require network access for Debian packages; numerical execution after preparation remains network-free.

## Compare platforms and build the PDF

After both runs exist:

~~~powershell
& $python -m book_repro compare-runs --windows build\windows-run --linux build\linux-run --output build\platform-comparison.json
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_OFFLINE=1 -e BOOK_REPRO_CONTAINER_NETWORK=none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-docs:0.1.2 `
  python -m book_repro build-docs --run /work/build/linux-run --output /work/build/linux-docs
docker run --rm --platform linux/amd64 --network none `
  -e BOOK_REPRO_ROOT=/work -e PYTHONPATH=/work/src `
  -v "${PWD}:/work" book-repro-docs:0.1.2 `
  pdfinfo /work/build/linux-docs/example_EN.pdf
~~~

The PDF is build/linux-docs/example_EN.pdf; its build report is build/linux-docs/build_docs_report.json. Render all pages with pdftoppm from the documentation image or an equivalent local Poppler installation and inspect them visually. Native document construction is optional and requires latexmk, pdflatex, and pdfinfo on PATH; numerical reproduction needs neither TeX nor Poppler.

## Optional manuscript checks

The standalone example and structural coverage check do not require the full book. Only these optional commands require a separately supplied, identified copy of manuscript v22:

~~~powershell
& $python -m book_repro coverage --manuscript PATH_TO_IDENTIFIED_V22_COPY --output build\coverage-with-manuscript.json
& $python -m book_repro check-book --manuscript PATH_TO_IDENTIFIED_V22_COPY --run build\windows-run --output build\book-check.json
~~~

The registry preserves 69 located supports and 13 supports pending location. A locator is not an independent re-derivation. Appendix A is the only reproduced numerical application; Chapters 7, 10, 11, 12, and 16 are linked through reduced interfaces, not full simulations.

## Scientific comparison and scope

CSV keys, rows, units, classifications, and text fields are exact. Floating values use atol + rtol * abs(expected) from config/tolerances.json. Generated LaTeX tables and SVGs are compared as exact UTF-8 after normalizing only line endings. The independent P3 checks use exact rational arithmetic; “P3” is retained as the technical identifier for the finite-oracle layer.

The optional --baseline argument may compare against a separately preserved historical run, but no historical run is needed for a clean Windows–Linux comparison.

The GitHub Actions file is configuration only: no public repository, remote CI execution, DOI, archival deposit, or editorial submission is claimed. Rights, authorship, ORCID, AI assistance, and third-party notices are documented in CITATION.cff, LICENSE_STATUS.md, docs/AI_ASSISTANCE.md, and THIRD_PARTY_NOTICES.md.
