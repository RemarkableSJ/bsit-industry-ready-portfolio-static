# Joshua E. Decena — BSIT Professional Portfolio (GitHub Pages Edition)

A free, static HTML/CSS/JavaScript portfolio for GitHub Pages. It preserves the portfolio profile, skills, project case studies, troubleshooting examples, cybersecurity case study, AI-use reflection, interview preparation, career plan, resume area, and project-defense presentation.

## Live features

- Responsive portfolio with light/dark theme switch
- Three detailed project case studies
- Static project evidence links and downloadable source archives
- Project defense slides with keyboard navigation and print support
- Contact links using email and social profiles (no server-stored messages)
- Content is loaded from `assets/js/default-data.js`

## Project deployment destinations

1. **Joshua's Studio House Museum** — the static demo is in `project-archives/joshua-studio-house-museum/`. It includes a browser-local cart and simulated checkout/commission flows; no real orders or payments are processed.
2. **TechZone Mobile Store** — the Streamlit source package is in `project-archives/TechZone_Project2_Complete_Source_Package.zip`. Deploy it separately to Streamlit Community Cloud. The 15-record dataset supports product comparison and inventory screening, not sales forecasting.
3. **Buo** — Windows desktop source is in `project-archives/buo-desktop/` and `project-archives/Buo_Desktop_Source.zip`. GitHub Pages can display source/documentation, but cannot run the Kivy desktop application in a browser. GPS route capture and Android background tracking remain incomplete in this source snapshot.

## Publish with GitHub Pages (free for public repositories on GitHub Free)

1. Create or open the GitHub repository for this static site.
2. Put the contents of this folder at the repository root. `index.html` must be at the root.
3. Commit and push the files to the `main` branch.
4. In GitHub, open **Settings → Pages**.
5. Under **Build and deployment**, choose **Deploy from a branch**.
6. Select branch **main** and folder **/(root)**, then click **Save**.
7. Wait for the Pages deployment to finish. Open the site URL shown in the Pages settings.

GitHub Pages only serves static files. This edition intentionally has no server-side application, database-backed admin dashboard, stored contact form, or server upload feature. The TechZone project archive still contains its own supplementary SQL demonstration; that is separate from the portfolio website.

## Update the portfolio content

1. Edit `data/portfolio.json` using VS Code or another text editor.
2. From the repository root, run:

   ```bash
   python tools/build_portfolio_data.py
   ```

3. Preview locally:

   ```bash
   python -m http.server 8000
   ```

4. Open `http://localhost:8000`.
5. In GitHub Desktop, commit the updated JSON and generated JavaScript, then click **Push origin**. GitHub Pages redeploys after the push.

See `editing.html` for a visual guide.

## Local preview on Windows

Double-click `run_local_preview.bat` (Python must be installed), then open `http://localhost:8000`. This is a static preview; no MySQL or PHP installation is required.

## Important static-site limitations

- Content edits are made in the repository and published with a Git commit; visitors cannot edit shared content.
- Contact buttons open email/social apps; there is no inbox or stored contact form.
- Evidence files are committed as static assets; there is no upload manager or private file storage.
- Do not publish confidential records, personal IDs, credentials, API keys, private databases, or files that should not be public. GitHub Pages sites are publicly accessible.

## Technology

HTML5, CSS3, JavaScript, JSON, Bootstrap CDN, GitHub Pages. No server-side runtime or database is required.
