# Astro Starlight — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for the Astro Starlight documentation framework.
To combine with capabilities/languages/typescript.md for general TS best practices.
-->

> **Reference version:** Astro 5.x / Starlight ^0.38 | **Last updated:** 2026-04
> **Official docs:** [starlight.astro.build](https://starlight.astro.build) | [Astro docs](https://docs.astro.build)

---

## 🏛️ Fundamental principles

### 1. Project structure

Starlight is an Astro integration — the project follows Astro conventions:

```
<project>/
├── astro.config.mjs          ← Starlight config (title, sidebar, i18n, components)
├── src/
│   ├── content/
│   │   └── docs/             ← All documentation pages (Markdown/MDX)
│   │       ├── fr/           ← French content
│   │       └── en/           ← English content
│   ├── components/           ← Starlight component overrides
│   ├── plugins/              ← Rehype/Remark plugins
│   ├── assets/               ← Static assets (images, etc.)
│   └── content.config.ts     ← Content collections config
├── public/                   ← Unprocessed static files
├── package.json
└── tsconfig.json
```

### 2. Content as Markdown

All documentation pages are Markdown (`.md`) or MDX (`.mdx`) files in `src/content/docs/`.

```markdown
---
title: My Page
description: A brief description for SEO and sidebar.
sidebar:
  order: 1
  label: Optional sidebar label
---

## Section title

Content here...
```

**Frontmatter rules:**
- `title` is **mandatory** — Starlight will fail without it
- `description` is strongly recommended (SEO, sidebar, search)
- `sidebar.order` controls sort order within a section
- Use `sidebar.label` to override the displayed title in the sidebar

### 3. Internationalisation (i18n)

Starlight provides native i18n with a routing-based approach — no third-party plugin needed:

```js
// astro.config.mjs
starlight({
  defaultLocale: 'fr',
  locales: {
    fr: { label: 'Français', lang: 'fr' },
    en: { label: 'English', lang: 'en' },
  },
})
```

**Rules:**
- Content files mirror paths between locales: `fr/guide/setup.md` ↔ `en/guide/setup.md`
- The default locale's path prefix can be omitted (`root` locale) or explicit
- UI strings are translated via Starlight's built-in translation system

---

## 🔧 Component overrides

Starlight allows replacing built-in components by pointing to custom ones in `astro.config.mjs`:

```js
starlight({
  components: {
    Head: './src/components/Head.astro',
    // Other overridable components:
    // Header, Footer, Sidebar, PageTitle, Hero, etc.
  },
})
```

### Head.astro override pattern

The most common override — used to inject scripts, meta tags, or client-side features:

```astro
---
import type { Props } from '@astrojs/starlight/props';
import Default from '@astrojs/starlight/components/Head.astro';
---

<Default {...Astro.props}><slot /></Default>

<!-- Custom additions below -->
<script>
  // Client-side code here
</script>

<style is:global>
  /* Global styles here */
</style>
```

**Rules:**
- Always import and render the `Default` component — never replace it entirely
- Pass `{...Astro.props}` and `<slot />` to preserve Starlight features
- Use `is:global` for styles that need to escape Astro's scoped CSS
- Astro `<script>` tags are bundled and deduplicated automatically

---

## 🎨 Theming & CSS

### CSS custom properties

Starlight exposes CSS variables for theming. Use them for consistent styling:

```css
var(--sl-color-bg)            /* Page background */
var(--sl-color-text)          /* Default text color */
var(--sl-color-text-accent)   /* Accent/link color */
var(--sl-color-gray-5)        /* Border color */
var(--sl-color-gray-6)        /* Subtle background */
```

### Dark mode

Starlight handles dark mode via `data-theme` on `<html>`:

```js
const isDark = document.documentElement.dataset.theme === 'dark';
```

**Rules:**
- Never hard-code colors — always use Starlight CSS variables
- Test both light and dark themes for every custom component
- Use `data-theme` attribute, not `prefers-color-scheme`, for JS detection

---

## 🔌 Rehype & Remark plugins

Starlight uses Astro's Markdown pipeline. Custom transformations use rehype/remark plugins:

```js
// astro.config.mjs
export default defineConfig({
  markdown: {
    rehypePlugins: [myRehypePlugin],
    remarkPlugins: [myRemarkPlugin],
  },
});
```

### Plugin file pattern

```js
// src/plugins/rehype-my-transform.mjs
import { visit } from 'unist-util-visit';

export default function rehypeMyTransform() {
  return (tree) => {
    visit(tree, 'element', (node) => {
      // Transform AST nodes
    });
  };
}
```

**Rules:**
- Use `.mjs` extension for ESM plugins
- Always handle the transform defensively (`node?.properties?.className`, etc.)
- Prefer rehype (HTML AST) for DOM transformations, remark (Markdown AST) for content transforms

---

## ⚡ Vite configuration

Starlight runs on Vite. Custom Vite config goes through `astro.config.mjs`:

```js
export default defineConfig({
  vite: {
    optimizeDeps: {
      include: ['mermaid'], // Pre-bundle heavy ESM packages
    },
  },
});
```

**Key rule:** Heavy ESM-only packages (like `mermaid`) **must** be added to `vite.optimizeDeps.include` or they will fail in dev mode with module resolution errors.

---

## 🧩 Client-side integrations (Mermaid example)

### Architecture pattern

For client-side libraries that render on the page (diagrams, charts, interactive elements):

```
┌──────────────────────────────────────────────────────┐
│  rehype plugin: transform code blocks → <pre class>  │
│  (runs at build time, tags content for client JS)    │
├──────────────────────────────────────────────────────┤
│  Head.astro <script>: client-side rendering          │
│  (picks up tagged elements, renders with library)    │
├──────────────────────────────────────────────────────┤
│  Head.astro <style is:global>: component styling     │
│  (toolbar, wrapper, buttons — uses Starlight vars)   │
└──────────────────────────────────────────────────────┘
```

### Lessons learned — Starlight CSS isolation

> ⚠️ **Critical:** Starlight CSS leaks into `<foreignObject>` HTML inside SVGs.

When a library like Mermaid renders SVGs with `<foreignObject>` (HTML embedded in SVG), the **document's CSS cascade applies to that HTML** — including Starlight's global styles. This corrupts text measurement, positioning, and layout.

**What does NOT work:**
| Approach | Why it fails |
|---|---|
| CSS `display: flex !important` on foreignObject children | Destroys Mermaid's `table-cell + vertical-align: middle` layout |
| `<style>` inside SVG | SVG `<style>` elements do NOT apply to HTML inside `<foreignObject>` |
| Shadow DOM for **display only** | SVG coordinates are already baked in with wrong positions from render time |
| Shadow DOM as **render container** | Mermaid uses `document.getElementById()` internally — Shadow DOM breaks that |

**What works:**
```js
// Temporarily disable all external stylesheets during render
function disableExternalStyles() {
  const disabled = [];
  for (let i = 0; i < document.styleSheets.length; i++) {
    const sheet = document.styleSheets[i];
    const owner = sheet.ownerNode;
    // Keep the library's own styles active
    if (owner?.id?.startsWith('mermaid')) continue;
    if (!sheet.disabled) {
      disabled.push(sheet);
      sheet.disabled = true;
    }
  }
  return () => disabled.forEach(s => s.disabled = false);
}

const restore = disableExternalStyles();
try {
  const { svg } = await mermaid.render(id, code);
} finally {
  restore();
}
```

**Post-render display isolation** — use Shadow DOM for the rendered output:
```js
const host = document.createElement('div');
const shadow = host.attachShadow({ mode: 'open' });
shadow.innerHTML = `<style>
  :host { display: block; overflow: auto; }
  svg { display: block; max-width: none; height: auto; }
</style>${svg}`;
```

### SVG/PNG export

When exporting SVGs with `<foreignObject>` as standalone files or PNG:

1. **Inline computed styles** before removing `foreignObject` (element indices must match between original and clone)
2. **Set explicit dimensions** on the SVG clone — Mermaid v11+ injects `style="width:100%;max-width:Xpx"` which breaks standalone rendering
3. **Replace `foreignObject` with `<text>` + `<tspan>`** for cross-platform compatibility:
   - Use `text-anchor="middle"` + `dominant-baseline="central"` for centering
   - Word-wrap into lines: estimate chars per line from `foreignObject` width
   - Position at the center of the `foreignObject` bounding box

```js
// Word-wrap text into tspan lines
const fontSize = 14;
const charWidth = fontSize * 0.58;
const maxChars = Math.floor((foWidth - 16) / charWidth);
// Split words into lines respecting maxChars...
// Create <tspan x={centerX} y={startY + i * lineHeight}> for each line
```

4. **Add background rect** as first child of the SVG for opaque export
5. **PNG via data URI**: serialize SVG → data URI → Image → Canvas → toBlob

### Page navigation

Starlight uses View Transitions. Re-init client-side features on navigation:

```js
renderFeature();
document.addEventListener('astro:page-load', () => renderFeature());
```

---

## 🚫 Anti-patterns

```
❌ Missing frontmatter `title`         → Starlight build fails silently or with obscure errors
❌ Hard-coded colors in components      → Breaks dark mode, inconsistent with theme
❌ Forgetting `is:global` on styles     → Styles don't apply to dynamically created elements
❌ Using prefers-color-scheme for JS    → Doesn't match Starlight's theme toggle state
❌ Heavy ESM packages without optimizeDeps → Vite dev server crashes with resolution errors
❌ Full <Head> replacement              → Breaks Starlight SEO, fonts, and theme features
❌ CSS affecting foreignObject in SVGs  → Corrupts library layout calculations (see above)
❌ Shadow DOM as render container       → Libraries using getElementById cannot find their elements
❌ Not re-initialising on astro:page-load → Features disappear on View Transition navigation
```

---

## ✅ Checklist

- [ ] Every `.md` file has a `title` in frontmatter
- [ ] Custom components extend `Default`, not replace
- [ ] Styles use Starlight CSS variables, not hard-coded values
- [ ] Both light and dark themes tested
- [ ] Heavy ESM packages in `vite.optimizeDeps.include`
- [ ] Client-side features re-init on `astro:page-load`
- [ ] SVG libraries render with external styles disabled
- [ ] SVG display uses Shadow DOM isolation
- [ ] Exports handle foreignObject → text conversion with word-wrap
- [ ] i18n: content paths mirror between locales

---

## 🔗 Related capabilities

- `languages/typescript.md` — TypeScript conventions used in Astro components
- `security/owasp.md` — XSS considerations for `securityLevel: 'loose'` in diagram libraries
