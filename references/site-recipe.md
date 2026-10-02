# Site recipe: files, building, serving, publishing

## The site folder

    my-course-site/
      content/                 what students see in their file browser (notebooks, data, images)
      pypi/                    wheels for packages installed at runtime with %pip
      jupyter-lite.json        site name, interface, default kernel
      requirements.txt         the pinned build stack (frozen for the semester)
      .github/workflows/deploy.yml   builds and publishes on every push (only if publishing)
      .gitignore               keeps build output, tests, and instructor files out of git
      robots.txt               keeps the site out of search engines (optional)
      README.md                the instructor guide (Phase 6)
      tests/                   local-only notebooks (smoke test); gitignored, never published

`tools/scaffold_site.py` in the companion repository (https://github.com/william-pfalzgraff/jupyterlite-course-demo) creates this from its `templates/` folder.

## The build environment

Use a dedicated environment so the pinned stack can't drift with other work:

    conda create -n course-site python=3.12 pip     # or: python -m venv course-site
    pip install -r requirements.txt

`requirements.txt` holds `jupyterlite-core[all]`, `jupyterlite-pyodide-kernel`, and, if the course needs them, `ipympl`, `ipywidgets`, `jupyterlab_widgets` and `plotly`. The interactive packages must be in the build environment because the build copies their browser extensions into the site; the same packages also need wheels in `pypi/` for the Python side. The reverse also holds: every Jupyter extension present in the build environment is copied into the site, so keep that environment to exactly the course's needs. Start from the tested pins (`references/compatibility.md`), then freeze them.

## Runtime wheels

Anything students `%pip install` should be in `pypi/` so it installs offline and at a pinned version:

    pip download --no-deps -d pypi ipympl==0.10.0 ipywidgets==8.1.9 jupyterlab_widgets==3.0.17 widgetsnbextension comm traitlets typing_extensions

The scaffold script knows the dependency sets for the widget backend, Plotly, py3Dmol and pint and downloads them. Only pure-Python wheels (`py3-none-any.whl`) work; a compiled wheel in `pypi/` is silently useless. The build prints one line per wheel it picks up.

## Build, serve, rebuild

    jupyter lite build --contents content --contents tests --output-dir _output
    (cd _output && python -m http.server 8000 &)    # background it; then open http://127.0.0.1:8000
    curl -sI http://127.0.0.1:8000/ | head -1       # confirm it answers

The local build is identical to what GitHub Pages serves, except that `tests/` (the smoke test) is included locally and never published (the deploy workflow builds `--contents content` only).

**Hidden files.** Files whose names start with a dot are copied by the build but omitted from the file listing, so notebooks can't open them. Rename them, leave them out, or add to `jupyter_lite_config.json`: `{"ContentsManager": {"allow_hidden": true}}`.

**Internet on first load.** The site itself is static, but the browser downloads Python (Pyodide, about 30 MB) from a CDN the first time a kernel starts in a session, then caches it. Tell students. A fully self-contained build is possible with `jupyter lite build --pyodide <pyodide tarball>` at the cost of a much larger site.

**Rebuilding.** After changing notebooks, rebuilding is incremental and fine. After changing `jupyter-lite.json`, `requirements.txt` or the wheels, do a clean rebuild:

    rm -rf _output .jupyterlite.doit.db
    jupyter lite build --contents content --output-dir _output

Deleting `_output` alone leaves the build cache thinking the configuration step is done; the site then comes up with default settings (JupyterLab interface, default name) and no error. This cost an afternoon once.

**Seeing the rebuilt site.** The browser keeps its own copy of every notebook opened from the site, layered over the published one. Open a private window, or delete the notebook in the site's file browser to get the fresh copy.

## jupyter-lite.json

    {
      "jupyter-lite-schema-version": 0,
      "jupyter-config-data": {
        "appName": "Physical Chemistry",
        "appUrl": "./tree",
        "defaultKernelName": "python"
      }
    }

`appUrl` is `./tree` for the classic Notebook interface (one notebook per browser tab, a file list as the landing page) or `./lab` for JupyterLab. In the classic interface every browser tab is titled with `appName`, so keep it short.

## Notebook header convention

For every notebook that uses the interactive backend, the first three code cells are:

    %pip install -q ipympl            (plus any other runtime packages the notebook needs)
    %matplotlib widget
    import numpy as np                (imports only; no magics in this cell)
    import matplotlib.pyplot as plt

Notebooks with static figures need only the install cell for packages outside Pyodide, then the imports. Delete `%matplotlib inline` or give it its own cell.

## Publishing to GitHub Pages

Only after the local demo passed, and only with the instructor's go-ahead at each step.

1. Instructor: `gh auth login`. You: `gh auth status`.
2. In the site folder: `git init`, confirm `.gitignore` is present, `git add .`, and show `git status` so the instructor can see that no instructor file is staged. Then commit.
3. `gh repo create <name> --public --source . --push` (Pages is free on public repositories only).
   If the push fails with "correct access rights", the CLI chose an SSH remote and the machine has
   no SSH key on the account. Switch to HTTPS and push again:
   `git remote set-url origin https://github.com/<owner>/<name>.git && gh auth setup-git && git push -u origin main`
4. Enable Pages from Actions: `gh api -X POST repos/<owner>/<name>/pages -f build_type=workflow`, then `gh run watch` for the first build. If the API call fails, the instructor can set Settings > Pages > Source to "GitHub Actions" in the browser.
5. The site address is `https://<owner>.github.io/<name>/`. The instructor verifies in a private window.

The deploy workflow (`templates/deploy.yml`) installs `requirements.txt`, builds with `--contents content`, copies `robots.txt`, and publishes. Every push to the main branch republishes within a couple of minutes.

## Clear outputs before committing

Anything saved in a notebook's outputs is what students see before they run a cell: old
printouts, the `%pip` "you may need to restart the kernel" note, and widget views that can't
render without their kernel. Opening a notebook in a local Jupyter to review it is enough to
save outputs into the file. Strip them before every commit, for example:

    python -c "import nbformat,glob
    for p in glob.glob('content/**/*.ipynb', recursive=True):
        nb = nbformat.read(p, as_version=4)
        for c in nb.cells:
            if c.cell_type == 'code': c.outputs = []; c.execution_count = None
        nb.metadata.pop('widgets', None); nbformat.write(nb, p)"

(or install `nbstripout` as a git filter). The adapt script already clears outputs, but edits
made afterwards can put them back.

## Rules for the semester

- Pushing is publishing. Don't push half-finished notebooks.
- A notebook a student has already opened will not update in their browser. Publish a fix under a new filename (`Week03_v2.ipynb`).
- Don't change `requirements.txt` or the wheels mid-semester; a version bump can change what runs.
- Instructor and solution files never enter the repository. The `.gitignore` blocks common names as a backstop, but the rule is to keep them in a different folder entirely.
- Keep pickled data files tied to the site's pandas version; regenerate them only with that version.
