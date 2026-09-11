# Continuous-integration status and scope

The workflow at .github/workflows/reproduce.yml defines clean Windows and Linux numerical reproduction, cross-platform comparison, and a pinned Docker documentation build. The protected manuscript is absent, so check-book is explicitly not run in CI.

This distribution prepares and locally checks the configuration. It does not create a remote repository, trigger GitHub Actions or claim a green remote run. The machine-readable status is provenance/ci_status.json and remains remote_execution: not_run until an actual hosted execution supplies a URL, identifier and logs.

The Docker job uses network isolation after image construction. Direct platform jobs activate the Python socket guard after offline wheel installation. CI artifacts are scientific runs, not a publication bundle.
