# Hand-off documents

Fill these in with the instructor's actual choices and write them into the site folder: the instructor guide as `README.md`, the student handout both as `STUDENT_HANDOUT.md` for the instructor and as a notebook in `content/` whose name sorts first (`0. Read me first.ipynb`). A Markdown file in `content/` opens as plain text in the classic interface; a notebook of markdown cells renders.

For a site that is local-only so far, write the README with the local address and commands, and add a "Publishing later" paragraph pointing at the publishing steps in `references/site-recipe.md`.

## Instructor guide template

    # {COURSE} notebook site

    Students run the notebooks at {SITE_URL} in their browser. Nothing is installed and
    nothing runs on a server; the site is static files published from this repository.
    (Local-only for now? Then: the site is built from this folder and served on your own
    computer at http://127.0.0.1:8000; see "Publishing later" below.)

    ## Adding a week's notebooks
    1. Prepare the student version of the notebook outside this repository. Never copy
       instructor or solution versions in; everything in `content/` is public.
    2. Header cells for notebooks with interactive plots: `%pip install -q ipympl`,
       `%matplotlib widget`, then imports, each in its own cell.
    3. Put data files and images next to the notebook (or in `content/data/` with
       `../data/...` paths).
    4. Copy the folder into `content/{WEEK_FOLDER_PATTERN}`.
    5. Preview: {PREVIEW_COMMANDS}. Check in a private browser window.
    6. `git add`, commit, push. The site updates in about two minutes.

    ## Fixing a published notebook
    A notebook students have opened will not update in their browser. Publish the fix
    under a new filename and tell students which one to use.

    ## Do not change during the semester
    `requirements.txt` and the wheels in `pypi/`. They are the frozen version set the
    site was tested with.

    ## Grading
    {HOW_STUDENTS_SUBMIT}

    ## If something breaks
    - A package error on the first cell: the install cell didn't run; Restart & Run All.
    - Interactive plot error "widget is not a recognised backend": matplotlib was
      imported before the install cell ran; restart the kernel and run from the top.
    - A student "lost" work: it is in the browser they used, on the computer they used.
      Otherwise, their last downloaded copy is the backup.

## Student handout template

    # Where your work lives, and how not to lose it

    Your notebooks run at {SITE_URL}. Everything you do there is saved by your web
    browser on the computer you are using: same computer, same browser, same profile.
    Close the tab, restart the computer, come back next week: your work is still there.

    It will NOT be there if you
    - switch to a different computer, browser, or browser profile;
    - clear your browsing data or "site data";
    - use a private or incognito window (everything vanishes when it closes);
    - haven't visited the site in a long while, on some browsers.

    So: **at the end of every session, download your notebook** (right-click it in the
    file browser, choose Download). {SUBMISSION_SENTENCE} Your downloaded copy is your
    backup; the Upload button in the file browser puts it back.

    Other things worth knowing
    - You need an internet connection the first time you open the site in a session: the
      browser downloads Python itself (about 30 MB) and then keeps it.
    - The first cell of each notebook installs what the notebook needs. Run it first,
      and again after every kernel restart.
    - If a plot won't appear or a cell says a package is missing: Kernel > Restart,
      then Run All from the top.
    - Deleting a notebook in the file browser resets it to the course's published copy.
      That is also how to start over.
