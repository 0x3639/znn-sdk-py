# PyZNN documentation website

This directory contains the Docusaurus site for the Python Zenon SDK.
It requires Node.js 20 or newer.

## Local development

```bash
npm install
npm run start
```

The development server watches the Markdown and React sources for changes.

Search is local and credential-free. Its index is produced by the production
build, so use `npm run build` followed by `npm run serve` to test search.

## Production build

```bash
npm run build
```

The generated static site is written to `build/`. The production build must
pass before documentation changes are merged because it checks MDX parsing and
internal links.

## Deployment

The site is published at `https://pyznn.0x3639.com/` by
`.github/workflows/pages.yml`. Every push to `master` performs a clean install,
builds Docusaurus, uploads `build/` as a Pages artifact, and deploys it. The
workflow can also be run manually from the Actions tab.

Until the new custom domain is active, the workflow overrides Docusaurus to
serve the inherited project URL at `https://www.0x3639.com/znn-sdk-py/`. Remove
`DOCUSAURUS_URL` and `DOCUSAURUS_BASE_URL` from the workflow when completing the
custom-domain cutover.

### Custom domain activation

Repository configuration alone does not create the DNS record. Before the
custom URL can resolve:

1. in **Settings → Pages**, select **GitHub Actions** as the build and deployment
   source;
2. create a DNS `CNAME` record for `pyznn` pointing to `0x3639.github.io`;
3. confirm `pyznn.0x3639.com` as the custom domain in the repository's Pages
   settings;
4. push or manually run the Pages workflow; and
5. enable **Enforce HTTPS** after GitHub provisions the certificate.

The tracked `static/CNAME` file preserves the custom domain on each deployment.
