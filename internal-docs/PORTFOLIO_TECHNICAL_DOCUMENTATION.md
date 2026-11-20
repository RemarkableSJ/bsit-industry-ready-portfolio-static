# Joshua E. Decena — BSIT Portfolio Technical Documentation

**Website:** `https://remarkablesj.github.io/bsit-industry-ready-portfolio-static/`  
**Repository:** `https://github.com/RemarkableSJ/bsit-industry-ready-portfolio-static`  
**Edition:** Static GitHub Pages portfolio  
**Prepared:** 20 November 2026

> This is technical documentation for maintaining the portfolio source. It is kept in the repository but is not linked as a public documentation page from the portfolio website.

## 1. Purpose and scope

The portfolio presents the owner's professional profile, education, technical skills, projects, problem-solving examples, evidence, employability preparation, resume, contact links, career plan, reflection, and project-defense material.

This edition is a static website. It is designed for GitHub Pages and does not require PHP, MySQL, a server-side runtime, or a paid hosting plan.

## 2. Technology stack

- **HTML5** — page structure and static page shells.
- **CSS3** — responsive layout, visual design, and theme styling.
- **JavaScript** — page rendering, navigation, content presentation, theme switching, and browser-local interactions.
- **JSON** — editable portfolio content in `data/portfolio.json`.
- **Bootstrap 5.3.3 CDN** — selected layout and component utilities.
- **GitHub Pages + GitHub Actions** — static hosting and deployment.
- **Python build script** — validates and transforms the portfolio JSON into the JavaScript data file used by the site.

Some visual libraries, fonts, and styling utilities are loaded from CDNs. Those resources require an internet connection. The site itself is static, but a visitor's browser still needs to download those external assets.

## 3. Repository layout

```text
repository-root/
├── index.html                         # Main portfolio page
├── project.html                       # Dynamic project case-study page
├── defense.html                       # Project-defense presentation
├── editing.html                       # Browser-based local content editor
├── data/
│   └── portfolio.json                 # Human-editable source content
├── assets/
│   ├── css/                           # Main, upgrade, and theme styles
│   ├── js/
│   │   ├── default-data.js            # Generated browser data; do not edit by hand
│   │   ├── app.js                     # Main rendering and interaction logic
│   │   └── theme.js                   # Light/dark theme behavior
│   ├── images/                        # Profile and project identity images
│   └── files/                         # Public downloadable files such as the resume
├── project-archives/                  # Bundled project source/demo packages
├── evidence-staging/                  # Public supporting evidence files
├── tools/
│   └── build_portfolio_data.py        # Generates default-data.js from portfolio.json
└── .github/workflows/
    └── static.yml                     # GitHub Pages deployment workflow
```

The repository also contains separate project documentation and supporting files. Keep private credentials, private databases, personal exports, and confidential records out of this public repository.

## 4. Main website behavior

The main page renders the following portfolio sections from the JavaScript data object:

1. Homepage and professional headline.
2. Professional profile and contact details.
3. Technical skills and evidence notes.
4. Three project cards and case-study navigation.
5. Evidence and supporting files.
6. Troubleshooting examples.
7. Security case study.
8. AI-literacy material.
9. Employability and interview preparation.
10. Career plan.
11. Resume links and PDF download.
12. Certificates and achievements.
13. GitHub links.
14. Contact links.
15. Reflection and submission-readiness checklist.

`project.html?id=0`, `project.html?id=1`, and `project.html?id=2` display the three project case studies. Project-specific documentation links are added only for Joshua's Studio House Museum and Buo.

### Browser-local settings

- The light/dark theme preference is saved in the current browser's `localStorage`.
- The personal submission checklist is saved in the current browser's `localStorage`.
- These values do not sync to GitHub, other browsers, other devices, or other visitors.
- Contact links open the visitor's email application or social profile. The static site does not store contact messages in an inbox.
- The content editor operates in the visitor's browser. It is not a shared online CMS. Publishing shared content changes requires updating the source data and pushing a Git commit.

## 5. Updating portfolio content

1. Open `data/portfolio.json` in Visual Studio Code.
2. Edit the required profile, skill, project, resume, or other content values.
3. Preserve valid JSON syntax: double quotes around property names and string values, commas between properties, and no trailing commas.
4. Open PowerShell at the repository root (the folder containing `index.html`).
5. Run:

   ```powershell
   python tools\build_portfolio_data.py
   ```

6. Confirm the script reports that `assets/js/default-data.js` was updated.
7. Preview locally from the repository root:

   ```powershell
   python -m http.server 8000
   ```

8. Open `http://localhost:8000/` and inspect the result.
9. In GitHub Desktop, review the changed files, commit them, and push to `main`.
10. Wait for the GitHub Pages Actions deployment to succeed, then refresh the public website.

Do not edit `assets/js/default-data.js` directly for content changes. It is generated from `data/portfolio.json` and will be overwritten the next time the build script runs.

## 6. Adding or replacing a static asset

1. Place the file in the appropriate repository folder, for example `assets/images/` or `assets/files/`.
2. Use a short, predictable filename without special characters where practical.
3. Update the matching URL or relative path in `data/portfolio.json` or the relevant HTML/JavaScript page.
4. Rebuild `default-data.js` when a JSON field changes.
5. Check that the direct asset URL opens from the published site.
6. Commit and push the file and its reference together.

### Resume and profile photo

The profile photo is referenced by `profile.photoUrl`. The resume is referenced by the top-level `resume` object, including `resumeUrl` and `fileName`. The uploaded file path and the URL in the data must match exactly, including filename extension and spaces. Before publishing a resume, remove personal details that should not be publicly exposed, such as a full home address or date of birth.

## 7. Project deployment boundaries

- **Joshua's Studio House Museum:** the bundled presentation demo is static HTML/CSS/JavaScript and can run within the repository's GitHub Pages path. Its cart and request interactions are demonstrations only.
- **TechZone Mobile Store:** its Streamlit application is a separate Python app. GitHub Pages can host its source archive and supporting evidence, but cannot run Streamlit. A Streamlit-capable service is needed for a live dashboard.
- **Buo:** a Python/Kivy desktop application. GitHub Pages can host documentation and source downloads but cannot run the desktop app in a browser. Buo must be installed and launched on a compatible desktop, or separately packaged for a target platform.

## 8. GitHub Pages deployment

The repository uses `.github/workflows/static.yml` to deploy static files to GitHub Pages.

The workflow:

- runs when a commit is pushed to `main` or when manually dispatched;
- checks out the repository;
- configures GitHub Pages;
- uploads the repository root as the Pages artifact;
- deploys the artifact to GitHub Pages.

The workflow requires the repository Pages source to be set to **GitHub Actions** in **Settings → Pages**. Check the Actions tab for the latest deployment run. A green check indicates that the deployment job completed successfully; it does not replace checking the visible website and its links in a browser.

## 9. Security and privacy

This repository and the GitHub Pages website are public. Do not commit:

- API keys, OAuth tokens, passwords, or private configuration files;
- `cloud_config.json` or any other file containing a real Gemini/Firebase secret;
- Buo's private `buo.db` database or user fitness exports;
- personal journals, private backups, identity documents, or confidential records;
- resume details that should not be published publicly.

Use example configuration files with placeholders. Rotate any credential that was previously exposed; removing it from a later commit does not invalidate the exposed credential.

## 10. Known limitations and maintenance checklist

- The static portfolio has no shared database-backed admin dashboard.
- Visitor contact messages are not stored by the website.
- Evidence files are committed as public static files; there is no private upload manager.
- Browser-local editor/checklist/theme state is not shared or synchronized.
- External CDN resources may not load when a visitor is offline or when the CDN is unavailable.
- A successful Pages workflow only verifies deployment, not every project interaction.

Before a portfolio presentation, verify the live homepage, mobile navigation, theme switch, profile photo, resume PDF, case-study pages, Museum demo, downloadable project archives, documentation pages, and defense presentation. Re-test any application feature on the actual target device before describing it as fully working.
