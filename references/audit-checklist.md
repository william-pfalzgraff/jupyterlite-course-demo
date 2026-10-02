# Audit checklist: what breaks in a browser Python, and what to do about it

`tools/audit_notebooks.py` (in the companion repository) finds the patterns below and prints them with notebook and cell numbers. This file is the judgment layer: why each pattern matters, how severe it is, and the fix to propose. Report format is at the end.

## Packages

**Three kinds of package.** (1) Built into the Pyodide distribution: importable with no extra step. (2) Pure-Python packages from PyPI: installable at runtime with `%pip install`, and the site can bundle their wheels so the install works offline and pinned. (3) Packages with compiled code that Pyodide doesn't ship: unavailable, full stop. The script classifies every top-level import; `references/compatibility.md` says how to check a specific Pyodide version and lists common chemistry and physics packages by kind.

- **Kind 3 import** -> blocker. Propose an alternative (SciPy or NumPy routines, a pure-Python package, precomputed data shipped with the notebook) and let the instructor decide; this is a pedagogical change.
- **Kind 2 import with no `%pip install` cell** -> adaptation. Add `%pip install -q <package>` in its own cell before the import, and bundle the wheel. This applies even to packages the site bundles: bundling makes the wheel available, `%pip install` makes it importable. Verified: `ipywidgets` imported without an install cell fails with `ModuleNotFoundError` even when its wheel is in the site.
- **`!pip install ...`** -> adaptation. Shell commands don't exist in the browser; change to `%pip install`.
- **Kind 1 import in a cell that also contains a magic line** -> adaptation, and a subtle one. The kernel decides which built-in packages to load by parsing a cell's import statements; a cell containing a `%` or `!` line isn't valid Python, so its imports load nothing and the first import fails with `No module named 'matplotlib'`. Verified both ways. Rule: magics get their own cell. Notebooks where an install cell happens to pull the package in first will work by accident; fix them anyway.

## Functions that no longer exist

The browser Python ships current NumPy and Matplotlib, and notebooks written a few years ago call things those versions removed: `np.trapz` (gone in NumPy 2.4; `np.trapezoid` takes the same arguments), `np.in1d`, `np.row_stack`, `np.product`, `np.alltrue`, `np.float_`, `np.NaN`, `np.Inf`, the `np.int`/`np.float` aliases, `fig.gca(projection='3d')`, `plt.hold`. Each is a blocker: the cell raises `AttributeError`. The script checks a list; read `references/compatibility.md` for the shipped versions and check anything else that looks dated against the NumPy 2 migration guide. These break on any current laptop installation too, which is a persuasive point for the instructor.

## Plotting and interactivity

**Interactive backends keep figures open across cells.** Under `%matplotlib inline`, every cell got a fresh figure and closed it; under `%matplotlib widget` (as under the old `%matplotlib notebook`), the last figure stays active, so a cell that calls `plt.plot(...)` without first calling `plt.figure()` or `plt.subplots()` draws into the previous figure. Notebooks written for `%matplotlib notebook` already call `plt.figure()`; notebooks written for `inline` usually don't. When a course moves to the interactive backend, every plotting cell without its own figure call (the script lists them with `--interactive`) needs `plt.figure()` added, or that notebook stays static. The adapt script's `--ensure-figure` does the insertion and logs it.

- **`%matplotlib notebook`** -> adaptation. That backend no longer exists in current Jupyter, in the browser or on a laptop. Replace with `%matplotlib widget` (interactive, needs `%pip install -q ipympl` in an earlier cell) or remove the line (static figures, the browser default). Propose based on what the notebooks do (toolbar instructions, 3D surfaces, sliders), and confirm with the instructor.
- **`%matplotlib widget` with no `%pip install -q ipympl` cell before it** -> adaptation; the magic fails with "widget is not a recognised backend".
- **`%matplotlib inline`** -> note or adaptation. Static figures are the default in the browser, so the line is unnecessary; it is harmless *if it sits in its own cell* (see the magic rule above). Move it or drop it.
- **3D axes (`projection='3d'`, `plot_surface`, ...)** -> works with the widget backend: drag rotates. Scroll zoom is off by default; `fig.canvas.capture_scroll = True` turns it on. Mention as an option, don't add unasked.
- **Sliders (`interact`, `ipywidgets`)** -> two cases. With static figures, a callback that calls `plt.figure()` each time simply replaces the figure: fine. With the widget backend, the same callback adds a new live figure on every slider move. Fix: create the figure once outside the callback and redraw it in place (`fig.clear(); ax = fig.subplots(); ...; fig.canvas.draw_idle()`), or make that one notebook static. The script flags a `plt.figure`/`plt.subplots` call inside a function in any notebook that also calls `interact`.
- **Plotly** -> works with extra setup (see compatibility notes: nbformat must be installed in the kernel, Plotly in the build environment, explicit figure size for 3D). **py3Dmol** works; its viewer loads from the web. Other widget-based 3D libraries are unverified; say so.

## Files and paths

- **Data files loaded by name** (`np.loadtxt`, `pd.read_csv`, `open`, `pickle.load`, `np.load`, or any helper function given a filename) -> the file must be in the site, in the folder the notebook expects. The script checks every string literal that looks like a data filename and reports those not where the notebook would find them. Files loaded through a helper that builds the name (`LoadScenario(name + '.pkl')`) are invisible to it; the script also lists files in each folder that no notebook names, so you can ask what loads them.
- **Hidden files** (names starting with a dot) -> adaptation. The build copies them but the file listing omits them, so the kernel can't open them. Rename, drop, or set `allow_hidden` in the build configuration (see the site recipe).
- **Paths that escape the folder** (`../../`, absolute paths, `~`) -> adaptation. Students see only the site's content folder; keep shared data in a folder at the content root and use `../data/...` style relative paths.
- **Files written by notebooks** (`savefig`, `to_csv`, `pickle.dump`) -> works; the file appears in the student's browser storage, next to the notebook. Note it in the student handout: right-click, Download, to keep a copy.
- **HDF5** -> partial. Arrays and scalars via h5py work; tables stored by pandas need PyTables, which Pyodide lacks. Prefer pickle, CSV, or `.npy` for data files.
- **Pickled DataFrames** -> tied to the pandas version. Files pickled with a newer pandas than the site's may not load. Check the site's pandas version (compatibility notes) and test-load fixtures with it.
- **`os.chdir`, `drive.mount`, `files.upload`** (Colab habits) -> adaptation; remove.

## Network

- **Downloads in code** (`requests`, `urllib`, `pd.read_csv(url)`, `wget`) -> blockers as written. Two separate obstacles: Python's socket layer doesn't exist in the browser, so `urllib` and `requests` fail before any request is sent; and even through the browser's own fetch, a server must allow cross-origin requests, which most data servers don't. Pyodide ships `pyodide-http`, whose `patch_all()` reroutes `urllib`/`requests` through the browser fetch, so a download from a server that sends `Access-Control-Allow-Origin: *` can work; this skill has not verified it in a browser, so treat it as an experiment for Phase 3, not a recommendation. The reliable fix: download the data once, ship it in the site, read the local copy, and note the source and date in the notebook.
- **Remote images in markdown** -> adaptation. Images from other sites can vanish (a colleague's faculty page, a retired wiki), and any `http://` address is blocked outright on an `https://` site. The adapt script downloads each into an `images/` folder beside the notebook and rewrites the reference; it reports every failure so the instructor can replace a dead image.
- **`http://` links in text** -> note. Clickable links work; only embedded resources are blocked.

## Things that don't exist in the browser

- `subprocess`, `multiprocessing`, `threading` (blockers), `tkinter` and other GUI toolkits (blockers), `input()` (works in current versions but confirm), `time.sleep` (works, but blocks the whole page), shell commands starting with `!` (blockers).
- Heavy numerical work is slower than on a laptop; long loops should be flagged, not changed.

## Wording that describes another environment

Instructions in markdown that say "on the JupyterHub server", "in Colab", "click the upload arrow in the upper left", "Validate, then Submit", or "log out" describe where the notebook used to run. The script greps for these. Propose rewording to the site: files appear in this site's file browser; the Upload button is at the top of the file browser; downloads are the student's durable copy; hand-in is whatever the interview established. This is a cross-cutting finding, stated once.

## Presentation

- **Inline image and caption in one paragraph** (`<img ...> <strong>Figure 1</strong>...`) -> renders side by side in the wide layouts of today's Jupyter, caption beside the picture. The narrow classic notebook always wrapped it below. Fix: `<br>` after the image, or the caption in its own paragraph. The adapt script does this.
- **Cells that don't parse** -> usually intentional: `dt = ?`, a deliberate error for students to fix. The script reports them separately from other findings; confirm with the instructor and leave them alone.
- **Colab metadata, nbgrader locks** -> harmless in the browser; the adapt script strips Colab metadata and clears outputs. nbgrader-locked cells stay locked in the student's site, which is usually what the instructor wants.

## Keep out of the site

- **Solution and instructor files** (`### BEGIN SOLUTION`, filenames with "instructor", "solution", "key") -> stop and tell the instructor. Publishing a site is publishing these.
- **Autograder markers** (nbgrader metadata, Otter `# BEGIN QUESTION` raw cells, `grader.check`) -> note and offer separate help. The site serves whatever student version the grading tool produces. nbgrader's locked cells stay uneditable in the browser only because nbgrader also sets `editable: false` and `deletable: false` on them; the script counts those flags. The notebooks' own "Validate and Submit" instructions must be reworded (above).

## Report format

Lead with one line per notebook (name, blockers, adaptations, notes counts). Then per notebook, in severity order:

    **notebook.ipynb, cell 12** (blocker)
    `import rdkit`
    RDKit is compiled and not part of Pyodide; nothing in the browser can provide it.
    Proposed: ...

Course-wide findings (same thing in many notebooks, or a workflow spanning notebooks) go in their own section before the per-notebook sections, with a letter code the per-notebook sections refer to. Then a closing list of decisions the instructor needs to make, each phrased as a question with the options.
