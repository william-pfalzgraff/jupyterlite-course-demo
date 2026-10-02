#!/usr/bin/env python
"""Apply the mechanical JupyterLite adaptations to a folder of notebooks, writing converted copies
and a change log. The originals are never modified.

    python adapt_notebooks.py SRC_FOLDER OUT_FOLDER [--backend widget|keep|static] [--ensure-figure]
                              [--pip PKG ...] [--no-images] [--log FILE]

Backend policy (matplotlib):
  widget  (default) interactive everywhere: `%matplotlib notebook|inline` become `%matplotlib widget`,
          and notebooks that use matplotlib but have no backend line get a `%matplotlib widget` cell
  keep    convert `%matplotlib notebook` to `widget`; leave notebooks without a backend line static
  static  remove every matplotlib backend line (static figures are the browser default)
--ensure-figure: in notebooks that end up interactive, insert `plt.figure()` at the top of plotting
  cells that don't open their own figure (under the interactive backend such cells draw into the
  previous figure). Off by default because it edits cells students read; every insertion is logged.

Also, per notebook (every edit logged with the ORIGINAL cell number, as the instructor's masters
number them):
  * any magic sharing a cell with other code moves to its own cell; a cell left with only comments
    after that is dropped (logged with its text)
  * `!pip install` -> `%pip install`; `np.trapz(` -> `np.trapezoid(` (removed in NumPy 2.4, same behaviour)
  * one `%pip install -q ...` cell before the first use of packages that are not part of Pyodide:
    ipympl (interactive backend), ipywidgets, plotly (+nbformat), py3Dmol, pint, plus --pip extras
  * remote images in markdown are downloaded into images/ beside the notebook (only if the server
    returns an image content type) and the reference is rewritten; failures are logged
  * a <br> is inserted between an inline image and a caption that follows it in the same paragraph
  * outputs cleared, Colab metadata removed, kernel set to the browser kernel
Files other than notebooks are copied with their relative paths, except that a data file a notebook
loads by bare name from a subfolder is copied beside the notebook instead (no duplicates).
Files whose names look like instructor/solution material are NOT copied; the log says so.
The log is written OUTSIDE the output folder (default: <OUT>-CONVERSION_LOG.md) so students never see it.
"""
import argparse, glob, os, re, shutil, urllib.parse, urllib.request
import nbformat
from nbformat.v4 import new_code_cell

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--backend", choices=["widget", "keep", "static"], default="widget")
ap.add_argument("--ensure-figure", action="store_true")
ap.add_argument("--pip", nargs="*", default=[], help="extra packages for the install cell")
ap.add_argument("--no-images", action="store_true", help="leave remote images as they are")
ap.add_argument("--log", help="where to write the change log (default: next to OUT)")
args = ap.parse_args()
SRC, OUT = os.path.abspath(args.src), os.path.abspath(args.out)
LOG = os.path.abspath(args.log) if args.log else OUT.rstrip("/") + "-CONVERSION_LOG.md"
if os.path.exists(OUT) and glob.glob(os.path.join(OUT, "**", "*.ipynb"), recursive=True):
    raise SystemExit(f"{OUT} already contains notebooks; choose a fresh output folder")
os.makedirs(OUT, exist_ok=True)

INSTRUCTOR = re.compile(r"instructor|solution|answer|_key\b|answerkey", re.I)
RUNTIME_PKGS = {"ipywidgets": "ipywidgets", "plotly": "plotly nbformat", "py3Dmol": "py3Dmol", "pint": "pint"}
DATA_REF = re.compile(r"""['"]([^'"/\n]+?\.(?:pkl|pickle|csv|tsv|txt|dat|npy|npz|hdf5|h5|xlsx|xls|json))['"]""", re.I)
IMG = re.compile(r"""(<img[^>]+src=)(["'])(https?://[^"']+)\2|(<img[^>]+src=)()(https?://[^\s>"']+)()|(!\[[^\]]*\]\()(https?://[^)\s]+)(\))""")
CAPTION = re.compile(r"(<img[^>]*>)\s*(?=(?:__Figure|\*\*Figure|<strong>Figure|<b>Figure))")
MAGIC = re.compile(r"^\s*[%!]")
PLOT_CALL = re.compile(r"\bplt\.(plot|scatter|hist|bar|barh|imshow|contour|contourf|pcolormesh|semilogx|semilogy|loglog|errorbar|fill_between|step|stem|pie|boxplot)\(")
NEW_FIGURE = re.compile(r"plt\.(figure|subplots|subplot)\(|\.clear\(\)|\.cla\(\)|\.clf\(\)")
log = ["# Conversion log", "", f"Source: `{SRC}`", f"Output: `{OUT}`", f"Backend policy: {args.backend}" + ("; --ensure-figure" if args.ensure_figure else ""),
       "", "Cell numbers are the ORIGINAL notebook's (0-based, counting markdown cells), so they match the instructor's master copies.", ""]

all_files = sorted(f for f in glob.glob(os.path.join(SRC, "**", "*"), recursive=True) if os.path.isfile(f) and ".ipynb_checkpoints" not in f and not f.endswith(".DS_Store"))
moved_beside = set()   # data files copied next to a notebook; not copied again at their original path

def fetch_image(url, images_dir):
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(url).path))) or "image"
    if not os.path.splitext(name)[1]: name += ".png"
    os.makedirs(images_dir, exist_ok=True); dest = os.path.join(images_dir, name)
    if os.path.exists(dest): return name, None
    try:
        req = urllib.request.Request(urllib.parse.quote(url, safe=":/%?=&#"), headers={"User-Agent": "Mozilla/5.0"})
        r = urllib.request.urlopen(req, timeout=30); ct = r.headers.get("Content-Type", "")
        if not ct.startswith("image/"): raise ValueError(f"server returned {ct.split(';')[0] or 'unknown type'}, not an image")
        data = r.read()
        if len(data) < 200: raise ValueError(f"only {len(data)} bytes")
        open(dest, "wb").write(data); return name, None
    except Exception as e:
        return None, str(e)

# ---- notebooks ------------------------------------------------------------------------------
for f in sorted(x for x in all_files if x.endswith(".ipynb")):
    rel = os.path.relpath(f, SRC); log.append(f"\n## {rel}")
    if INSTRUCTOR.search(os.path.basename(f)): log.append("- NOT COPIED: filename looks like instructor/solution material"); continue
    nb = nbformat.read(f, as_version=4); cells = nb.cells; changes = []
    for k, c in enumerate(cells): c.metadata["_orig"] = k          # remember original numbering
    def orig(c): return c.metadata.get("_orig", "new")
    out_dir = os.path.join(OUT, os.path.dirname(rel)); os.makedirs(out_dir, exist_ok=True)
    code_all = "\n".join(c.source for c in cells if c.cell_type == "code")
    uses_mpl = "matplotlib" in code_all
    had_backend = bool(re.search(r"^\s*%matplotlib\s+\w+", code_all, re.M))
    interactive = uses_mpl and (args.backend == "widget" or (args.backend == "keep" and had_backend))

    # 1. magics: backend policy, and every magic into its own cell
    i = 0
    while i < len(cells):
        c = cells[i]
        if c.cell_type != "code": i += 1; continue
        lines = c.source.splitlines(); rest, magics = [], []
        for l in lines:
            if re.match(r"\s*%matplotlib\s+\w+", l):
                if interactive:
                    if l.strip() != "%matplotlib widget": changes.append(f"cell {orig(c)}: `{l.strip()}` -> `%matplotlib widget`")
                    magics.append("%matplotlib widget")
                else:
                    changes.append(f"cell {orig(c)}: `{l.strip()}` removed (static figures are the browser default)")
            elif re.match(r"\s*!pip install", l):
                changes.append(f"cell {orig(c)}: `{l.strip()}` -> `%pip install`"); magics.append(l.strip().replace("!pip", "%pip", 1))
            elif MAGIC.match(l): magics.append(l.strip())
            else: rest.append(l)
        magics = list(dict.fromkeys(magics))
        rest_src = "\n".join(rest).strip("\n")
        rest_is_comment_only = rest_src and all(l.strip().startswith("#") or not l.strip() for l in rest)
        if magics and rest_src and not rest_is_comment_only:
            c.source = rest_src; new = new_code_cell("\n".join(magics)); new.metadata["_orig"] = f"{orig(c)}a"
            cells.insert(i, new); changes.append(f"cell {orig(c)}: magic line(s) moved to their own cell ({'; '.join(magics)})"); i += 2; continue
        elif magics:
            if rest_is_comment_only: changes.append(f"cell {orig(c)}: comment left over after separating the magic was dropped: {rest_src.strip()[:80]!r}")
            c.source = "\n".join(magics)
        elif not rest_src and any(MAGIC.match(l) for l in lines):
            changes.append(f"cell {orig(c)}: cell held only a removed backend line; deleted"); del cells[i]; continue
        elif not rest_src and rest_is_comment_only is False and lines and all(l.strip().startswith("#") or not l.strip() for l in lines) and any("matplotlib" in l for l in lines):
            pass
        i += 1
    if interactive and not had_backend:
        first = next((j for j, c in enumerate(cells) if c.cell_type == "code" and "matplotlib" in c.source), 0)
        new = new_code_cell("%matplotlib widget"); new.metadata["_orig"] = "new"; cells.insert(first, new)
        changes.append(f"before cell {orig(cells[first + 1])}: added `%matplotlib widget` (notebook had no backend line; policy = interactive everywhere)")
    elif uses_mpl and not interactive and args.backend == "keep" and not had_backend:
        changes.append("no backend line and policy = keep: figures stay static")

    # 2. plotting cells without their own figure (interactive only)
    if interactive:
        for c in cells:
            if c.cell_type == "code" and PLOT_CALL.search(c.source) and not NEW_FIGURE.search(c.source) and "ax." not in c.source:
                if args.ensure_figure:
                    c.source = "plt.figure()   # start a new figure: the interactive backend keeps earlier figures open\n" + c.source
                    changes.append(f"cell {orig(c)}: `plt.figure()` inserted at the top (plots without it would draw into the previous figure)")
                else:
                    changes.append(f"cell {orig(c)}: NOTE plotting cell with no plt.figure(); under the interactive backend it draws into the previous figure (run with --ensure-figure, or edit by hand)")

    # 2b. safe renames of functions removed from current NumPy (identical arguments and results)
    for c in cells:
        if c.cell_type == "code" and "np.trapz(" in c.source:
            k = c.source.count("np.trapz("); c.source = c.source.replace("np.trapz(", "np.trapezoid(")
            changes.append(f"cell {orig(c)}: {k} x `np.trapz(` -> `np.trapezoid(` (np.trapz was removed in NumPy 2.4; same arguments and result)")

    # 3. install cell
    code_all = "\n".join(c.source for c in cells if c.cell_type == "code")
    pkgs = ["ipympl"] if interactive else []
    for imp, pkg in RUNTIME_PKGS.items():
        if re.search(rf"^\s*(?:import|from)\s+{imp}\b", code_all, re.M): pkgs += pkg.split()
    pkgs += [p for p in args.pip if p not in pkgs]
    if pkgs:
        pkgs = list(dict.fromkeys(pkgs)); line = "%pip install -q " + " ".join(pkgs)
        existing = next((c for c in cells if c.cell_type == "code" and c.source.strip().startswith("%pip install")), None)
        if existing is not None:
            if existing.source.strip() != line: existing.source = line; changes.append(f"cell {orig(existing)}: install cell updated to `{line}`")
        else:
            first = next((j for j, c in enumerate(cells) if c.cell_type == "code" and re.search(r"matplotlib|" + "|".join(RUNTIME_PKGS), c.source)), 0)
            new = new_code_cell(line); new.metadata["_orig"] = "new"; cells.insert(first, new)
            nxt = orig(cells[first + 1]) if first + 1 < len(cells) else "?"
            where = "at the top, before the new `%matplotlib widget` cell" if nxt == "new" else f"before cell {nxt}"
            changes.append(f"{where}: added `{line}`")

    # 4. markdown: remote images, captions
    for c in cells:
        if c.cell_type != "markdown": continue
        if not args.no_images:
            def sub(m):
                url = m.group(3) or m.group(6) or m.group(9)
                name, err = fetch_image(url, os.path.join(out_dir, "images"))
                if err: changes.append(f"cell {orig(c)}: image NOT fetched, reference left as is: {url} ({err})"); return m.group(0)
                changes.append(f"cell {orig(c)}: image {url} -> images/{name}")
                if m.group(3): return m.group(1) + '"' + f"images/{name}" + '"'
                if m.group(6): return m.group(4) + '"' + f"images/{name}" + '"'
                return m.group(8) + f"images/{name}" + m.group(10)
            c.source = IMG.sub(sub, c.source)
        c.source, k = CAPTION.subn(r"\1<br>\n", c.source)
        if k: changes.append(f"cell {orig(c)}: <br> inserted between image and caption")

    # 5. data files loaded by bare name but living in a subfolder
    for c in cells:
        if c.cell_type != "code": continue
        for m in DATA_REF.finditer(c.source):
            name = m.group(1)
            if re.search(r"savefig|to_csv|to_excel|np\.save|pickle\.dump|SaveMy", c.source[max(0, m.start()-60):m.start()]): continue
            if os.path.exists(os.path.join(os.path.dirname(f), name)) or os.path.exists(os.path.join(out_dir, name)): continue
            hit = next((x for x in all_files if os.path.basename(x) == name), None)
            if hit: shutil.copy(hit, out_dir); moved_beside.add(hit); changes.append(f"cell {orig(c)}: data file `{name}` copied from `{os.path.relpath(hit, SRC)}` to sit beside the notebook")
            else: changes.append(f"cell {orig(c)}: data file `{name}` NOT FOUND under the source folder")

    # 6. housekeeping
    for c in cells:
        c.metadata.pop("_orig", None)
        if c.cell_type == "code": c.outputs = []; c.execution_count = None
    nb.metadata.pop("colab", None)
    nb.metadata["kernelspec"] = {"name": "python", "display_name": "Python (Pyodide)", "language": "python"}
    nbformat.write(nb, os.path.join(OUT, rel))
    log += [f"- {ch}" for ch in changes] or ["- no changes needed"]

# ---- files other than notebooks (after the notebooks, so moved data files aren't duplicated) ----
log.append("\n## Other files")
for f in all_files:
    rel = os.path.relpath(f, SRC)
    if f.endswith(".ipynb") or f in moved_beside: continue
    if INSTRUCTOR.search(os.path.basename(f)): log.append(f"- NOT COPIED (looks like instructor material): `{rel}`"); continue
    if os.path.basename(f).startswith("."): log.append(f"- NOT COPIED (hidden file; the site would not list it): `{rel}`"); continue
    dst = os.path.join(OUT, rel); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(f, dst); log.append(f"- copied `{rel}`")
for d in sorted({os.path.dirname(os.path.relpath(x, SRC)) for x in moved_beside}):
    if d and not os.listdir(os.path.join(OUT, d)) if os.path.isdir(os.path.join(OUT, d)) else False: os.rmdir(os.path.join(OUT, d))

open(LOG, "w").write("\n".join(log) + "\n")
print("\n".join(log)); print(f"\nlog written to {LOG}")
