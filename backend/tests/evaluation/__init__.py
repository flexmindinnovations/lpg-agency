"""Backtest cases for AI Operational Intelligence heuristics.

Each Stage 2-5 heuristic adds one `test_*.py` here that builds
point-in-time `Observation`s from seed data and asserts
`BacktestReport.beats_baseline` -- a heuristic that cannot beat its
named naive baseline fails CI, per
`22-ai-operational-intelligence/PLAN.md`.
"""
