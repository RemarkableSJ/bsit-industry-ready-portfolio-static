# Joshua's Studio House Museum — Project Documentation

**Project type:** Static web presentation · digital art gallery and storefront demo  
**Technology:** HTML5, CSS3, JavaScript, Tailwind CSS CDN, Lucide icons, Google Fonts, browser `localStorage`, and local image assets  
**Prepared:** 20 November 2026

## 1. Project overview

Joshua's Studio House Museum is a browser-based art gallery and storefront presentation. It brings artwork, studio materials, drawing supplies, and selected product items into a museum-inspired browsing experience. Visitors can move between exhibition areas, inspect items, filter collections, select variants where available, and try a demonstration cart and commission-request flow.

The version included in this portfolio is intentionally a static presentation edition. It demonstrates the visitor interface and front-end interactions; it is not a live e-commerce service.

## 2. Problem and objectives

### Problem addressed

An art studio may need a more organized online presentation than separate social-media posts or manually shared photographs. Visitors benefit from a single place to browse artwork, see product choices, and understand how a commission request would be initiated.

### Objectives

- Present artwork and studio products in organized exhibition areas.
- Provide a consistent visual identity for Graphite, Canvas, and Artisan Artifacts.
- Demonstrate showroom navigation and image browsing.
- Allow visitors to filter product collections.
- Show product descriptions, sample prices, stock indicators, and variants where defined.
- Demonstrate a browser-local cart and simulated checkout journey.
- Demonstrate a commission-request form without sending a real order to a server.

## 3. Main user journey

1. **Grand Hall:** the visitor arrives at the museum-style landing section.
2. **Showrooms:** the visitor browses Graphite Hall, Canvas Wing, and Artisan Artifacts.
3. **Exhibitions / portfolio:** the visitor opens the catalog and filters items by category.
4. **Product selection:** the visitor inspects an item and selects an available variant when applicable. The interface updates the displayed price and stock state from the local demonstration inventory.
5. **Acquisitions cart:** the visitor adds items, sees the cart count, changes quantities or removes items, and reviews the subtotal.
6. **Simulated checkout:** the visitor can explore the shipping or pickup flow. This is a demonstration only and does not submit a real order or payment.
7. **Patronage / commission request:** the visitor can open the commission section and complete the demonstration form. It does not create a server-side request for the studio.

## 4. Features included in the static presentation

- Museum/gallery landing page and navigation.
- Graphite, Canvas, and Artisan Artifacts showroom areas.
- Showroom image carousel controls.
- Catalog and category filters.
- Product cards with images and item details.
- Variant selection for selected supplies and materials.
- Dynamic sample price and stock display for defined variants.
- Add-to-cart and remove-from-cart interactions.
- Cart badge, quantities, and subtotal calculation.
- Shipping/pickup demonstration choice.
- Commission-type selection and request form presentation.
- Responsive layout for common desktop and mobile viewports.
- Seventeen supplied artwork/product image assets in the project package.

## 5. Technology and architecture

### Front end

- `index.html` provides the page shell, navigation, footer, and application root.
- `styles.css` contains the museum visual design and responsive styling.
- `script.js` defines the demonstration inventory, in-memory application state, rendering logic, navigation, filtering, variants, cart behavior, and local presentation storage.
- `assets/images/` contains the artwork and product photography used by the page.

### External visual dependencies

The page loads Tailwind CSS, Lucide icons, and fonts from public CDNs. An internet connection is therefore needed for those external resources to load.

### Browser state

The application keeps the current cart and navigation state in JavaScript while the page is open. The demonstration inventory is read from and written to browser `localStorage` under the key `museum_demo_inventory`. This is browser-local state, not a shared or server-side inventory database.

## 6. Data and transaction behavior

This portfolio copy deliberately removes real backend, payment, and remote-order behavior. The local inventory starts from the demonstration data defined in `script.js`. Variant stock changes can be saved in the current browser's local storage. The current cart and simulated request interactions are not submitted to a business server.

The presentation must not be represented as accepting real purchases, taking payments, reserving stock, arranging fulfilment, or sending commission requests to a staff inbox.

## 7. Run locally

1. Download or extract the portfolio repository.
2. Open `project-archives/joshua-studio-house-museum/`.
3. Either open `index.html` in a modern browser or start a simple local server from that folder:

   ```powershell
   python -m http.server 8000
   ```

4. Visit `http://localhost:8000/`.
5. Test showroom navigation, image carousels, filters, variant selection, cart interactions, simulated checkout, and the commission form.

A local server is recommended for consistent browser handling of local assets and JavaScript modules.

## 8. GitHub Pages location

The Museum demo is included at `project-archives/joshua-studio-house-museum/index.html`.

Public path:

`https://remarkablesj.github.io/bsit-industry-ready-portfolio-static/project-archives/joshua-studio-house-museum/`

Because the repository root is deployed to GitHub Pages, the Museum folder can be opened at that path without a separate hosting subscription.

## 9. Verification status

### Static checks already performed on the supplied package

- JavaScript source syntax was checked.
- The supplied local image references were checked against the package assets.
- The static presentation copy was checked to ensure real payment and external-order integrations were not included.
- The expected `index.html`, stylesheet, JavaScript, and image assets are included.

### Manual acceptance checks still recommended

- Test all navigation and showroom controls on desktop and mobile browsers.
- Test every category filter and each product variant.
- Verify quantity limits and cart subtotals.
- Confirm the simulated checkout clearly states that no real transaction occurs.
- Confirm the commission demo does not imply that a real request has been sent.
- Re-test the deployed GitHub Pages URL after significant changes.

## 10. Limitations

- No server-side application or database is included in this static presentation copy.
- No visitor account or administrator dashboard is provided.
- No real order, payment, webhook, inventory reservation, or fulfilment is performed.
- Commission requests are local demonstrations and are not sent to the studio.
- Cart and local inventory state are not synchronized between visitors or devices.
- Clearing browser storage can reset the demonstration inventory state.
- CDN-hosted styling, icons, and fonts need internet access.

## 11. Future improvements

Possible future work includes accessibility testing, more device-size testing, replacing CDN dependencies with local packages for offline demonstrations, improving product filtering and keyboard navigation, and adding a secure backend only if real orders or shared inventory are intentionally required. Any future payment or order system would need server-side validation, access controls, secure secret storage, and end-to-end testing.

## 12. Source files

- `index.html`
- `styles.css`
- `script.js`
- `assets/images/`
- `README.md`

This document describes the static presentation package in this portfolio, not any separate private or historical production service.
