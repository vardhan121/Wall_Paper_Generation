const API = "http://127.0.0.1:8765";
const status = document.getElementById("status");

async function get(path, options) {
  const r = await fetch(API + path, options);
  const text = await r.text();
  if (!r.ok) throw new Error(`${r.status}: ${text}`);
  return text ? JSON.parse(text) : {};
}

document.getElementById("health").onclick = async () => {
  try {
    const data = await get("/api/health");
    status.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    status.textContent = "Local service unavailable:\n" + e;
  }
};

document.getElementById("generate").onclick = async () => {
  status.textContent = "Generating...";
  try {
    const data = await get("/api/generate", { method: "POST" });
    status.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    status.textContent = "Generation failed:\n" + e;
  }
};
