# Screenshots for GitHub

Drop your PNG or JPG files **in this folder** (`docs/screenshots/`).

## Filenames the main README expects

Rename (or export) your captures to match these so the images show on the repo homepage:

| File | What to show |
|------|----------------|
| `main-ui.png` | Main window: scan list + header + detail panel |
| `detail-panel.png` | Close-up of the right-hand “what will this affect?” panel |
| `localhost-tab.png` | Localhost servers tab with a few rows |
| `settings.png` | Settings screen (dry-run, recycle bin, extra roots) |

You can use `.jpg` instead of `.png` — then edit the paths in the root `README.md` (change `.png` → `.jpg`).

After adding files:

```bash
git add docs/screenshots/
git commit -m "docs: add screenshots"
git push
```
