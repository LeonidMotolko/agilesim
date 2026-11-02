# Contributing

This repository is developed like a production project, even though it has a single author.
Nothing is committed straight to `main` or `dev`.

## Branching model

| Branch | Purpose | Who merges into it |
| --- | --- | --- |
| `main` | Released, demo-ready state. Only changes through a `dev` -> `main` pull request. | `dev` (when everything is ready) |
| `dev` | Integration branch. Always green; the base of all work. | feature branches |
| `<type>/<short-description>` | One change: a feature, a fix, a chore. Short-lived. | branched from `dev` |

```
main  ●───────────────────────────●  (release: dev -> main, merge commit)
       \                         /
dev     ●──●────●────●────●────●
            \  /      \  /
feat/..      ●          ●
```

## Workflow

1. Branch from an up-to-date `dev`: `git switch dev && git pull && git switch -c <type>/<short-description>`.
2. Commit in small steps using [Conventional Commits](https://www.conventionalcommits.org/).
3. Push the branch and open a pull request **into `dev`**; fill in the PR template.
4. Wait for CI to pass, then merge with **squash**, so `dev` keeps one commit per change.
5. Delete the feature branch after merging.
6. When `dev` is ready for a release or a defense milestone, open a pull request `dev` -> `main`
   and merge it with a **merge commit** (not squash), so the history of `dev` is preserved.
7. A hotfix on `main` is branched from `main`, merged into `main`, and then merged back into `dev`.

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
| Dependency audit | `pip-audit`, `pnpm audit` | CI |

## Branch protection (recommended GitHub settings)

On both `main` and `dev`: require a pull request, require the CI checks to pass, and require
branches to be up to date. Allow **squash** merging on `dev`; allow **merge commits** on `main`.
Set `dev` as the default branch so new pull requests target it automatically.
