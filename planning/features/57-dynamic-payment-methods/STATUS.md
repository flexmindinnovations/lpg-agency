# Status — 57 dynamic payment methods

M1–M5 built. Backend: ruff, mypy --strict, import-linter (7 contracts), OpenAPI check and 1523 unit tests pass. Apps: analyze clean; api_client, admin (104), customer (66) and driver (105) tests pass.

Behaviour change to know about: **card is no longer offered anywhere**, and **on credit** appears at the door only when the agency has a credit limit configured. An agency that wants either has to be given a setting for it (see Out of scope in PLAN.md).

M6 (live check on emulators) not yet done.
