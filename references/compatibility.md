# Compatibility: what runs in the browser

Everything under "Verified" was tested by an instructor in a desktop browser on a locally built site. Everything else is labeled as such. Re-verify after any version change; the numbers below are a snapshot with a date, not a promise.

## Versions

**Known-good pinned build stack (tested 2026-09-30):**

    jupyterlite-core[all]==0.8.3
    jupyterlite-pyodide-kernel==0.8.5   # bundles Pyodide 314.0.5: Python 3.14.2
    ipympl==0.10.0
    ipywidgets==8.1.9
    jupyterlab_widgets==3.0.17

Pyodide 314.0.5 ships numpy 2.4.6, pandas 3.0.2, matplotlib 3.10.8, scipy 1.18.0, sympy 1.14.0, astropy 7.2.0, scikit-learn 1.8.0, networkx 3.6.1.

**How to look up current versions and the package list.** After installing the kernel package in the build environment:

    python -c "from jupyterlite_pyodide_kernel.constants import PYODIDE_VERSION; print(PYODIDE_VERSION)"
    curl -sS https://cdn.jsdelivr.net/pyodide/v<VERSION>/full/pyodide-lock.json -o pyodide-lock.json

The lock file's `packages` object lists every built-in package with its version. `tools/audit_notebooks.py` fetches it for the pinned version and classifies imports against it, then asks PyPI whether an unknown package has a pure-Python (`py3-none-any`) wheel.

Pin the widget packages to a set known to work together. The front-end halves (ipympl's and ipywidgets' Jupyter extensions) come from the *build* environment; the Python halves come from wheels bundled in the site's `pypi/` folder and installed at runtime. Both sides must match.

## Verified plotting and interactivity results (2026-09-30)

| Need | Approach | Result | Notes |
|---|---|---|---|
| Pan and zoom on 2D plots | `%pip install -q ipympl` (own cell), `%matplotlib widget` (own cell), then imports | works | toolbar appears under each figure |
| Rotatable 3D surface | same, `projection='3d'`, `plot_surface` | works | drag rotates; scroll zooms only with `fig.canvas.capture_scroll = True` |
| Sliders updating a plot in place | widget backend; create figure once; callback sets data or clears and redraws, then `fig.canvas.draw_idle()` | works | callback that creates a new figure per call piles up figures |
| Sliders with static figures | `%pip install -q ipywidgets`; no matplotlib magic; callback makes a fresh figure | works | Pyodide's default backend is static; `%matplotlib inline` unnecessary but harmless in its own cell |
| Plotly 3D surface | Plotly installed in the build env; wheels for plotly, narwhals, packaging, nbformat, fastjsonschema, jupyter_core bundled; `%pip install -q plotly nbformat`; `fig.show()` | works | without nbformat every `show()` renderer fails with "Mime type rendering requires nbformat"; give 3D figures explicit `width`/`height`, otherwise the scene renders tiny |
| Plotly without the extension | `HTML(fig.to_html(include_plotlyjs='cdn', full_html=False))` | works | needs internet for plotly.js |
| Molecular viewer | `%pip install -q py3Dmol`, `py3Dmol.view(...)` | works | viewer script loads from the web; scroll zoom is sensitive |
| Two real thermodynamics notebooks (3D surfaces) converted from `%matplotlib notebook` | widget backend + install cell | work | |
| Magic line in the same cell as imports | any | FAILS | `No module named 'matplotlib'`; kernel can't parse the cell to find imports |
| Interface | classic Notebook | works | every browser tab is titled with the site name only |
| Interface | JupyterLab | works | notebook names appear on in-page tabs |

Instructor's verdict after testing both: matplotlib with the widget backend over Plotly for 3D surfaces, as a matter of preference.

**Unverified:** nglview, ipyvolume, k3d, pythreejs, bokeh, altair in the browser (each needs its front-end extension in the build environment and its wheel bundled); `IPython.display.Audio` playback; whether Pyodide's matplotlib has a serif font (`rcParams['font.family'] = 'serif'` may fall back with a warning); `pyodide_http.patch_all()` for live downloads; how much slower a long pure-Python loop runs (expect a few times slower than a laptop, with the page unresponsive meanwhile). Treat these as experiments to run in Phase 3, not promises, and say so to the instructor.

## Common chemistry and physics packages (Pyodide 314.0.5)

| Built in | Pure Python, install at runtime | Not available (compiled) |
|---|---|---|
| numpy, scipy, sympy, pandas, matplotlib | ipywidgets, ipympl, plotly, py3Dmol, pint, uncertainties, lmfit (check), tqdm (built in) | rdkit, numba, pyscf, psi4, qutip, mdtraj, openmm, ase |
| astropy, scikit-learn, networkx, statsmodels, h5py, pillow, sqlite3 | | pytables (so no pandas HDF5) |

"check" means the package is pure Python but its dependencies must be confirmed against the lock file. When in doubt, run the audit script: it resolves the actual imports.

## Checking data files against the site's versions

Pickled DataFrames depend on the pandas that wrote them. The build environment deliberately has no pandas, so test-load fixtures in a throwaway environment pinned to the site's versions:

    python -m venv /tmp/site-pandas && /tmp/site-pandas/bin/pip install numpy==2.4.6 pandas==3.0.2
    /tmp/site-pandas/bin/python -c "import pickle; print(type(pickle.load(open('file.pkl','rb'))))"

HDF5 files: arrays written with h5py or h5io load in the browser; tables written by pandas need PyTables, which Pyodide lacks. Tell them apart without h5py: `strings file.hdf5 | grep -E 'pandas_type|TITLE|CLASS'` finds pandas/PyTables markers.

## Runtime behaviour worth telling instructors

- The first `%pip install` and the first `import` of a large package take a few seconds while the browser downloads them; afterwards they are cached.
- Restarting the kernel discards installed packages; the install cell must run again after every restart. "Restart, then Run All from the top" is the habit to teach.
- Files a notebook writes land in the browser's storage next to the notebook and appear in the file browser (refresh it if not).
- Everything a student does is stored by the browser for that site address. Same computer, same browser, same profile. Private windows keep nothing. Clearing site data wipes it. Some browsers evict storage after weeks of non-use. Hence: download the notebook at the end of every session.
