// @ts-check
// Note: type annotations allow type checking and IDEs autocompletion

const {themes} = require("prism-react-renderer");
const lightCodeTheme = themes.github;
const darkCodeTheme = themes.vsDark;
const siteUrl = process.env.DOCUSAURUS_URL || "https://pyznn.0x3639.com";
const baseUrl = process.env.DOCUSAURUS_BASE_URL || "/";
const llmsUrl = new URL(`${baseUrl}llms.txt`, siteUrl).toString();

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "PyZNN",
  tagline: "Stable, typed Python SDK for the Zenon Network of Momentum.",
  url: siteUrl,
  baseUrl,
  onBrokenLinks: "throw",
  favicon: "img/favicon.ico",
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: "warn",
    },
  },

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: "0x3639",
  projectName: "znn-sdk-py",

  // Even if you don't use internalization, you can use this field to set useful
  // metadata like html lang. For example, if your site is Chinese, you may want
  // to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: require.resolve("./sidebars.js"),
          editUrl:
            "https://github.com/0x3639/znn-sdk-py/edit/master/documentation/website/",
        },
        theme: {
          customCss: require.resolve("./src/css/custom.css"),
        },
      }),
    ],
  ],

  themes: [
    [
      require.resolve("@easyops-cn/docusaurus-search-local"),
      {
        hashed: true,
        language: ["en"],
        indexDocs: true,
        indexBlog: false,
        indexPages: true,
      },
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      colorMode: {
        defaultMode: "dark",
        respectPrefersColorScheme: false,
      },
      navbar: {
        title: "PyZNN",
        logo: {
          alt: "PyZNN Logo",
          src: "img/logo.svg",
        },
        items: [
          {
            type: "doc",
            docId: "installation",
            position: "left",
            label: "Documentation",
          },
          {
            href: "https://github.com/0x3639/znn-sdk-py",
            label: "GitHub",
            position: "right",
          },
        ],
      },
      footer: {
        style: "dark",
        links: [
          {
            title: "Docs",
            items: [
              {
                label: "Install",
                to: "/docs/installation",
              },
              {
                label: "JSON-RPC clients",
                to: "/docs/json-rpc-client",
              },
              {
                label: "Cookbook",
                to: "/docs/cookbook",
              },
              {
                label: "API reference",
                to: "/docs/api-reference",
              },
              {
                label: "LLM index",
                href: llmsUrl,
              },
            ],
          },
          {
            title: "Community",
            items: [
              {
                label: "Forum",
                href: "https://forum.zenon.org/",
              },
              {
                label: "Website",
                href: "https://zenon.network/",
              },
              {
                label: "Zenon on X",
                href: "https://x.com/Zenon_Network",
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} PyZNN contributors. Built with Docusaurus.`,
      },
      prism: {
        theme: lightCodeTheme,
        darkTheme: darkCodeTheme,
      },
    }),
};

module.exports = config;
