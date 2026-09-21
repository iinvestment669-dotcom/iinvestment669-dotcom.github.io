# bb-autopilot

Single-file bug bounty recon + scan pipeline. Point it at an in-scope
domain, it enumerates subdomains, probes live hosts, crawls URLs, runs
nuclei, and produces a report with **candidate findings marked in red**.

> ⚠️ **This tool does NOT find bugs by itself.** It surfaces candidates.
> You verify them. You write the report.

## Legal

Authorized testing only — bug bounty programs you're enrolled in, or
systems you own / have written permission to test. The tool refuses to
run against anything not listed in `scope.txt`. Misuse is on you.

## Install

```bash
git clone https://github.com/iinvestments669-dotcom/bb-autopilot.git
cd bb-autopilot
pip install -r requirements.txt