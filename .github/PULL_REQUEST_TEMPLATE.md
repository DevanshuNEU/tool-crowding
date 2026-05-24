## Summary

<one-paragraph description of what this PR changes and why>

## Linked issue

Closes #__

## Motivation

<why is this change needed? cite the design doc, paper, or production incident that motivates it>

## Test plan

- [ ] `pytest tests/` passes locally (current target: 116 passing as of v0.1.0-pre-pilot)
- [ ] `ruff check tcrun/ tests/` clean
- [ ] `pyright tcrun/` clean (or new warnings explained in reviewer notes)
- [ ] New tests added for new behavior

## Pre-registration check

- [ ] This PR does NOT touch `design/PRE_REGISTRATION.md`, the locked thresholds, or the four scenario abstracts
- [ ] If it does: I have explicitly stated in the summary whether this change is motivated by pilot data we have not yet released

## Conflict of interest

- [ ] This PR does NOT add a server to the pool that I maintain or have a financial interest in
- [ ] If it does: COI is disclosed above and a leave-X-out sensitivity analysis is requested

## Breaking changes

- [ ] No breaking changes
- [ ] Breaking change documented in `CHANGELOG.md` under [Unreleased] with migration notes

## Docs

- [ ] Updated the relevant design doc or `harness/SPEC.md` section
- [ ] Updated `CHANGELOG.md`

## Reviewer notes

<anything reviewers should look at first; subtle decisions; alternative approaches considered>
