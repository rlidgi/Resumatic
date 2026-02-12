
// ----- Data (replace thumbs/links with your real assets) -----
const TEMPLATES = [
  {
    id: "classic-elegant",
    name: "Classic Elegant",
    style: "Classic",
    thumbnail: "classic-elegant-thumb.jpg",
    tags: ["ATS-friendly", "Serif"],
    description: "Traditional serif typography with meticulous spacing and section dividers.",
    formats: ["PDF", "DOCX"],
    demoUrl: "/app/builder?template=classic-elegant",
    downloadUrls: {
      "PDF": "classic-elegant.pdf",
      "DOCX": "classic-elegant.docx"
    }
  },
  {
    id: "classic-simplicity",
    name: "Classic Simplicity",
    style: "Classic",
    thumbnail: "classic-simplicity-thumb.jpg",
    tags: ["Single-column", "Monochrome"],
    description: "No-nonsense one-column layout optimized for ATS parsing.",
    formats: ["PDF", "DOCX"],
    demoUrl: "/app/builder?template=classic-simplicity",
    downloadUrls: {
      "PDF": "classic-simplicity.pdf",
      "DOCX": "classic-simplicity.docx"
    }
  },
  {
    id: "classic-structure",
    name: "Classic Structure",
    style: "Classic",
    thumbnail: "classic-structure-thumb.jpg",
    tags: ["Grid", "2-column"],
    description: "Clean grid-based layout balancing summary, skills, and experience.",
    formats: ["PDF", "DOCX"],
    demoUrl: "/app/builder?template=classic-structure",
    downloadUrls: {
      "PDF": "classic-structure.pdf",
      "DOCX": "classic-structure.docx"
    }
  },

];

// ----- Utilities -----
function resolveBuilder(t) {
  // Prefer explicit demoUrl if provided; else construct from BUILDER_BASE + ?template=<id>
  if (t.demoUrl) return t.demoUrl;
  const base = (window.BUILDER_BASE || "/builder");
  const sep = base.includes("?") ? "&" : "?";
  return base + sep + "template=" + encodeURIComponent(t.id);
}

function resolveThumb(t) {
  if (!t.thumbnail) return "";
  if (/^https?:\/\//.test(t.thumbnail)) return t.thumbnail;
  const base = (window.STATIC_BASE || "/static/");
  return base + "images/templates/" + t.thumbnail;
}

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

function uniq(arr) { return Array.from(new Set(arr)); }

// ----- Render -----
const grid = $("#cardsGrid");
const styleFilter = $("#styleFilter");
const tagFilter = $("#tagFilter");
const sortSelect = $("#sortSelect");
const searchInput = $("#searchInput");

const allTags = uniq(TEMPLATES.flatMap(t => t.tags)).sort();
allTags.forEach(t => {
  const opt = document.createElement("option");
  opt.value = t; opt.textContent = t;
  tagFilter.appendChild(opt);
});

function card(t) {
  const el = document.createElement("article");
  el.className = "bg-white rounded-2xl shadow hover:shadow-lg border overflow-hidden transition";
  el.innerHTML = `
    <div class="aspect-[3/4] overflow-hidden">
      <img src="${resolveThumb(t)}" alt="${t.name} preview" class="h-full w-full object-cover">
    </div>
    <div class="p-4">
      <div class="flex items-center justify-between gap-3">
        <h3 class="font-semibold truncate">${t.name}</h3>
        <span class="text-xs px-2 py-1 rounded-full border">${t.style}</span>
      </div>
      <p class="text-sm text-gray-600 mt-1 line-clamp-2">${t.description}</p>
      <div class="flex flex-wrap gap-1 mt-2">
        ${t.tags.map(x => `<span class="text-xs px-2 py-0.5 rounded-full border">${x}</span>`).join("")}
      </div>
      <div class="flex flex-wrap items-center gap-2 text-xs text-gray-600 mt-2">
        ${t.formats.map(f => `<span class="rounded-full border px-2 py-0.5">${f}</span>`).join("")}
      </div>
      <div class="flex gap-2 pt-3">
        <a href="${resolveBuilder(t)}" class="flex-1 inline-flex items-center justify-center px-3 py-2 rounded-md bg-primary text-white hover:bg-primary/90">Use this template</a>
        <button data-id="${t.id}" class="preview-btn border rounded-md px-3 py-2">Preview</button>
      </div>
    </div>
  `;
  return el;
}

function applyFilters() {
  const q = searchInput.value.trim().toLowerCase();
  const style = styleFilter.value;
  const tag = tagFilter.value;
  let res = TEMPLATES.filter(t =>
    (style === "All" || t.style === style) &&
    (tag === "All" || t.tags.includes(tag)) &&
    (q === "" ||
      t.name.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.tags.some(x => x.toLowerCase().includes(q)))
  );
  if (sortSelect.value === "name") {
    res = res.slice().sort((a, b) => a.name.localeCompare(b.name));
  }
  grid.innerHTML = "";
  res.forEach(t => grid.appendChild(card(t)));
}

styleFilter.addEventListener("change", applyFilters);
tagFilter.addEventListener("change", applyFilters);
sortSelect.addEventListener("change", applyFilters);
searchInput.addEventListener("input", applyFilters);

// Preview modal bindings
const modal = $("#previewModal");
const modalTitle = $("#modalTitle");
const modalImg = $("#modalImg");
const modalDesc = $("#modalDesc");
const modalTags = $("#modalTags");
const modalFormats = $("#modalFormats");
const modalUseBtn = $("#modalUseBtn");
const modalDownload = $("#modalDownload");
$("#modalClose").addEventListener("click", () => modal.classList.add("hidden"));
modal.addEventListener("click", (e) => { if (e.target === modal) modal.classList.add("hidden"); });

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".preview-btn");
  if (!btn) return;
  const t = TEMPLATES.find(x => x.id === btn.dataset.id);
  if (!t) return;
  modalTitle.textContent = t.name;
  modalImg.src = resolveThumb(t);
  modalImg.alt = `${t.name} full preview`;
  modalDesc.textContent = t.description;
  modalTags.innerHTML = t.tags.map(x => `<span class="text-xs px-2 py-0.5 rounded-full border">${x}</span>`).join("");
  modalFormats.innerHTML = t.formats.map(f => `<span class="text-xs rounded-full border px-2 py-0.5">${f}</span>`).join("");
  modalUseBtn.href = resolveBuilder(t);
  modalDownload.innerHTML = `<option value="">Download</option>` + t.formats
    .filter(f => t.downloadUrls && t.downloadUrls[f])
    .map(f => `<option value="${f}">${f}</option>`).join("");
  modalDownload.onchange = () => {
    const f = modalDownload.value;
    if (f && t.downloadUrls && t.downloadUrls[f]) {
      window.location.href = resolveDownload(t.downloadUrls[f]);
    }
  };
  modal.classList.remove("hidden");
});


function resolveDownload(filename) {
  if (!filename) return "";
  if (/^https?:\/\//.test(filename)) return filename;
  const base = (window.DOWNLOAD_BASE || "/static/templates/");
  return base + filename;
}

// Initial render
applyFilters();
