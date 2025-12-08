#!/usr/bin/env python3
"""
buildthinkingmachine_bundle.py

Generates a complete Thinking Machine bundle for 126 agents (1 controller + 125 workers),
including configuration JSONs, controller/agent skeleton scripts, bootstrap scripts,
a runbook, and placeholder PDFs that will include the content you paste from the provided links.

USAGE:
    python3 buildthinkingmachine_bundle.py

NOTES:
- This script does NOT fetch the Copilot share URLs automatically. Paste the content
  from each URL into the PLACEHOLDERS/links_content.txt file (the script creates it).
- The script will attempt to install reportlab if not present to generate PDFs.
- Replace placeholder secrets and endpoints before deploying to production.
"""

import os, json, sys, textwrap, uuid, shutil, zipfile, subprocess
from pathlib import Path
from datetime import datetime

# -------------------------
# User-provided links (placeholders)
# -------------------------
LINKS = [
    "https://copilot.microsoft.com/shares/DXd1z5ugzeGQBr2ttAuhP",
    "https://copilot.microsoft.com/shares/U9kA9s753JzBaxx15Rb3M",
    "https://copilot.microsoft.com/shares/fNM8mfNJUr365JedXqk7ch",
    "https://copilot.microsoft.com/shares/HMUvsWTniVr2medBmtscS",
    "https://copilot.microsoft.com/shares/Gd59GbmhBTdMjJDp3N2Nh",
    "https://copilot.microsoft.com/shares/U9kA9s753JzBaxx15Rb3M"
]

# -------------------------
# Top-level bundle settings
# -------------------------
BUNDLEDIR = Path("thinkingmachine_bundle")
CONFIGSDIR = BUNDLEDIR / "configs"
AGENTSDIR = CONFIGSDIR / "agents"
ORCHDIR = CONFIGSDIR / "orchestrators"
AGGDIR = CONFIGSDIR / "aggregators"
SCRIPTSDIR = BUNDLEDIR / "scripts"
PLACEHOLDERSDIR = BUNDLEDIR / "PLACEHOLDERS"
PDFSDIR = BUNDLEDIR / "pdfs"

TOTAL_AGENTS = 126
UNITY_POINTS = [f"U{str(i+1).zfill(2)}" for i in range(36)]
LEAFPERUP = 3  # 36 * 3 = 108 gardeners
SUPPORTAGENTS = TOTAL_AGENTS - 1 - (36 * LEAFPERUP)  # controller excluded

# -------------------------
# Utility functions
# -------------------------
def ensure_dirs():
    for d in [BUNDLEDIR, CONFIGSDIR, AGENTSDIR, ORCHDIR, AGGDIR, SCRIPTSDIR, PLACEHOLDERSDIR, PDFSDIR]:
        d.mkdir(parents=True, exist_ok=True)

def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    print(f"Written {path}")

def safe_write(path: Path, text: str):
    path.write_text(text, encoding="utf-8")
    print(f"Written {path}")

def pip_install(pkg):
    try:
        import importlib
        importlib.import_module(pkg)
    except Exception:
        print(f"Installing {pkg} via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# -------------------------
# Generate configuration templates
# -------------------------
def generate_controller_config():
    cfg = {
        "nodeid": "controller001",
        "role": "controller",
        "host": "0.0.0.0",
        "port": 8443,
        "db": {"type": "sqlite", "path": "controller.db"},
        "tokenttlseconds": 3600,
        "provenance": {"ledger_path": "provenance/ledger.jsonl", "anchoring": "weekly"},
        "tls": {"enabled": False},
        "max_workers": 200,
        "audit": {"enabled": True}
    }
    write_json(CONFIGSDIR / "controller_config.json", cfg)

def generate_agent_configs():
    for up in UNITY_POINTS:
        for i, role in enumerate(["A", "B", "C"]):
            aid = f"gardener{up}{role}"
            cfg = {
                "agent_id": aid,
                "role": "gardener",
                "unity_point": up,
                "sector": f"face{(UNITY_POINTS.index(up)//6)+1}",
                "capabilities": ["build", "snapshot", "verify"],
                "resources": {"cpucores": 1, "memorymb": 2048},
                "gate_set": ["HG1", "HG12"],
                "heartbeatintervals": 10,
                "controllerurl": "http://CONTROLLERHOST:8443",
                "auth_token": "<injected at runtime>"
            }
            write_json(AGENTSDIR / f"{aid}.json", cfg)
    # Support agents (orchestrators, aggregators, leaders, storage, judge, monitor)
    for i in range(1, 7):
        oid = f"orchestratorface{i}"
        cfg = {"agentid": oid, "role": "orchestrator", "managedfaces": [f"face{i}"], "concurrencylimit": 6, "controllerurl": "http://CONTROLLERHOST:8443"}
        write_json(ORCHDIR / f"{oid}.json", cfg)
    for i in range(1, 7):
        aid = f"aggregatorface{i}"
        cfg = {"agentid": aid, "role": "aggregator", "managedfaces": [f"face{i}"], "mergepolicy": "sha256firstthenunion", "controllerurl": "http://CONTROLLER_HOST:8443"}
        write_json(AGGDIR / f"{aid}.json", cfg)
    # Storage nodes
    for i in range(1, 3):
        sid = f"storagenode{i}"
        cfg = {"agentid": sid, "role": "storage", "storepath": f"/data/storage{i}", "controllerurl": "http://CONTROLLER_HOST:8443"}
        write_json(CONFIGSDIR / f"{sid}.json", cfg)
    # Sector leaders and judge/monitor
    for i in range(1, 7):
        lid = f"sectorleaderface_{i}"
        cfg = {"agentid": lid, "role": "sectorleader", "face": f"face{i}", "controllerurl": "http://CONTROLLER_HOST:8443"}
        write_json(CONFIGSDIR / f"{lid}.json", cfg)
    write_json(CONFIGSDIR / "judgemonitor.json", {"agentid": "judgemonitor001", "role": "judge", "model": "MISTRAL13BGGUF_PLACEHOLDER"})

# -------------------------
# Generate skeleton scripts
# -------------------------
def generate_controller_app():
    content = textwrap.dedent("""\
    # controller_app.py
    # Minimal FastAPI controller skeleton for the Thinking Machine bundle.
    from fastapi import FastAPI
    from pydantic import BaseModel
    import sqlite3, json, os, time

    app = FastAPI(title="Commodore Controller")

    DB = "controller.db"
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        conn.execute("CREATE TABLE registry(agent_id TEXT PRIMARY KEY, meta TEXT)")
        conn.commit()
        conn.close()

    class RegisterPayload(BaseModel):
        agent_id: str
        role: str
        address: str = None
        capabilities: dict = {}

    @app.post("/register")
    def register(p: RegisterPayload):
        conn = sqlite3.connect(DB)
        conn.execute("INSERT OR REPLACE INTO registry(agentid, meta) VALUES (?,?)", (p.agentid, json.dumps(p.dict())))
        conn.commit(); conn.close()
        return {"status":"registered","agentid":p.agentid}

    @app.get("/task")
    def get_task(agentid: str = None):
        # Placeholder: implement task queue logic
        return {}

    @app.post("/report")
    def report(payload: dict):
        os.makedirs("provenance", exist_ok=True)
        entry = {"ts": time.time(), "payload": payload}
        with open("provenance/ledger.jsonl","a",encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\\n")
        return {"ok": True}
    """)
    safe_write(SCRIPTSDIR / "controller_app.py", content)

def generate_agent_worker():
    content = textwrap.dedent("""\
    # agent_worker.py
    # Minimal agent worker skeleton for the Thinking Machine bundle.
    import argparse, json, time, requests, hashlib
    from pathlib import Path

    def load_config(path):
        return json.load(open(path,encoding="utf-8"))

    def compute_sha(path):
        h = hashlib.sha256()
        h.update(Path(path).read_bytes())
        return h.hexdigest()

    def process_block(task, cfg):
        out = {"workid": task.get("workid","demo"), "agent": cfg["agent_id"], "result":"ok"}
        outpath = Path("work") / f"{cfg['agentid']}{int(time.time())}.json"
        outpath.parent.mkdir(exist_ok=True)
        outpath.write_text(json.dumps(out, ensure_ascii=False))
        return str(outpath)

    def report_result(cfg, workid, outpath, duration):
        sha = compute_sha(outpath)
        payload = {"agentid": cfg["agentid"], "workid": workid, "sha256": sha, "size": Path(outpath).stat().st_size, "duration_s": duration}
        try:
            requests.post(f"{cfg['controller_url']}/report", json=payload, timeout=10)
        except Exception as e:
            print("Report failed", e)

    def main():
        p = argparse.ArgumentParser()
        p.add_argument("--config", required=True)
        args = p.parse_args()
        cfg = load_config(args.config)
        try:
            requests.post(f"{cfg['controllerurl']}/register", json={"agentid":cfg["agent_id"], "role":cfg["role"], "capabilities":cfg.get("capabilities",{})}, timeout=5)
        except Exception as e:
            print("Register failed", e)
        while True:
            task = {"workid":"demo_task"}
            start = time.time()
            out = process_block(task, cfg)
            duration = time.time() - start
            report_result(cfg, task["workid"], out, duration)
            time.sleep(cfg.get("heartbeatintervals",10))

    if name == "main":
        main()
    """)
    safe_write(SCRIPTSDIR / "agent_worker.py", content)

def generate_bootstrap_sh():
    content = textwrap.dedent("""\
    # bootstrap.sh
    # Simple bootstrap to start controller and a subset of agents for pilot testing.
    uvicorn scripts.controller_app:app --host 0.0.0.0 --port 8443 --reload &
    sleep 1
    for cfg in configs/agents/*.json; do
      python3 scripts/agent_worker.py --config "$cfg" &
      sleep 0.02
    done
    echo "Bootstrap launched. Monitor logs."
    """)
    safe_write(BUNDLEDIR / "bootstrap.sh", content)

# -------------------------
# Generate runbook and PDFs (placeholders)
# -------------------------
def generate_runbook_text():
    runbook = textwrap.dedent(f"""\
    Thinking Machine Runbook
    Generated: {datetime.utcnow().isoformat()}Z

    Overview:
    - Total nodes: {TOTAL_AGENTS}
    - Unity Points: 36 (U01..U36)
    - Gardeners: 108 (3 per UP)
    - Support agents: {SUPPORTAGENTS}
    - Controller: 1

    Quick start:
    1. Install Python 3.10+, create venv, pip install -r requirements.txt
    2. Edit configs/controller_config.json and inject TLS and Vault endpoints
    3. Place agent configs in configs/agents/
    4. Start controller: uvicorn scripts.controller_app:app --host 0.0.0.0 --port 8443
    5. Start a pilot subset of agents using the bootstrap.sh script

    Placeholders:
    - The following Copilot share URLs were provided by the user. Paste their content into PLACEHOLDERS/links_content.txt:
    {chr(10).join(LINKS)}

    Security:
    - Use Vault for tokens and signing keys
    - Enable TLS in production
    - Rotate tokens regularly

    Provenance:
    - Ledger path: provenance/ledger.jsonl
    - Weekly anchoring: sign weekly digest with controller signing key

    Monitoring:
    - Expose /metrics on agents and controller
    - Use Prometheus + Grafana for dashboards

    See the PDF files in the pdfs/ folder for per-topic instructions and the full checklist.
    """)
    safe_write(BUNDLEDIR / "RUNBOOK.txt", runbook)

def generate_placeholders_file():
    lines = ["# PLACEHOLDERS: paste content from each Copilot share URL below.",
             "# For each URL, paste the full text or notes. After pasting, re-run the script to embed into PDFs.",
             ""]
    for i, url in enumerate(LINKS, start=1):
        lines.append(f"--- LINK {i} ---")
        lines.append(url)
        lines.append("")
        lines.append("[PASTE CONTENT HERE]")
        lines.append("")
    safe_write(PLACEHOLDERSDIR / "links_content.txt", "\n".join(lines))

def generate_pdfs_from_placeholders():
    # Use reportlab to create simple PDFs with placeholders embedded
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception:
        pip_install("reportlab")
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

    # Read placeholders file
    pc = (PLACEHOLDERSDIR / "links_content.txt").read_text(encoding="utf-8")
    # Create a PDF per major topic and one combined
    topics = {
        "Runbook": (BUNDLEDIR / "RUNBOOK.txt").read_text(encoding="utf-8"),
        "LinksContent": pc,
        "ConfigurationChecklist": "\n".join([
            "1. Controller & Registry",
            "2. Agent Identity & Provisioning",
            "3. Unity Points & Topology",
            "4. Agent Roles & Mapping",
            "5. Gate & Operator Registry",
            "6. Work Unit Schema",
            "7. Runtime Worker",
            "8. Orchestration Topology",
            "9. Storage & Artifact Management",
            "10. Provenance & Ledger",
            "11. Security & Secrets",
            "12. Monitoring & Observability",
            "13. Experiment Management",
            "14. Failure Modes & Recovery",
            "15. Governance & Ethics",
            "16. Deployment & Rollout",
            "17. Runbook & Incident Response"
        ])
    }
    for name, text in topics.items():
        pdfpath = PDFSDIR / f"{name}.pdf"
        c = canvas.Canvas(str(pdfpath), pagesize=A4)
        width, height = A4
        margin = 40
        y = height - margin
        lines = text.splitlines()
        c.setFont("Helvetica", 10)
        for line in lines:
            if y < margin + 20:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 10)
            c.drawString(margin, y, line[:200])
            y -= 12
        c.save()
        print(f"Generated PDF {pdfpath}")

# -------------------------
# Manifest and packaging
# -------------------------
def generate_manifest():
    manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "bundledir": str(BUNDLEDIR.resolve()),
        "totalagents": TOTAL_AGENTS,
        "unitypoints": UNITY_POINTS,
        "leafperup": LEAFPERUP,
        "supportagents": SUPPORTAGENTS,
        "notes": "Replace placeholders in PLACEHOLDERS/links_content.txt with the content from the Copilot share URLs."
    }
    write_json(BUNDLEDIR / "manifest.json", manifest)

def package_bundle():
    zippath = Path(f"{BUNDLEDIR.name}.zip")
    if zippath.exists():
        zippath.unlink()
    with zipfile.ZipFile(zippath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(BUNDLEDIR):
            for f in files:
                full = Path(root) / f
                z.write(full, full.relative_to(BUNDLEDIR.parent))
    print(f"Packaged bundle into {zippath}")

# -------------------------
# Main build flow
# -------------------------
def main():
    print("Building Thinking Machine bundle...")
    ensure_dirs()
    generate_controller_config()
    generate_agent_configs()
    generate_controller_app()
    generate_agent_worker()
    generate_bootstrap_sh()
    generate_runbook_text()
    generate_placeholders_file()
    generate_manifest()
    print("Generating placeholder PDFs (will embed any pasted link content)...")
    generate_pdfs_from_placeholders()
    package_bundle()
    print("Bundle build complete.")
    print(f"Open {PLACEHOLDERSDIR / 'links_content.txt'} and paste the content from each Copilot share URL into the matching section.")
    print("After pasting, re-run this script to regenerate PDFs with the embedded content.")

if __name__ == "__main__":
    main()
