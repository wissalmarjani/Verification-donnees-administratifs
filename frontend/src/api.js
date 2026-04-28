const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

function getAuthHeader() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function parseErrorMessage(rawText) {
  if (!rawText) return "Request failed.";
  try {
    const parsed = JSON.parse(rawText);
    if (typeof parsed?.detail === "string") return parsed.detail;
    if (Array.isArray(parsed?.detail)) return parsed.detail.map((d) => d?.msg || JSON.stringify(d)).join(", ");
    return typeof parsed === "string" ? parsed : rawText;
  } catch {
    return rawText;
  }
}

async function parseOrThrow(res) {
  const rawText = await res.text();
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      throw new Error("Session expiree. Reconnectez-vous.");
    }
    throw new Error(parseErrorMessage(rawText));
  }
  if (!rawText) return null;
  try {
    return JSON.parse(rawText);
  } catch {
    throw new Error("Invalid server response.");
  }
}

export async function login(username, password) {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await parseOrThrow(res);
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("role", data.role);
  return data;
}

export async function createShipment(reference) {
  const res = await fetch(`${API_URL}/shipments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeader() },
    body: JSON.stringify({ reference }),
  });
  return parseOrThrow(res);
}

export async function listShipments({ page = 1, pageSize = 20, status = "", q = "" } = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    ...(status ? { status } : {}),
    ...(q ? { q } : {}),
  });
  const res = await fetch(`${API_URL}/shipments?${params.toString()}`, { headers: getAuthHeader() });
  return parseOrThrow(res);
}

export async function uploadDocuments(shipmentId, items, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    items.forEach((item) => {
      form.append("doc_types", item.docType);
      form.append("files", item.file);
    });

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/shipments/${shipmentId}/documents`);
    const token = localStorage.getItem("token");
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (!onProgress || !e.lengthComputable) return;
      onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        if (!xhr.responseText) {
          resolve([]);
          return;
        }
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Invalid upload response from server."));
        }
        return;
      }
      reject(new Error(parseErrorMessage(xhr.responseText)));
    };
    xhr.onerror = () => reject(new Error("Upload failed. Check API URL or network."));
    xhr.send(form);
  });
}

export async function listDocuments(shipmentId) {
  const res = await fetch(`${API_URL}/shipments/${shipmentId}/documents`, { headers: getAuthHeader() });
  return parseOrThrow(res);
}

export async function startAnalysisJob(shipmentId) {
  const res = await fetch(`${API_URL}/shipments/${shipmentId}/analysis-jobs`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  return parseOrThrow(res);
}

export async function getAnalysisJob(jobId) {
  const res = await fetch(`${API_URL}/shipments/analysis-jobs/${jobId}`, { headers: getAuthHeader() });
  return parseOrThrow(res);
}

export async function getAnalysisResult(jobId) {
  const res = await fetch(`${API_URL}/shipments/analysis-jobs/${jobId}/result`, { headers: getAuthHeader() });
  return parseOrThrow(res);
}

export function reportUrl(shipmentId) {
  const token = localStorage.getItem("token");
  return `${API_URL}/shipments/${shipmentId}/report${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

export async function askChat(shipmentId, question) {
  const res = await fetch(`${API_URL}/shipments/${shipmentId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeader() },
    body: JSON.stringify({ question }),
  });
  return parseOrThrow(res);
}
