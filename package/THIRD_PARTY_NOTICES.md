# Third-party notices

This package uses the following pinned Python components. License descriptions come from installed package metadata; the packages retain their own terms.

| Component | Version | Declared license metadata | Role |
|---|---:|---|---|
| ReportLab | 4.4.9 | BSD license; Copyright ReportLab Inc. | PDF/SVG figure generation |
| Pillow | 12.3.0 | MIT-CMU | Image support used by ReportLab |
| charset-normalizer | 3.5.1 | MIT | ReportLab dependency |
| setuptools | 80.9.0 | MIT | Local build backend |

Generated figures embed Bitstream Vera Sans. The complete bundled font notice is at assets/fonts/BITSTREAM_VERA_LICENSE.txt.

The Docker documentation target installs Debian packages for LaTeX, Latin Modern fonts, Poppler and GNU time. These packages are not copied into the source tree; the delivered images contain them under the licenses and notices supplied by Debian. Exact installed versions are listed in DEBIAN_PACKAGES.tsv, distributed alongside the Docker bundle.

GitHub Actions references actions/checkout, actions/setup-python, actions/upload-artifact and actions/download-artifact by public major-version tags. The workflow is configuration only; no remote run is claimed.
