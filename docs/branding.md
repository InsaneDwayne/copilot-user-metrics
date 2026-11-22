# Branding

The image ships a default theme, served at `/theme/`. To brand the dashboard with your name,
logo, fonts and colours, give the API your own theme folder. Nothing is rebuilt and nothing
restarts when you edit it: changes show on the next browser reload.

## 1. Start from the defaults

Copy the theme out of the running image. It includes
`theme.schema.json`, which gives your editor autocomplete and validation for `theme.json` and
always matches your version:

```bash
docker compose cp api:/app/static/theme ./theme
```

## 2. Mount it

Put the mount in a `compose.override.yaml` next to the compose file. Docker Compose reads that
file automatically, and release bundles never contain it, so it survives upgrades. If you
already have one (e.g. for [Traefik](deployment/docker-compose.md#traefik-in-the-same-stack)), add
the `api` part to it:

```yaml
services:
  api:
    volumes:
      - ./theme:/app/static/theme:ro
```

Then run `docker compose up -d`. Alternatively, uncomment the same mount under `api` in the
compose file itself, but then you have to carry the change over to each new release bundle.
From a checkout, `deploy/theme/` is git-ignored.

## 3. Edit `theme.json` and reload the page

Your folder replaces the default one entirely, so
keep `theme.json` in it. Keys you leave out keep their defaults. A missing or invalid
`theme.json` falls back to the default theme and logs the reason in the browser console; look
there first if a change doesn't show. Everything in the folder is public: it is served to the
sign-in page too.

```text
theme/
├── theme.json          # name, logo, fonts, colours: the only file you need
├── theme.schema.json   # editor autocomplete (from step 1)
├── theme.css           # optional: anything theme.json can't express
├── logo.svg            # paths in theme.json are relative to this folder
└── fonts/…             # e.g. self-hosted fonts
```

| Key in `theme.json` | What it does |
| --- | --- |
| `appName`, `showAppName` | Name in the header and the browser tab; turn `showAppName` off when the logo already contains the name. |
| `logoUrl`, `logoUrlDark` | Header logo, and an optional one for dark mode. Shown at the header height. |
| `faviconUrl` | Browser-tab icon. |
| `font`, `fontStylesheetUrl` | Font family for all text, and the stylesheet that loads it (a web-font URL or a CSS file in the folder). Without a stylesheet the font is used only where it is installed. |
| `colors.accent` | The brand colour. It is darkened or lightened per mode just enough to stay readable. |
| `colors.light` / `colors.dark` | Per mode: `bg` and `text` (every other colour is derived from these), optional `surface` (cards), `accent` (used exactly as given) and `tokens`. |
| `colors.tokens` | Restyles single roles (chart series, muted text, lines, banners, …) as a `#rrggbb` colour or a palette step such as `accent-300`. The roles are listed in the default `theme.css`. |
| `defaultMode` | `system`, `light` or `dark`: what people see until they use the header toggle. |
| `stylesheetUrl` | A CSS file loaded last, e.g. `theme.css`, which can override any token or style. |

## Examples

Name and brand colour only; everything else stays as it is:

```json
{
  "$schema": "./theme.schema.json",
  "appName": "Acme Copilot Usage",
  "colors": { "accent": "#0b6bcb" }
}
```

A logo that already contains the company name (with a light variant for dark mode), a favicon,
and dark mode by default:

```json
{
  "$schema": "./theme.schema.json",
  "appName": "Acme Copilot Usage",
  "showAppName": false,
  "logoUrl": "logo.svg",
  "logoUrlDark": "logo-white.svg",
  "faviconUrl": "favicon.svg",
  "defaultMode": "dark",
  "colors": { "accent": "#0b6bcb" }
}
```

Corporate colours per mode, an exact accent in light mode, and the first two chart series in
brand colours:

```json
{
  "$schema": "./theme.schema.json",
  "colors": {
    "accent": "#c8102e",
    "light": { "bg": "#ffffff", "text": "#1a1a1a", "accent": "#a50d26" },
    "dark": { "bg": "#121417", "text": "#ececec" },
    "tokens": { "series-1": "#c8102e", "series-2": "#00857c", "fg-muted": "neutral-300" }
  }
}
```

A self-hosted font, so browsers make no request outside your network (the default theme
loads Inter from Google Fonts). `theme.json`:

```json
{
  "$schema": "./theme.schema.json",
  "font": "Corporate Sans",
  "fontStylesheetUrl": "fonts/fonts.css"
}
```

`fonts/fonts.css` (its `url()`s are relative to itself):

```css
@font-face {
  font-family: 'Corporate Sans';
  src: url('corporate-sans.woff2') format('woff2');
  font-weight: 400 700;
}
```

Anything `theme.json` can't express goes in `theme.css` (set `"stylesheetUrl": "theme.css"`).
Every colour is a CSS variable `--color-<role>`; a plain `:root` rule applies to both modes,
`:root[data-theme='light']` or `:root[data-theme='dark']` to one:

```css
:root {
  --radius-md: 4px;
  --radius-lg: 6px;
}
:root[data-theme='dark'] {
  --color-notice: rgb(200 16 46 / 0.15);
}
```
