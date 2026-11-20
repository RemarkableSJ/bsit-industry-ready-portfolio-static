# BSIT Professional Portfolio Website — Technical Documentation

**Owner:** Joshua E. Decena  
**Platform:** Static HTML/CSS/JavaScript website  
**Hosting target:** GitHub Pages  
**Purpose:** Technical and operational documentation for the portfolio website itself.

## 1. Overview

The BSIT Professional Portfolio presents the owner's profile, technical skills, project case studies, evidence, troubleshooting examples, cybersecurity learning, responsible AI-use reflection, employability preparation, career plan, resume, contact links, and project-defense presentation.

The published edition is static. It is built from HTML, CSS, JavaScript, and JSON-derived browser data. It does not require PHP, MySQL, or a server-side application to render the portfolio.

## 2. Objectives and scope

- Present professional background and career direction.
- Show technical skills with supporting evidence.
- Organize three featured projects and their demos, source packages, reports, and limitations.
- Document problem-solving, cybersecurity awareness, and responsible AI use.
- Support interview preparation, career planning, resume access, and project-defense rehearsal.
- Provide a maintainable GitHub Pages website.

Included: public portfolio presentation; client-side navigation and theme selection; structured content rendering; static evidence links; project case-study pages; public documentation pages; a content-update guide; and a project-defense presentation view.

Not included in this static edition: server-side authentication, a private admin portal, shared database-backed content management, server-stored contact messages, an upload manager, or backend transaction processing.

## 3. Page and section inventory

| Page / section | Purpose |
|---|---|
| Homepage / Hero | Introduces the owner, role, specialization, and professional statement. |
| Profile | Presents the About Me text and professional profile information. |
| Technical Skills | Groups skills by category, level, and evidence. |
| Projects | Summarizes featured projects and links to case studies and supporting materials. |
| Evidence Library | Links to supporting reports and workbooks. |
| Problem-solving | Presents expandable troubleshooting cases. |
| Cybersecurity Case | Explains a defensive security topic and safe practices. |
| Responsible AI Use | Lists AI-assisted tasks and personal verification/reflection. |
| Employability | Provides interview preparation and a defense run sheet. |
| Career Plan | Records target role, skill gaps, learning goals, and timed goals. |
| Resume | Links to the resume file or configured resume URL. |
| Certificates & Achievements | Presents verifiable awards and credentials when added. |
| GitHub / Contact | Links to repositories, email, and social profiles. Contact links are external actions, not server-side forms. |
| Reflection | Presents the portfolio owner's reflection. |
| Checklist | Shows readiness items. In the updated build, selections are stored locally in the visitor's browser, not shared. |
| `project.html` | Renders a selected project case study using `?id=0`, `?id=1`, or `?id=2`. |
| `editing.html` | Gives content editing, data generation, preview, and publish instructions. |
| `defense.html` | Renders presentation steps with previous/next controls, keyboard arrows, and print support. |
| `documentation/*.html` | Public documentation pages for the portfolio and selected projects. |

## 4. Technology stack

| Technology | Role |
|---|---|
| HTML5 | Page structure and content containers. |
| CSS3 | Layout, responsive styling, visual components, and themes. |
| JavaScript | Rendering, project selection, theme switching, and client-side presentation interactions. |
| JSON | Editable structured portfolio content. |
| Python 3 | Runs the data-generation script. |
| Bootstrap 5.3.3 CDN | CSS framework dependency loaded from jsDelivr on applicable pages. |
| Git / GitHub | Version control and repository hosting. |
| GitHub Pages | Static website publishing. |

The portfolio website runtime does not need PHP or MySQL. SQL examples inside separate project packages are not part of the portfolio runtime.

## 5. Architecture and data flow

`data/portfolio.json` is the editable source of structured content. `tools/build_portfolio_data.py` reads that JSON and generates `assets/js/default-data.js`, assigning the data to `window.defaultPortfolio`.

The homepage loads `default-data.js` and `assets/js/app.js`. The application script reads the data and populates page sections. `project.html` uses the `id` query parameter to select a project record. `defense.html` reads the defense plan and profile/project data to render presentation steps.

```text
data/portfolio.json
        |
        v
python tools/build_portfolio_data.py
        |
        v
assets/js/default-data.js
        |
        +--> index.html + assets/js/app.js
        +--> project.html (?id=0, ?id=1, ?id=2)
        +--> defense.html

Static HTML/CSS/JS/assets --> GitHub repository --> GitHub Pages
```

**Important:** Edit `data/portfolio.json`, then rebuild `assets/js/default-data.js`. Do not hand-edit the generated file because the build script overwrites it.

## 6. Key files and folders

```text
bsit-industry-ready-portfolio-static/
├── index.html
├── project.html
├── editing.html
├── defense.html
├── data/portfolio.json
├── tools/build_portfolio_data.py
├── assets/
│   ├── css/style.css
│   ├── css/upgrade.css
│   ├── css/portfolio-theme.css
│   ├── js/app.js
│   ├── js/theme.js
│   ├── js/default-data.js
│   └── images/
├── project-archives/
├── evidence-staging/
├── documentation/
├── internal-docs/
└── .nojekyll
```

| File | Responsibility |
|---|---|
| `index.html` | Main portfolio homepage and content containers. |
| `project.html` | Project case-study template. |
| `editing.html` | Content maintenance instructions. |
| `defense.html` | Presentation / defense view. |
| `data/portfolio.json` | Editable content source. |
| `tools/build_portfolio_data.py` | JSON-to-JavaScript build script. |
| `assets/js/default-data.js` | Generated browser data. |
| `assets/js/app.js` | Homepage content rendering and interaction logic. |
| `assets/js/theme.js` | Light/dark theme initialization and toggle. |
| `assets/css/style.css` | Base layout and styling. |
| `assets/css/upgrade.css` | Additional visual refinement. |
| `assets/css/portfolio-theme.css` | Theme and component styles. |
| `project-archives/` | Independent project source packages and static demo files. |
| `evidence-staging/` | Project reports and supporting workbook files. |
| `documentation/` | Public HTML documentation pages. |
| `internal-docs/` | Maintainer-facing Markdown notes. |

## 7. Featured project boundaries

1. **Joshua's Studio House Museum:** A static gallery/storefront presentation demo. Its cart, checkout, and commission interactions are simulations; no real orders or payments are processed.
2. **TechZone Mobile Store:** A separate smartphone product analysis project. The portfolio contains its source archive, report, and workbook. Its 15 actual product records support comparison and inventory screening, not sales forecasting. The separate Streamlit application is not executed by GitHub Pages.
3. **Buo:** A Python/Kivy desktop application. GitHub Pages can present its case study and source archive but cannot run the Windows desktop app in a browser. GPS route capture and Android background tracking remain incomplete in the supplied source snapshot.

Do not describe these three applications as components running inside the portfolio website. They are separate projects linked from the portfolio.

## 8. Local preview

Run these commands from the repository root:

```powershell
python tools/build_portfolio_data.py
python -m http.server 8000
```

Open `http://localhost:8000`. Stop the server with `Ctrl + C` in the terminal.

## 9. Update and publish workflow

1. Open the repository in VS Code.
2. Edit `data/portfolio.json` and preserve valid JSON syntax.
3. Run `python tools/build_portfolio_data.py` from the repository root.
4. Preview with `python -m http.server 8000` and test relevant pages and links.
5. Review changed files in GitHub Desktop.
6. Commit changes to the correct branch.
7. Click **Push origin**.
8. Confirm the GitHub Pages deployment succeeds and test the live website.

## 10. Theme, local storage, and visitor interactions

- The theme script supports light/dark appearance and stores the visitor's preference in that browser's `localStorage`.
- The mobile navigation button controls the compact navigation state.
- Project and troubleshooting details use expandable sections.
- The defense view supports previous/next controls and left/right keyboard arrows; the browser print feature can print or save it as PDF.
- In the updated build, checklist state is browser-local. It is not synchronized between visitors or devices.
- Contact links open the visitor's email client or social destination; no message is stored by a portfolio backend.

Browser storage can be cleared by the visitor, removing locally saved preferences and checklist state.

## 11. Hosting and deployment

The intended GitHub Pages configuration serves static files from the configured repository branch and directory. The current setup uses the `main` branch and repository root. `index.html` must be in the publishing root and all referenced paths must resolve. GitHub Pages does not execute PHP or provide a MySQL database for this website.

## 12. Security and privacy

- Treat all content committed to a public repository as publicly accessible.
- Do not commit credentials, API keys, passwords, private tokens, personal IDs, private databases, or confidential work records.
- Review public resume and contact information before publishing.
- Keep credentials for separate projects out of the public portfolio source.
- Test downloadable files and remove anything that should not be public.

## 13. Limitations and future work

Current limitations: no server-side login, database, admin content management, stored contact form, visitor inbox, or server upload manager; publication requires repository changes and a Git push; theme/checklist preferences are browser-local; some CSS resources load from a public CDN; and GitHub Pages does not execute the separate Kivy or Streamlit projects.

Recommended work: test desktop/mobile layouts; check all project, documentation, resume, report, and workbook links; improve keyboard and screen-reader testing; consider local copies of CDN dependencies for offline demonstrations; and add a secure backend only if shared accounts, stored messages, uploads, or centralized management become real requirements.

## 14. Verification checklist

- [ ] Homepage and sections load without missing assets or scripts.
- [ ] Main navigation and mobile menu work.
- [ ] Light/dark themes remain readable.
- [ ] Profile, skills, and project content are current.
- [ ] All three project case-study pages open with the correct IDs.
- [ ] Museum demo and source links resolve.
- [ ] TechZone report, workbook, and source archive links resolve.
- [ ] Buo source and documentation links resolve.
- [ ] Resume and contact links are correct and safe to publish.
- [ ] Defense Mode controls and print view work.
- [ ] Public documentation pages open from the website.
- [ ] Mobile layouts are checked at common phone widths.

A source review is not a substitute for testing the latest deployed site in a real browser.
