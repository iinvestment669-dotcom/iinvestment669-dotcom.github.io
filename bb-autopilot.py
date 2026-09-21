#!/usr/bin/env python3
"""
bb-autopilot — single-file bug bounty recon + scan pipeline.

Point it at an in-scope domain, it enumerates subdomains, probes live hosts,
crawls URLs, runs nuclei, and produces a color-coded report of CANDIDATE
findings for you to manually verify.

AUTHORIZED TESTING ONLY. Requires scope.txt with in-scope domains.
This tool surfaces candidates — it does NOT confirm or exploit bugs.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
    from rich.console import Console
    from rich.panel import Panel
    from jinja2 import Template
except ImportError:
    print("Missing deps. Run: pip install -r requirements.txt")
    sys.exit(1)

console = Console()

# ---------------------------------------------------------------- config

SEVERITY_COLOR = {
    "critical": "#b30000",
    "high": "#d62728",
    "medium": "#e6a700",
    "low": "#3b7dd8",
    "info": "#6c757d",
    "unknown": "#6c757d",
}

DEFAULT_CONFIG = {
    "threads": 25,
    "rate_limit": 50,
    "nuclei_severity": ["low", "medium", "high", "critical"],
    "subfinder_timeout": 300,
    "httpx_timeout": 600,
    "katana_timeout": 600,
    "nuclei_timeout": 1800,
}

# ---------------------------------------------------------------- helpers


def have(tool):
    return shutil.which(tool) is not None


def run(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout
    except subprocess.TimeoutExpired:
        console.print(f"[yellow][!] timeout: {cmd}[/yellow]")
        return ""
    except Exception as e:
        console.print(f"[yellow][!] error: {e}[/yellow]")
        return ""


def load_scope(path="scope.txt"):
    p = Path(path)
    if not p.exists():
        return set()
    return {
        l.strip().lower()
        for l in p.read_text().splitlines()
        if l.strip() and not l.startswith("#")
    }


def in_scope(domain, scoped):
    d = domain.strip().lower()
    return any(d == e or d.endswith("." + e) for e in scoped)


# ---------------------------------------------------------------- stages


def stage_recon(domain, outdir, cfg):
    console.rule("[bold]1. Recon[/bold]")
    subs = set()

    if have("subfinder"):
        console.print("[*] subfinder")
        out = run(f"subfinder -d {domain} -silent",
                  cfg["subfinder_timeout"])
        subs.update(x.strip() for x in out.splitlines() if x.strip())
    else:
        console.print("[yellow][!] subfinder not found[/yellow]")

    console.print("[*] crt.sh")
    try:
        r = requests.get(
            f"https://crt.sh/?q=%25.{domain}&output=json", timeout=60
        )
        for entry in r.json():
            for name in entry.get("name_value", "").split("\n"):
                name = name.strip().lstrip("*.")
                if name.endswith(domain):
                    subs.add(name)
    except Exception as e:
        console.print(f"[yellow][!] crt.sh failed: {e}[/yellow]")

    subs = sorted(subs)
    (outdir / "subdomains.txt").write_text("\n".join(subs))
    console.print(f"[cyan]  -> {len(subs)} subdomains[/cyan]")
    return subs


def stage_probe(subs, outdir, cfg):
    console.rule("[bold]2. Probe[/bold]")
    if not subs:
        return []

    infile = outdir / "subdomains.txt"
    outfile = outdir / "live.txt"

    if have("httpx"):
        console.print("[*] httpx")
        run(
            f"httpx -l {infile} -silent -o {outfile} "
            f"-threads {cfg['threads']} -rate-limit {cfg['rate_limit']} "
            f"-status-code -title -tech-detect",
            cfg["httpx_timeout"],
        )
    else:
        console.print("[yellow][!] httpx not found — assuming https[/yellow]")
        outfile.write_text("\n".join(f"https://{s}" for s in subs))

    live = []
    if outfile.exists():
        live = [l.strip() for l in outfile.read_text().splitlines() if l.strip()]
    console.print(f"[cyan]  -> {len(live)} live hosts[/cyan]")
    return live


def stage_crawl(live, outdir, cfg):
    console.rule("[bold]3. Crawl[/bold]")
    if not live:
        return []

    infile = outdir / "live.txt"
    outfile = outdir / "urls.txt"

    if have("katana"):
        console.print("[*] katana")
        run(
            f"katana -list {infile} -silent -o {outfile} -d 3 -jc "
            f"-rate-limit {cfg['rate_limit']}",
            cfg["katana_timeout"],
        )
    else:
        console.print("[yellow][!] katana not found[/yellow]")

    urls = []
    if outfile.exists():
        urls = [l.strip() for l in outfile.read_text().splitlines() if l.strip()]
    console.print(f"[cyan]  -> {len(urls)} URLs[/cyan]")
    return urls


def stage_scan(live, outdir, cfg):
    console.rule("[bold]4. Scan[/bold]")
    findings = []

    if have("nuclei") and live:
        console.print("[*] nuclei")
        infile = outdir / "live.txt"
        json_out = outdir / "nuclei.jsonl"
        sev = ",".join(cfg["nuclei_severity"])

        run(
            f"nuclei -l {infile} -severity {sev} -jsonl -o {json_out} "
            f"-rate-limit {cfg['rate_limit']} -silent",
            cfg["nuclei_timeout"],
        )

        if json_out.exists():
            for line in json_out.read_text().splitlines():
                try:
                    findings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    else:
        console.print("[yellow][!] nuclei not found or no live hosts[/yellow]")

    console.print("[*] misconfig checks")
    findings.extend(misconfig_checks(live))
    console.print(f"[cyan]  -> {len(findings)} candidate findings[/cyan]")
    return findings


def misconfig_checks(live):
    paths = [
        ("/.git/HEAD", "Exposed .git directory"),
        ("/.env", "Exposed .env file"),
        ("/backup.zip", "Possible backup archive"),
        ("/phpinfo.php", "phpinfo() exposure"),
        ("/.DS_Store", "macOS .DS_Store exposure"),
        ("/server-status", "Apache server-status"),
    ]
    out = []
    for host in live[:50]:
        base = host.split()[0].rstrip("/")
        for path, label in paths:
            url = base + path
            try:
                r = requests.get(url, timeout=5, allow_redirects=False)
                if r.status_code == 200 and len(r.content) > 0:
                    out.append({
                        "template-id": "custom-misconfig",
                        "info": {"name": label, "severity": "medium"},
                        "matched-at": url,
                        "type": "http",
                    })
            except Exception:
                continue
    return out


# ---------------------------------------------------------------- report


def sev_of(f):
    return (f.get("info", {}).get("severity") or "unknown").lower()


def name_of(f):
    return f.get("info", {}).get("name") or f.get("template-id", "finding")


def url_of(f):
    return f.get("matched-at") or f.get("host") or f.get("url", "")


def color_of(f):
    return SEVERITY_COLOR.get(sev_of(f), "#6c757d")


def order(f):
    ranks = ["critical", "high", "medium", "low", "info", "unknown"]
    s = sev_of(f)
    return ranks.index(s) if s in ranks else 99


def stage_report(outdir, domain, subs, live, urls, findings):
    console.rule("[bold]5. Report[/bold]")
    findings = sorted(findings, key=order)

    tpl = Template("""# bb-autopilot report — {{ domain }}

> **Candidate findings only.** Verify each manually before reporting.
> <span style="color:#d62728">●</span> red = high/critical ·
> <span style="color:#e6a700">●</span> yellow = medium ·
> <span style="color:#3b7dd8">●</span> blue = low/info

## Summary
- Subdomains: **{{ subs|length }}**
- Live hosts: **{{ live|length }}**
- URLs: **{{ urls|length }}**
- Candidates: **{{ findings|length }}**

## Candidate Findings

{% if findings %}
{% for f in findings %}
### <span style="color:{{ color(f) }}">● {{ name(f) }}</span>

- **Severity:** <span style="color:{{ color(f) }}">**{{ sev(f)|upper }}**</span>
- **Matched at:** `{{ url(f) }}`
- **Template:** `{{ f.get('template-id','n/a') }}`

Verify manually. Check scope. Check Hacktivity for duplicates. Then write
your Bugcrowd report.

{% endfor %}
{% else %}
_No candidates. That's normal — use the recon data for manual hunting._
{% endif %}

## Live Hosts
{% for h in live %}- `{{ h }}`
{% endfor %}

## Subdomains
{% for s in subs %}- `{{ s }}`
{% endfor %}

---
_Generated by bb-autopilot. Authorized testing only._
""")

    md = tpl.render(
        domain=domain, subs=subs, live=live, urls=urls, findings=findings,
        sev=sev_of, name=name_of, url=url_of, color=color_of,
    )
    (outdir / "report.md").write_text(md)
    (outdir / "report.html").write_text(md_to_html(md, domain))
    console.print(f"[green][+] {outdir}/report.md[/green]")
    console.print(f"[green][+] {outdir}/report.html[/green]")


def md_to_html(md, domain):
    h = md
    h = re.sub(r"^### (.*)$", r"<h3>\1</h3>", h, flags=re.M)
    h = re.sub(r"^## (.*)$", r"<h2>\1</h2>", h, flags=re.M)
    h = re.sub(r"^# (.*)$", r"<h1>\1</h1>", h, flags=re.M)
    h = re.sub(r"`([^`]+)`", r"<code>\1</code>", h)
    h = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", h)
    h = re.sub(r"^- (.*)$", r"<li>\1</li>", h, flags=re.M)
    h = re.sub(r"(<li>.*?</li>\n?)+", r"<ul>\g<0></ul>", h, flags=re.S)
    h = h.replace("\n\n", "</p><p>")
    css = """
    body{font-family:-apple-system,system-ui,sans-serif;max-width:900px;
    margin:2rem auto;padding:0 1rem;line-height:1.55;color:#222}
    code{background:#f4f4f4;padding:2px 6px;border-radius:4px}
    h1{border-bottom:2px solid #eee;padding-bottom:.3rem}
    blockquote{background:#fff3cd;border-left:4px solid #e6a700;
    padding:.8rem 1rem;border-radius:4px;margin:1rem 0}
    """
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>bb-autopilot — {domain}</title><style>{css}</style></head>
<body><p>{h}</p></body></html>"""


# ---------------------------------------------------------------- main


def banner():
    console.print(Panel.fit(
        "[bold red]bb-autopilot[/bold red]\n"
        "[dim]recon + scan pipeline · authorized testing only[/dim]",
        border_style="red",
    ))


def main():
    banner()
    ap = argparse.ArgumentParser(
        description="Bug bounty recon + scan pipeline. Authorized use only."
    )
    ap.add_argument("domain", help="Root domain (must be in scope.txt)")
    ap.add_argument("--scope", default="scope.txt")
    ap.add_argument("--outdir", default="output")
    args = ap.parse_args()

    scoped = load_scope(args.scope)
    if not scoped:
        console.print(f"[bold red][!] {args.scope} missing or empty.[/bold red]")
        console.print("[red]Create it and list in-scope domains.[/red]")
        sys.exit(1)

    if not in_scope(args.domain, scoped):
        console.print(
            f"[bold red][!] '{args.domain}' not in {args.scope}.[/bold red]"
        )
        console.print("[red]Refusing to run. Add it if you're authorized.[/red]")
        sys.exit(1)

    console.print(f"[green][+] Scope OK:[/green] {args.domain}\n")

    cfg = DEFAULT_CONFIG
    outdir = Path(args.outdir) / args.domain
    outdir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    subs = stage_recon(args.domain, outdir, cfg)
    live = stage_probe(subs, outdir, cfg)
    urls = stage_crawl(live, outdir, cfg)
    findings = stage_scan(live, outdir, cfg)
    stage_report(outdir, args.domain, subs, live, urls, findings)

    console.print(
        f"\n[bold green]Done in {time.time()-t0:.1f}s.[/bold green]"
    )
    console.print(
        "[bold yellow]Reminder:[/bold yellow] verify every finding manually "
        "before reporting. No auto-exploit. Write your own Bugcrowd report."
    )


if __name__ == "__main__":
    main()