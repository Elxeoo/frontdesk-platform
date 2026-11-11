# ADR-0002: Squash merge for pull requests

- **Status:** Accepted
- **Date:** 2026-11-11 (enforced by the ruleset since 2026-11-05)

## Context

Every change reaches `main` through a pull request: the ruleset requires one and blocks direct and force pushes.
Work on a branch often takes several attempts before the required checks pass. The Trivy gate (#14), for example,
had four commits, three of them red.

`main` is the history that gets released, and the version number and release notes are read from it. Every commit
there should be one change that passed the checks and can be reverted on its own.

## Decision

Pull requests are merged with squash merge only; the ruleset allows no other method, and the branch is deleted
after the merge. The squash commit title is the pull request title, written as a Conventional Commit; GitHub
appends the pull request number.

## Consequences

**Positive**

- One pull request is one commit on `main`. `git log --oneline` reads as a list of changes with their PR numbers.
- Every commit on `main` passed the required checks; there are no broken intermediate states.
- A bad change is undone with a single `git revert`.

**Negative**

- Intermediate commits disappear from `main`. They stay visible on the pull request page, but `git bisect` cannot
  narrow a problem down below the size of one pull request.
- A large pull request becomes one large commit, so pull requests have to stay small.

## Alternatives considered

- **Merge commit.** Keeps every branch commit plus a merge commit. Rejected: red attempts land on `main` and the
  history branches, which makes it harder to read.
- **Rebase merge.** Keeps every branch commit on a straight line. Rejected: red attempts still land on `main`, and
  every intermediate commit would have to pass the checks to keep `main` healthy.
