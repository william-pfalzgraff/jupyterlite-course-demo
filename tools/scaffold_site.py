#!/usr/bin/env python
"""Create a new JupyterLite course-site folder from the files in ../templates.

    python scaffold_site.py OUT_FOLDER --name "Physical Chemistry" [--interface tree|lab]
                            [--widgets] [--plotly] [--py3dmol] [--pint] [--wheel PKG==VER ...]
                            [--site-check-in-content] [--no-download]

Writes jupyter-lite.json, requirements.txt, .github/workflows/deploy.yml, .gitignore, robots.txt,
an empty content/ folder, tests/smoke_test.ipynb (local-only), and downloads the runtime wheels the
chosen features need into pypi/ (pure-Python wheels only). Prints the build commands at the end.
"""
import argparse, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ASSETS = os.path.join(os.path.dirname(HERE), "templates")
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--name", required=True)
ap.add_argument("--interface", choices=["tree", "lab"], default="tree")
for flag in ["widgets", "plotly", "py3dmol", "pint", "site-check-in-content", "no-download"]: ap.add_argument(f"--{flag}", action="store_true")
ap.add_argument("--wheel", nargs="*", default=[], help="extra runtime packages, pinned, e.g. uncertainties==3.2.2")
a = ap.parse_args()
OUT = os.path.abspath(a.out)
if os.path.exists(OUT) and os.listdir(OUT): raise SystemExit(f"{OUT} exists and is not empty")
for d in ["content", "pypi", "tests", ".github/workflows"]: os.makedirs(os.path.join(OUT, d), exist_ok=True)

# templates
cfg = open(os.path.join(ASSETS, "jupyter-lite.json")).read().replace("{{SITE_NAME}}", a.name).replace('"./tree"', f'"./{a.interface}"')
open(os.path.join(OUT, "jupyter-lite.json"), "w").write(cfg)
req = open(os.path.join(ASSETS, "requirements.txt")).read()
if a.plotly: req = req.replace("# plotly==", "plotly==")
open(os.path.join(OUT, "requirements.txt"), "w").write(req)
shutil.copy(os.path.join(ASSETS, "deploy.yml"), os.path.join(OUT, ".github/workflows/deploy.yml"))
shutil.copy(os.path.join(ASSETS, "gitignore"), os.path.join(OUT, ".gitignore"))
shutil.copy(os.path.join(ASSETS, "robots.txt"), os.path.join(OUT, "robots.txt"))
shutil.copy(os.path.join(ASSETS, "smoke_test.ipynb"), os.path.join(OUT, "tests", "smoke_test.ipynb"))
if a.site_check_in_content: shutil.copy(os.path.join(ASSETS, "smoke_test.ipynb"), os.path.join(OUT, "content", "00_site_check.ipynb"))

# runtime wheels (pure Python only); versions of the widget set must match requirements.txt
SETS = {
    # pinned to the set tested together on 2026-09-30; refresh deliberately, all at once, then re-test in a browser
    "widgets": ["ipympl==0.10.0", "ipywidgets==8.1.9", "jupyterlab_widgets==3.0.17", "widgetsnbextension==4.0.16", "comm==0.2.3", "traitlets==5.16.1", "typing_extensions==4.16.0"],
    "plotly": ["plotly==7.1.0", "narwhals==2.26.0", "packaging==26.3", "nbformat==5.11.1", "fastjsonschema==2.22.2", "jupyter_core==5.9.1", "platformdirs==4.11.4", "traitlets==5.16.1"],
    "py3dmol": ["py3Dmol==2.5.5"],
    "pint": ["pint==0.25.3", "flexcache==0.3", "flexparser==0.4", "platformdirs==4.11.4", "typing_extensions==4.16.0"],
}
wanted = []
for k, v in SETS.items():
    if getattr(a, k): wanted += v
wanted += a.wheel
wanted = list(dict.fromkeys(wanted))
if wanted and not a.no_download:
    print("downloading runtime wheels:", " ".join(wanted))
    subprocess.run([sys.executable, "-m", "pip", "download", "-q", "--no-deps", "-d", os.path.join(OUT, "pypi")] + wanted, check=True)
    bad = [w for w in os.listdir(os.path.join(OUT, "pypi")) if not w.endswith(("py3-none-any.whl", "py2.py3-none-any.whl"))]
    if bad: print("WARNING: not pure-Python, will not work in the browser:", bad)
    open(os.path.join(OUT, "pypi", "MANIFEST.txt"), "w").write("\n".join(sorted(os.listdir(os.path.join(OUT, "pypi")))) + "\n")
elif wanted:
    open(os.path.join(OUT, "pypi", "TODO_download.txt"), "w").write("pip download --no-deps -d pypi " + " ".join(wanted) + "\n")

open(os.path.join(OUT, "README.md"), "w").write(f"""# {a.name} notebook site (JupyterLite)

Build environment: `pip install -r requirements.txt` in a dedicated environment that contains nothing
else (every Jupyter extension installed there ends up in the site).

    jupyter lite build --contents content --contents tests --output-dir _output   # local preview incl. tests/
    (cd _output && python -m http.server 8000 &)                                  # open http://127.0.0.1:8000

Students need an internet connection the first time they open the site in a session: the browser
downloads Python itself (about 30 MB, then cached) from a CDN.

Clean rebuild after changing jupyter-lite.json, requirements.txt or pypi/:

    rm -rf _output .jupyterlite.doit.db && jupyter lite build --contents content --output-dir _output

Everything in content/ is public once published. Instructor and solution files stay out of this folder.
""")
print(f"site scaffolded at {OUT}\n  interface: {a.interface}  name: {a.name}\n  runtime wheels: {len(wanted)} requested")
print(f"next: pip install -r {OUT}/requirements.txt (in the build env), copy notebooks into content/, then build")
