# Jupyter Site Demo

A small JupyterLite site: students (or you) open a web page and run Jupyter notebooks
with a Python that executes inside the browser. Nothing is installed and no server runs.

**Live site:** https://william-pfalzgraff.github.io/jupyterlite-course-demo/

This repository is the live example for *Build a Jupyter Site for Your Course* on the
Faculty AI Exchange (https://facultyaiexchange.org/examples/build-a-jupyter-site/), which
describes how an AI coding assistant can move an instructor's existing notebooks onto a
site like this one. The site was produced with that contribution's skill and scripts.

## What's here

    content/            the notebooks students see: a start-here page and three
                        showcase activities (thermodynamic surface, carbon cycle,
                        Fourier transform), each adapted from a published source
    pypi/               wheels for the packages notebooks install at runtime
                        (the interactive matplotlib backend and ipywidgets)
    jupyter-lite.json   site name, interface (classic Notebook), default kernel
    requirements.txt    the pinned build stack; frozen so the site stays reproducible
    .github/workflows/deploy.yml   builds and publishes the site on every push
    robots.txt          lets search engines index this demo (a course site would say Disallow)

## The tooling behind the skill

The skill's scripts, templates and reference notes live here so they can be kept current without
changes to the exchange page; the skill itself (`SKILL.md`) is on the exchange. The skill tells an assistant to clone this repository and use:

    tools/audit_notebooks.py     scan a folder of notebooks for what behaves differently in the browser
    tools/adapt_notebooks.py     apply the mechanical fixes to copies of the notebooks, with a change log
    tools/scaffold_site.py       lay out a new site folder from templates/ and download the runtime wheels
    templates/                   deploy workflow, site config, pinned requirements, gitignore, robots,
                                 and a smoke-test notebook
    references/                  the skill's reference notes: audit checklist, browser-verified
                                 compatibility table, site recipe, instructor-guide and student-handout
                                 templates

They need Python with `nbformat` (the JupyterLite build environment has it). This site was made
with them. Everything outside `content/` is MIT licensed.

## Build it yourself

    python -m venv .venv && source .venv/bin/activate      # or a conda environment
    pip install -r requirements.txt
    jupyter lite build --contents content --output-dir _output
    cd _output && python -m http.server 8000               # open http://127.0.0.1:8000

After changing `jupyter-lite.json`, `requirements.txt` or `pypi/`, delete both `_output`
and `.jupyterlite.doit.db` before rebuilding.

## Licenses

Notebooks (`content/`): CC BY 4.0, see `LICENSE-NOTEBOOKS.md`. Everything else: MIT, see `LICENSE`.

## Sources

- Neshyba, S.; Posta, F.; Pfalzgraff, W. C.; Eklof, J.; Neshyba-Rowe, D. P.; Rowe, P. M.
  CAMBIO: A Carbon Mass Balance Model for Undergraduates. *Bull. Am. Meteorol. Soc.* **2026**,
  *107* (1), E26–E43. https://doi.org/10.1175/BAMS-D-25-0069.1
- Guasco, T. L.; Pfalzgraff, W. C.; Stokes, G. Y.; Posta, F.; Neshyba, S. P. Teaching
  Thermodynamics with Geometry and Computational Guided Inquiry. In *Engaging Students in
  Physical Chemistry, Volume 2*; ACS Symposium Series 1515; American Chemical Society, 2025;
  pp 131–155. https://doi.org/10.1021/bk-2025-1515.ch010
- Dominic, A. J.; Cipolla, N. L.; Pfalzgraff, W. C.; Jankowski, J. A.; Rapf, R. J.;
  Montoya-Castillo, A. A Pedagogical Tour of the Fourier Transform with Applications to NMR
  and IR Spectroscopy. *J. Chem. Educ.* **2025**, *102* (5), 1972–1980.
  https://doi.org/10.1021/acs.jchemed.4c01439
