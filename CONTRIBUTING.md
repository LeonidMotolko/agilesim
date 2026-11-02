# Contributing

This repository is developed like a production project, even though it has a single author.
Nothing is committed straight to `main`.

## Workflow

1. Branch from an up-to-date `main`: `git switch -c <type>/<short-description>`.
2. Commit in small steps using [Conventional Commits](https://www.conventionalcommits.org/).
3. Push the branch and open a pull request into `main`; fill in the PR template.
4. Wait for CI to pass, then merge with **squash** so `main` keeps one commit per change.
5. Delete the branch after merging.

### Branch types

`feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`, `ci/`, for example `feat/rule-engine-wip-limits`.

### Commit messages

```
<type>(<optional scope>): <imperative summary, max ~72 chars>

<optional body: why, not what>
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
The `commit-msg` hook rejects anything else.

## Local setup

Python tooling is managed with [uv](https://docs.astral.sh/uv/); hooks with [pre-commit](https://pre-commit.com/).

```bash
uv tool install pre-commit
pre-commit install          # installs the pre-commit and commit-msg hooks
pre-commit run --all-files  # run every hook once on the whole repository
```

## Quality gates

| Gate | Tool | Where |
| --- | --- | --- |
| Lint and format (Python) | `ruff` | pre-commit, CI |
| Type check (Python) | `ty` | pre-commit, CI |
| Lint and format (TypeScript) | `eslint`, `prettier` | pre-commit, CI |
| Unit tests | `pytest`, `vitest` | CI |
| Secret scan | `gitleaks` | pre-commit |
| Dependency audit | `pip-audit`, `npm audit` | CI |

## Branch protection (recommended GitHub settings)

On `main`: require a pull request, require the CI checks to pass, require branches to be up to date,
and allow squash merging only.
