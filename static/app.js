// --- DOM refs ---
const $ = (id) => document.getElementById(id);
const dropZone = $("dropZone");
const fileInput = $("fileInput");
const fileList = $("fileList");
const fileCount = $("fileCount");
const terminal = $("terminal");
const runBtn = $("runBtn");
const keyBadge = $("keyBadge");

// --- Helpers ---
function fmtSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

function fileIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  const map = {
    png: "🖼️", jpg: "🖼️", jpeg: "🖼️", gif: "🖼️", webp: "🖼️", avif: "🖼️", svg: "🖼️",
    pdf: "📄", txt: "📄", csv: "📄", docx: "📄", xlsx: "📄", rtf: "📄", pptx: "📄", html: "📄", eml: "📄",
    mp4: "🎬", mov: "🎬", mp3: "🎵", wav: "🎵", m4a: "🎵",
    stl: "🧊", scad: "🧊", gcode: "🧊",
    app: "📦", dmg: "📦", zip: "📦", exe: "📦", iso: "📦",
  };
  return map[ext] || "📎";
}

// --- API ---
async function api(path, method = "GET", body = null) {
  const opts = { method };
  if (body) {
    if (body instanceof FormData) {
      opts.body = body;
    } else {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
  }
  const res = await fetch(path, opts);
  return res.json();
}

// --- File list ---
async function refreshFiles() {
  const files = await api("/api/files");
  fileCount.textContent = `(${files.length})`;
  if (files.length === 0) {
    fileList.innerHTML = '<div class="empty-state">No files in workspace. Upload some or load samples.</div>';
    return;
  }
  fileList.innerHTML = files
    .map(
      (f) => `
      <div class="file-item">
        <span class="file-icon">${fileIcon(f.name)}</span>
        <span class="file-name" title="${f.path}">${f.path}</span>
        <span class="file-size">${fmtSize(f.size)}</span>
      </div>`
    )
    .join("");
}

// --- Upload ---
// Uploads [{ file, path }] pairs, where path is relative to the chosen folder.
async function uploadEntries(entries) {
  if (!entries.length) return;
  const fd = new FormData();
  for (const e of entries) fd.append("files", e.file);
  fd.append("paths", JSON.stringify(entries.map((e) => e.path)));
  await api("/api/upload", "POST", fd);
  refreshFiles();
}

function uploadFiles(files) {
  uploadEntries([...files].map((f) => ({ file: f, path: f.name })));
}

// A picked folder's own name is dropped so its contents become the workspace.
function stripRoot(rel) {
  const parts = rel.split("/").filter(Boolean);
  return parts.length > 1 ? parts.slice(1).join("/") : parts[0] || rel;
}

function readEntries(reader) {
  return new Promise((resolve, reject) => {
    const all = [];
    const next = () =>
      reader.readEntries((batch) => {
        if (!batch.length) return resolve(all);
        all.push(...batch);
        next();
      }, reject);
    next();
  });
}

async function walkDir(dirEntry, prefix, out) {
  for (const child of await readEntries(dirEntry.createReader())) {
    if (child.isFile) {
      const file = await new Promise((res, rej) => child.file(res, rej));
      out.push({ file, path: prefix + file.name });
    } else {
      await walkDir(child, prefix + child.name + "/", out);
    }
  }
}

// Folder entries from a drop, or null when only loose files were dropped.
async function droppedFolder(dt) {
  const out = [];
  let sawFolder = false;
  for (const item of dt.items || []) {
    const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
    if (entry && entry.isDirectory) {
      sawFolder = true;
      await walkDir(entry, "", out);
    }
  }
  return sawFolder ? out : null;
}

const folderInput = $("folderInput");

dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => uploadFiles(e.target.files));
$("browseFiles").addEventListener("click", (e) => {
  e.stopPropagation();
  fileInput.click();
});
$("browseFolder").addEventListener("click", (e) => {
  e.stopPropagation();
  folderInput.click();
});
folderInput.addEventListener("change", (e) => {
  uploadEntries(
    [...e.target.files].map((f) => ({ file: f, path: stripRoot(f.webkitRelativePath || f.name) }))
  );
  e.target.value = "";
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", async (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const folder = await droppedFolder(e.dataTransfer);
  if (folder) return uploadEntries(folder);
  uploadFiles(e.dataTransfer.files);
});

// --- Sample / Clear ---
$("sampleBtn").addEventListener("click", async () => {
  await api("/api/sample", "POST");
  refreshFiles();
});
$("clearBtn").addEventListener("click", async () => {
  await api("/api/clear", "POST");
  refreshFiles();
});

// --- Output ---
function setOutput(text) {
  if (!text || !text.trim()) {
    terminal.innerHTML = '<div class="terminal-placeholder">No output.</div>';
    return;
  }
  terminal.innerHTML = text
    .split("\n")
    .map((line) => {
      let cls = "";
      if (line.startsWith("RENAMED:")) cls = "line-renamed";
      else if (line.startsWith("MOVED:")) cls = "line-moved";
      else if (line.startsWith("SKIP")) cls = "line-skip";
      else if (line.startsWith("DRY-RUN")) cls = "line-dry";
      else if (line.startsWith("STATUS:")) cls = "line-status";
      else if (/error|Error|ERROR|Traceback|SystemExit/i.test(line)) cls = "line-error";
      const esc = line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      return `<div class="${cls}">${esc || "&nbsp;"}</div>`;
    })
    .join("");
  terminal.scrollTop = terminal.scrollHeight;
}

$("clearOutput").addEventListener("click", () => {
  terminal.innerHTML = '<div class="terminal-placeholder">Run the organizer to see output here.</div>';
});

// --- Run ---
runBtn.addEventListener("click", async () => {
  const opts = {
    dry_run: $("dryRun").checked,
    recursive: $("recursive").checked,
    organize_only: $("organizeOnly").checked,
    organize: $("organize").checked,
    mnemonically_boosted: $("mnemonicallyBoosted").checked,
    prune_empty_dirs: $("pruneEmptyDirs").checked,
    trace: $("trace").checked,
    model: $("model").value,
  };
  runBtn.disabled = true;
  runBtn.textContent = "⏳ Running…";
  terminal.innerHTML = '<div class="terminal-placeholder">Running organizer…</div>';
  try {
    const res = await api("/api/run", "POST", opts);
    setOutput(res.output);
    refreshFiles();
  } catch (err) {
    setOutput("Error: " + err.message);
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "▶ Run Organizer";
  }
});

// --- Key status ---
async function checkKey() {
  const res = await api("/api/key-status");
  if (res.has_key) {
    keyBadge.textContent = "✓ API Key Set";
    keyBadge.className = "key-badge ok";
  } else {
    keyBadge.textContent = "⚠ No API Key (organize-only works)";
    keyBadge.className = "key-badge missing";
  }
}

// --- Init ---
checkKey();
refreshFiles();
