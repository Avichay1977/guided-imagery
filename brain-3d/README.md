# מוח תלת-ממדי · 3D Brain Learning Tool

כלי לימוד אינטראקטיבי של המוח האנושי בעברית — הדמיה תלת-ממדית חיה של קליפת
המוח, האונות והסינפסות. גררו כדי לסובב, צבטו לזום, ובחרו אונה כדי ללמוד
עליה.

An interactive Hebrew (RTL) learning tool that renders the human brain in
real-time 3D: a folded cortex (gyri/sulci), glowing synaptic points, and
clickable regions with plain-language explanations.

## מה יש כאן / What's inside

- **קורטקס מקומט** — icosphere displaced by seeded 3D simplex noise to form
  gyri and sulci, with a deep interhemispheric fissure along the midline.
- **פלטת ציאן→סגול→כתום** — a GLSL shader colours the cortex by elevation
  (cyan valleys → purple → orange ridges) with a fresnel rim glow.
- **נקודות סינפטיות זוהרות** — ~900 additively-blended points that pulse
  across the surface.
- **6 אזורים אינטראקטיביים** — frontal, parietal, temporal, occipital,
  cerebellum and brainstem, each with a Hebrew description and key functions.
  Tap a marker on the brain or a chip at the bottom to focus and learn.

## הרצה / Run

No build step, no dependencies to install — it's a single self-contained
page that loads Three.js from a CDN via an import map.

```bash
# any static server works, e.g.
python3 -m http.server -d brain-3d 8080
# then open http://localhost:8080
```

Or open `brain-3d/index.html` directly through a local web server (ES
modules require `http://`, not `file://`).

## שדרוג לתמונה האמיתית / Upgrading to the real image

This is the **code version** — it stands on its own without any external
asset. When a real photographic brain image is available, swap it in at the
`UPGRADE HOOK` comment at the bottom of `index.html`: load the image as a
texture on the existing `brainMat` shader (add a sampler + UV projection),
or replace the shader with a `MeshStandardMaterial({ map, displacementMap })`.
The geometry, synapses, region markers and UI all stay unchanged.

## טכנולוגיה / Tech

Vanilla JS + [Three.js](https://threejs.org/) r160 (ES modules over CDN),
custom GLSL shaders. No framework, no bundler.
