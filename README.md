# Asteria

![Main window](data/screenshots/Captura%20de%20tela%20de%202026-11-09%2015-38-03.png)

**Asteria** is a graphical interface for managing and build websites with **Asteria SSG**, a static site generator that transforms OpenDocument Text (`.odt`) files into fast, themeable static websites.

Asteria is designed to make website management accessible without using the command line and provides an interface for creating and managing sites, editing configurations, choosing themes, organizing navigation, and previewing your website all in one place.

## Features

- **Site management.** Create and delete Asteria sites directly from the graphical interface.
- **Site configuration.** Easily change the main site settings, including name, language, home page, and website URL.
- **Menu management.** Add, edit, and remove navigation menu items.
- **Social links.** Manage your social media links with simple add, edit, and remove operations.
- **Theme customization.** Select the active theme and choose its available variant.
- **Content shortcuts.** Quickly open the folders containing posts, pages, and cover images to add, modify, or delete files using your preferred editor.
- **Configuration editors.** Access and edit the main configuration files directly:
  - `site.yaml` — Site settings and general configuration.
  - `theme.yaml` — Theme configuration.
  - `i18n.yaml` — Internationalization and translation settings.
- **Integrated site preview.** Preview your website directly within the application without having to open a separate browser or manually run the development server.

## Managing content

Asteria provides shortcuts to the main content directories:

| Content | Purpose |
|---|---|
| Posts | Add, modify, or delete blog posts (`.odt`). |
| Pages | Add, modify, or delete standalone pages (`.odt`). |
| Covers | Add, modify, or delete cover images. |

Content files are managed using your preferred external editor. Asteria remains responsible for converting these files into the final static website.

## Configuration

The application provides direct access to the main YAML configuration files, allowing you to customize advanced settings when needed.

- **`site.yaml`** — General website settings and configuration.
- **`theme.yaml`** — Theme-specific settings and customization.
- **`i18n.yaml`** — Language and internationalization settings.

Basic site settings, navigation menus, and social links can also be managed through dedicated graphical controls.

## Themes

Choose from the available Asteria themes and select the desired theme variant through the interface.

## Live preview

Asteria includes an integrated website preview, allowing you to inspect the generated site while managing your project.

## Related project

Asteria is a graphical companion to [**Asteria SSG**](https://github.com/kriptolix/Asteria-Project).

For information about content authoring, supported configuration options, themes, and the static site generation process, see the Asteria SSG documentation.

## License

AGPL-3.0.

## Contributing

Issues and pull requests are welcome.