#!/usr/bin/env python
"""Scan Jupyter notebooks for things that behave differently in a browser Python (JupyterLite).

    python audit_notebooks.py FOLDER [--pyodide-version 314.0.5] [--offline] [--json report.json]
                              [--cache-dir DIR] [--interactive]

Prints, per notebook, evidence with cell numbers, graded stop / blocker / adaptation / note.
It reports; the reader (or the model running the skill) judges. references/audit-checklist.md
says what each finding means and the fix.

Network use (skipped with --offline): the Pyodide package list for the pinned kernel version
(cached under --cache-dir, default ~/.cache/jupyterlite-course-site), PyPI metadata for imports
that are not built in, and one HEAD request per remote image to see whether it is alive.
--interactive: the course will use the interactive matplotlib backend; plotting cells that do
not open their own figure are then reported (under that backend they draw into the previous one).
"""
import argparse, ast, glob, json, os, re, sys, urllib.error, urllib.request, warnings

ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("--pyodide-version")
ap.add_argument("--offline", action="store_true", help="no network: skip Pyodide/PyPI/image lookups")
ap.add_argument("--json", help="also write all findings to this JSON file")
ap.add_argument("--cache-dir", default=os.path.expanduser("~/.cache/jupyterlite-course-site"))
ap.add_argument("--interactive", action="store_true", help="report plotting cells that lack their own figure call")
args = ap.parse_args()
warnings.simplefilter("ignore")   # the notebooks' own invalid escapes would otherwise print SyntaxWarnings here

# ---------------------------------------------------------------------------------------- packages
STDLIB = set(sys.stdlib_module_names)
ALIASES = {"sklearn": "scikit-learn", "PIL": "pillow", "yaml": "pyyaml", "cv2": "opencv-python", "mpl_toolkits": "matplotlib",
           "IPython": "ipython", "skimage": "scikit-image", "Bio": "biopython", "dateutil": "python-dateutil", "bs4": "beautifulsoup4"}
pyodide_pkgs, pyver = set(), args.pyodide_version
if not pyver:
    try:
        from jupyterlite_pyodide_kernel.constants import PYODIDE_VERSION as pyver
    except Exception:
        pyver = None
if pyver and not args.offline:
    cache = os.path.join(args.cache_dir, f"pyodide-lock-{pyver}.json")
    try:
        if not os.path.exists(cache):
            os.makedirs(args.cache_dir, exist_ok=True)
            urllib.request.urlretrieve(f"https://cdn.jsdelivr.net/pyodide/v{pyver}/full/pyodide-lock.json", cache)
        for name, p in json.load(open(cache))["packages"].items():
            pyodide_pkgs.add(name.lower()); pyodide_pkgs.update(i.lower() for i in p.get("imports", []))
        print(f"Pyodide {pyver}: {len(pyodide_pkgs)} importable package names known (list cached in {args.cache_dir})")
    except Exception as e:
        print(f"(Pyodide package list unavailable: {e}; imports will be reported as unclassified)")
elif not pyver:
    print("(no Pyodide version known; pass --pyodide-version or install jupyterlite-pyodide-kernel)")

_pypi = {}
def pypi_info(dist):
    if dist not in _pypi:
        try:
            d = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{dist}/json", timeout=20))
            pure = any(f["filename"].endswith(("py3-none-any.whl", "py2.py3-none-any.whl")) for f in d["urls"])
            deps = sorted({re.split(r"[ ;<>=!~\[]", r)[0] for r in (d["info"].get("requires_dist") or []) if ";" not in r or "extra" not in r})
            _pypi[dist] = (pure, deps, d["info"].get("author") or d["info"].get("author_email") or "")
        except Exception:
            _pypi[dist] = (None, [], "")
    return _pypi[dist]

def classify(name):
    if name in STDLIB: return "stdlib", ""
    if name.lower() in pyodide_pkgs or ALIASES.get(name, "").lower() in pyodide_pkgs: return "in Pyodide", ""
    if not pyodide_pkgs: return "unclassified", ""
    if args.offline: return "not in Pyodide (check PyPI for a pure-Python wheel)", ""
    dist = ALIASES.get(name, name); pure, deps, author = pypi_info(dist)
    if pure is None: return "not in Pyodide; PyPI lookup failed (private or local module?)", ""
    if not pure: return "NOT AVAILABLE: compiled, not in Pyodide, no pure-Python wheel", ""
    missing = [d for d in deps if d.lower() not in pyodide_pkgs and d.lower() not in STDLIB]
    extra = (f"; also needs {', '.join(missing)} (not built in; bundle them too)" if missing else "") + (f"; author on PyPI: {author[:40]}" if author else "")
    return "pure Python on PyPI: needs `%pip install`, can be bundled", extra

# ---------------------------------------------------------------------------------------- patterns
REMOVED_APIS = {   # gone in the NumPy / Matplotlib versions current browser Pythons ship
    r"\bnp\.trapz\(": "np.trapz was removed in NumPy 2.4; use np.trapezoid (same arguments)",
    r"\bnp\.(in1d|row_stack|product|cumproduct|alltrue|sometrue|float_|complex_|string_|unicode_|NaN|Inf|infty|PINF|NINF)\b": "removed in NumPy 2.x; see the NumPy 2 migration guide",
    r"\bnp\.(int|float|bool|object|str)\b(?!\d|_)": "np.int / np.float / np.bool aliases were removed in NumPy 1.24; use int, float, bool or np.int64 etc.",
    r"gca\(\s*projection\s*=": "ax = fig.gca(projection='3d') was removed in Matplotlib 3.7; use fig.add_subplot(projection='3d') or plt.axes(projection='3d')",
    r"\bplt\.hold\(": "plt.hold was removed in Matplotlib 3.0",
}
CODE = {
    ("adaptation", "shell command (no shell in the browser)"): r"^\s*!\S",
    ("note", "other magic"): r"^\s*%(?!matplotlib|pip)\w+|^\s*%%\w+",
    ("note", "3D plotting"): r"projection\s*=\s*['\"]3d['\"]|Axes3D|plot_surface|plot_wireframe|scatter3D|plot3D|plot_trisurf",
    ("note", "widgets / sliders"): r"\binteract\w*\(|widgets\.\w+Slider|FloatSlider|IntSlider",
    ("adaptation", "path escaping the notebook folder"): r"['\"](?:\.\./\.\./|/Users/|/home/|[A-Z]:\\\\|~/)",
    ("blocker", "network access in code (no sockets in the browser; see checklist)"): r"requests\.\w+\(|urlopen\(|urlretrieve\(|read_csv\(\s*['\"]https?://|read_table\(\s*['\"]https?://|wget |curl ",
    ("blocker", "unsupported in the browser"): r"\bsubprocess\b|\bmultiprocessing\b|\bthreading\b|\btkinter\b|os\.system\(|drive\.mount|google\.colab",
    ("note", "file written by the notebook"): r"savefig\(|np\.save\(|to_csv\(|to_excel\(|pickle\.dump\(|SaveMy\w*\(",
    ("note", "HDF5 (arrays fine via h5py; pandas tables need PyTables, absent)"): r"h5py|h5io|read_hdf|to_hdf",
    ("note", "user input()"): r"\binput\(",
    ("note", "time.sleep (blocks the page)"): r"time\.sleep\(",
}
MARKDOWN = {
    ("adaptation", "remote image, plain http (blocked on an https site)"): r"<img[^>]+src=[\"']?http://|!\[[^\]]*\]\(\s*http://",
    ("adaptation", "remote image, https (vendor a copy; hosts disappear)"): r"<img[^>]+src=[\"']?https://|!\[[^\]]*\]\(\s*https://",
    ("adaptation", "image and caption in one paragraph (renders side by side)"): r"<img[^>]*>\s*(?:__Figure|\*\*Figure|<strong>Figure|<b>Figure)",
    ("adaptation", "environment-specific instruction (reword for the site)"): r"JupyterHub|Jupyterhub|Colab|\bValidate\b|\bSubmit\b|upload (?:arrow|button)|log ?out|Anaconda",
}
IMG_URL = re.compile(r"""<img[^>]+src=(["'])(https?://[^"']+)\1|<img[^>]+src=(https?://[^\s>"']+)|!\[[^\]]*\]\(\s*(https?://[^)\s]+)""")
DATA_REF = re.compile(r"""['"]([^'"\n]+?\.(?:pkl|pickle|csv|tsv|txt|dat|npy|npz|hdf5|h5|xlsx|xls|json|png|jpg|jpeg|gif))['"]""", re.I)
DATA_EXT = (".pkl", ".pickle", ".csv", ".tsv", ".txt", ".dat", ".npy", ".npz", ".hdf5", ".h5", ".xlsx", ".xls", ".json", ".png", ".jpg", ".jpeg", ".gif", ".py")
PLOT_CALL = re.compile(r"\bplt\.(plot|scatter|hist|bar|barh|imshow|contour|contourf|pcolormesh|semilogx|semilogy|loglog|errorbar|fill_between|step|stem|pie|boxplot)\(")
NEW_FIGURE = re.compile(r"plt\.(figure|subplots|subplot)\(|\.clear\(\)|\.cla\(\)|\.clf\(\)")
INSTRUCTOR_NAME = re.compile(r"instructor|solution|answer|_key\b|answerkey", re.I)

def strip_magics(src): return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("%", "!")))
def has_magic(src): return any(l.lstrip().startswith(("%", "!")) for l in src.splitlines())

_img_alive = {}
def image_alive(url):
    if args.offline: return "not checked (offline)"
    if url not in _img_alive:
        try:
            req = urllib.request.Request(urllib.parse.quote(url, safe=":/%?=&#"), method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            r = urllib.request.urlopen(req, timeout=15); ct = r.headers.get("Content-Type", "")
            _img_alive[url] = "alive" if ct.startswith("image/") else f"ALIVE BUT NOT AN IMAGE ({ct.split(';')[0]}; a captive portal or an HTML page)"
        except urllib.error.HTTPError as e: _img_alive[url] = f"DEAD (HTTP {e.code})"
        except Exception as e: _img_alive[url] = f"UNREACHABLE ({type(e).__name__})"
    return _img_alive[url]
import urllib.parse

# ---------------------------------------------------------------------------------------- scan
folder = os.path.abspath(args.folder)
nbs = sorted(f for f in glob.glob(os.path.join(folder, "**", "*.ipynb"), recursive=True) if ".ipynb_checkpoints" not in f)
all_files = [f for f in glob.glob(os.path.join(folder, "**", "*"), recursive=True) + glob.glob(os.path.join(folder, "**", ".*"), recursive=True)
             if os.path.isfile(f) and ".ipynb_checkpoints" not in f and not f.endswith(".DS_Store")]
all_files = sorted(set(all_files))
referenced = set()
report, summary = {}, []
print(f"\nScanning {len(nbs)} notebooks under {folder}\n")
for f in nbs:
    rel = os.path.relpath(f, folder); nb = json.load(open(f)); cells = nb.get("cells", []); meta = nb.get("metadata", {})
    findings = []
    def add(sev, label, cell, ev=""): findings.append((sev, label, cell, ev.strip()[:120]))
    if INSTRUCTOR_NAME.search(os.path.basename(f)): add("stop", "filename looks like an instructor/solution file", -1, os.path.basename(f))
    if "colab" in meta: add("note", "Colab metadata (harmless; the adapt script strips it)", -1)
    if any("nbgrader" in c.get("metadata", {}) for c in cells):
        locked = sum(1 for c in cells if c.get("metadata", {}).get("editable") is False)
        add("note", f"nbgrader metadata: autograding is out of scope; site serves this student version ({locked} cells carry editable:false, which the browser honours)", -1)
    if any(c.get("outputs") for c in cells): add("note", "saved outputs (the adapt script clears them)", -1)
    code_all = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
    backend_lines = re.findall(r"^\s*%matplotlib\s+(\w+)", code_all, re.M)
    uses_mpl = "matplotlib" in code_all
    will_be_interactive = args.interactive or "widget" in backend_lines or "notebook" in backend_lines
    has_install = {m for line in re.findall(r"^\s*%pip install.*$", code_all, re.M) for m in line.split()[2:] if not m.startswith("-")}
    imports = {}
    for i, c in enumerate(cells):
        src = "".join(c["source"])
        if c["cell_type"] == "code":
            try:
                tree = ast.parse(strip_magics(src))
            except SyntaxError:
                tree = None
                first = next((l.strip() for l in src.splitlines() if l.strip()), "")
                if re.search(r"\?|\.\.\.|fill|you fill|your code", src, re.I): add("note", "fill-in blank for students (leave as is)", i, first)
                else: add("note", "cell doesn't parse: a deliberate error example, or a typo? confirm with the instructor", i, first)
            if tree:
                names = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import): names.update(a.name.split(".")[0] for a in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0: names.add(node.module.split(".")[0])
                for n in names: imports.setdefault(n, i)
                if names and has_magic(src): add("adaptation", "magic line in the same cell as imports (the imports won't load in the browser)", i, src.splitlines()[0])
                if re.search(r"\binteract\w*\(", code_all):
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef) and PLOT_CALL.search(ast.get_source_segment(strip_magics(src), node) or "") and NEW_FIGURE.search(ast.get_source_segment(strip_magics(src), node) or ""):
                            add("adaptation", "slider callback opens a new figure each call (piles up under the interactive backend)", i, f"def {node.name}(...)")
            for m in re.finditer(r"^\s*%matplotlib\s+(\w+).*$", src, re.M):
                b = m.group(1); line = m.group(0).strip()
                if b == "notebook": add("adaptation", "`%matplotlib notebook`: backend no longer exists; use `%matplotlib widget` (+ ipympl install cell) or delete for static figures", i, line)
                elif b == "widget" and "ipympl" not in has_install: add("adaptation", "`%matplotlib widget` with no `%pip install -q ipympl` cell before it", i, line)
                elif b == "inline": add("note" if not has_magic(src) or len([l for l in src.splitlines() if l.strip()]) == 1 else "adaptation", "`%matplotlib inline` (unnecessary in the browser; harmless only in its own cell)", i, line)
            if will_be_interactive and PLOT_CALL.search(src) and not NEW_FIGURE.search(src) and "ax." not in src:
                add("adaptation", "plotting cell with no plt.figure(): under the interactive backend it draws into the previous figure", i, PLOT_CALL.search(src).group(0))
            for pat, why in REMOVED_APIS.items():
                for m in re.finditer(pat, src): add("blocker", why, i, src.splitlines()[src[:m.start()].count("\n")])
            if re.search(r"BEGIN SOLUTION|END SOLUTION|grader\.check\(|# BEGIN QUESTION", src): add("stop", "solution or autograder marker", i)
            for m in re.finditer(r"^\s*!pip install\s+(.*)$", src, re.M): add("adaptation", "`!pip install` -> `%pip install`", i, m.group(0))
            for m in re.finditer(r"^\s*%pip install\s+(.*)$", src, re.M): add("note", "runtime install (bundle these wheels)", i, m.group(0))
            for (sev, label), pat in CODE.items():
                for m in re.finditer(pat, src, re.M): add(sev, label, i, src.splitlines()[src[:m.start()].count("\n")])
            for m in DATA_REF.finditer(src):
                name = m.group(1)
                if name.startswith(("http://", "https://")) or "{" in name: continue
                if re.search(r"savefig|to_csv|to_excel|np\.save|pickle\.dump|SaveMy|['\"]w[b]?['\"]", src[max(0, m.start()-60):m.end()+30]): continue
                target = os.path.normpath(os.path.join(os.path.dirname(f), name)); referenced.add(target)
                if os.path.exists(target): add("note", "data file present where the notebook expects it", i, name)
                else:
                    hits = [os.path.relpath(x, folder) for x in all_files if os.path.basename(x) == os.path.basename(name)]
                    add("adaptation", "data file NOT where the notebook loads it" + (f" (found at {hits[0]})" if hits else " (not found anywhere under the folder; or loaded through a helper that builds the name)"), i, name)
        else:
            for (sev, label), pat in MARKDOWN.items():
                for m in re.finditer(pat, src): add(sev, label, i, src[m.start():m.start()+100].replace("\n", " "))
            for m in IMG_URL.finditer(src):
                url = m.group(2) or m.group(3) or m.group(4); add("adaptation", f"remote image is {image_alive(url)}", i, url)
    for n, i in sorted(imports.items()):
        k, extra = classify(n)
        sev = "blocker" if k.startswith("NOT AVAILABLE") else ("adaptation" if k.startswith(("pure Python", "not in Pyodide")) else "note")
        if k != "stdlib": add(sev, f"import {n}: {k}{extra}", i)
    # files beside the notebook that nothing names (loaded through helpers? leftovers? hidden?)
    folder_files = [x for x in all_files if os.path.dirname(x) == os.path.dirname(f) and not x.endswith(".ipynb")]
    for x in folder_files:
        if os.path.basename(x).startswith("."): add("adaptation", "hidden file (copied by the build but not listed, so the kernel can't open it); rename or drop", -1, os.path.basename(x))
        elif x.endswith(DATA_EXT) and x not in referenced and os.path.basename(x) not in code_all: add("note", "file in the folder that no notebook names literally (loaded through a helper, or a leftover?)", -1, os.path.basename(x))
    order = {"stop": 0, "blocker": 1, "adaptation": 2, "note": 3}
    uniq = []
    for x in findings:
        if x not in uniq: uniq.append(x)
    uniq.sort(key=lambda x: (order[x[0]], x[2]))
    counts = {k: sum(1 for x in uniq if x[0] == k) for k in order}
    summary.append(f"  {rel}: {counts['stop']} stop, {counts['blocker']} blockers, {counts['adaptation']} adaptations, {counts['note']} notes")
    report[rel] = [dict(severity=s, finding=l, cell=c, evidence=e) for s, l, c, e in uniq]
    print("=" * 100); print(f"{rel}  ({len(cells)} cells)")
    for s, l, c, e in uniq: print(f"  [{s:10s}] " + (f"cell {c:3d}: " if c >= 0 else "          ") + l + (f"  |  {e}" if e else ""))
print("\nSummary"); print("\n".join(summary))
print("\nSeverity: stop = must not enter the site; blocker = fails in the browser; adaptation = change needed; note = no action.")
if args.json:
    json.dump(report, open(args.json, "w"), indent=1); print(f"findings written to {args.json}")
