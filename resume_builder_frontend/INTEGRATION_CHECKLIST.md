# Integration Checklist

Quick reference for integrating this resume builder into your Flask project.

## Your Project Structure

```
your-project/
├── package.json          # Root (existing)
├── vite.config.ts        # Root (existing)
├── index.html            # Root (create this)
├── frontend/
│   └── src/              # Source code goes here
│       ├── app/          # ← Copy resume builder here
│       ├── styles/       # ← Copy styles here
│       ├── imports/      # ← Copy images here
│       └── main.tsx      # ← Copy entry point here
├── app.py                # Your Flask app
└── static/
    └── resume-builder/   # ← Built files go here
```

## File Copying Guide

Copy these files from this codebase to your project:

### Source Code
```
FROM this codebase          TO your project
─────────────────────────   ──────────────────────────
src/app/                 →  frontend/src/app/
src/styles/              →  frontend/src/styles/
src/imports/             →  frontend/src/imports/
src/main.tsx             →  frontend/src/main.tsx
```

### Configuration Files

1. **index.html** (in project root, same level as package.json) - Create this file with:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Resume Builder</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/frontend/src/main.tsx"></script>
  </body>
</html>
```

2. **vite.config.ts** (in project root) - Add/merge these settings:
```typescript
export default defineConfig({
  // ... your existing config
  
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    emptyOutDir: true,
  },
  
  base: '/create-resume/',
})
```

3. **package.json** (in project root) - Add these dependencies (merge with existing):
```json
{
  "dependencies": {
    "@radix-ui/react-accordion": "1.2.3",
    "@radix-ui/react-label": "2.1.2",
    "@radix-ui/react-slot": "1.1.2",
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "lucide-react": "0.487.0",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@tailwindcss/vite": "4.1.12",
    "@vitejs/plugin-react": "4.7.0",
    "tailwindcss": "4.1.12",
    "vite": "6.3.5"
  }
}
```

## Build & Deploy Steps

1. **Install dependencies** (first time only):
```bash
# From project root
npm install
```

2. **Build the project**:
```bash
# From project root
npm run build
```

This creates a `dist/` folder in your project root.

3. **Copy to Flask static folder**:
```bash
# From project root
cp -r dist/* static/resume-builder/
```

4. **Verify files copied**:
```
static/resume-builder/
├── index.html
├── assets/
│   ├── index-[hash].js
│   ├── index-[hash].css
│   └── ...
└── imports/
    ├── modern.jpg
    ├── classic.jpg
    └── ...
```

## Flask Routes

Add to your Flask app:

```python
from flask import send_from_directory, abort
import os

@app.route('/create-resume')
def create_resume():
    return send_from_directory('static/resume-builder', 'index.html')

@app.route('/create-resume/<path:path>')
def serve_resume_assets(path):
    if '..' in path or path.startswith('/'):
        abort(404)
    return send_from_directory('static/resume-builder', path)
```

## Testing

1. Start your Flask app
2. Visit `http://localhost:5000/create-resume`
3. You should see the template carousel
4. Check browser console for any errors
5. Verify images load correctly

## Common Issues

**Images not loading?**
- Ensure `static/resume-builder/imports/` folder exists with all .jpg files

**Blank page?**
- Check browser console for errors
- Verify `index.html` has `<div id="root"></div>`
- Confirm JS files are loading (Network tab)

**404 on assets?**
- Verify `base: '/create-resume/'` in vite.config.ts
- Check Flask routes are serving from correct directory
- Ensure build completed without errors
