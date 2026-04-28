import { useEffect, useMemo, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import {
  askChat,
  createShipment,
  getAnalysisJob,
  getAnalysisResult,
  listDocuments,
  listShipments,
  login,
  startAnalysisJob,
  uploadDocuments,
} from "./api";
import { useToast } from "./toast";

const DOC_TYPES = ["AUTO", "CC", "INVOICE", "BC", "PHYTO"];
const ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"];
const MAX_UPLOAD_SIZE_MB = 20;
const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

const FIELD_LABELS = {
  consignee: "Consignataire / Notify",
  packages: "Nombre de colis",
  gross_weight: "Poids brut",
  commercial_weight: "Poids commercial",
  transport_unit_number: "Numero unite de transport",
  incoterm: "Incoterm",
  destination: "Destination",
  transport_type: "Type de transport",
};

const CRITICAL_CHECK_FIELDS = {
  exporter_name: "Exportateur",
  importer_name: "Importateur",
  container_number: "Numero de conteneur",
  packages_checked: "Nombre de colis",
  net_weight_checked: "Poids net",
  gross_weight_checked: "Poids brut",
  product_variety: "Variete botanique produit",
};

export default function App() {
  const { notify } = useToast();
  const navigate = useNavigate();

  const [isAuthenticated, setIsAuthenticated] = useState(Boolean(localStorage.getItem("token")));
  const [authForm, setAuthForm] = useState({ username: "admin", password: "admin123" });
  const [shipments, setShipments] = useState([]);
  const [totalShipments, setTotalShipments] = useState(0);
  const [page, setPage] = useState(1);
  const [searchQ, setSearchQ] = useState("");
  const [selectedShipmentId, setSelectedShipmentId] = useState("");
  const [newReference, setNewReference] = useState("");
  const [uploadItems, setUploadItems] = useState([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [activeJob, setActiveJob] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatAnswer, setChatAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const selectedShipment = useMemo(
    () => shipments.find((s) => String(s.id) === String(selectedShipmentId)),
    [shipments, selectedShipmentId]
  );

  function handleAuthError(err) {
    if ((err?.message || "").toLowerCase().includes("session expiree")) {
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      setIsAuthenticated(false);
      navigate("/");
      return true;
    }
    return false;
  }

  async function refreshShipments() {
    const data = await listShipments({ page, q: searchQ });
    setShipments(data.items);
    setTotalShipments(data.total);
    setSelectedShipmentId((prev) => {
      if (!data.items.length) return "";
      if (prev && data.items.some((s) => String(s.id) === String(prev))) return prev;
      return String(data.items[0].id);
    });
  }

  useEffect(() => {
    if (isAuthenticated) {
      refreshShipments().catch((err) => {
        if (!handleAuthError(err)) notify("error", err.message);
      });
    }
  }, [isAuthenticated, page]);

  useEffect(() => {
    if (!activeJob) return;
    const timer = setInterval(async () => {
      try {
        const job = await getAnalysisJob(activeJob.id);
        setActiveJob(job);
        if (job.status === "completed") {
          const result = await getAnalysisResult(job.id);
          setAnalysis(result);
          notify("success", "Analyse terminee.");
          clearInterval(timer);
          setLoading(false);
        }
        if (job.status === "failed") {
          notify("error", `Analyse echouee: ${job.error_message}`);
          clearInterval(timer);
          setLoading(false);
        }
      } catch (err) {
        clearInterval(timer);
        setLoading(false);
        if (!handleAuthError(err)) notify("error", err.message);
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [activeJob?.id]);

  async function onLogin(e) {
    e.preventDefault();
    try {
      await login(authForm.username, authForm.password);
      setIsAuthenticated(true);
      notify("success", "Connexion reussie.");
      navigate("/");
    } catch (err) {
      notify("error", `Echec connexion: ${err.message}`);
    }
  }

  async function onCreateShipment(e) {
    e.preventDefault();
    if (!newReference.trim()) return;
    setLoading(true);
    try {
      const shipment = await createShipment(newReference.trim());
      await refreshShipments();
      setSelectedShipmentId(String(shipment.id));
      setNewReference("");
      notify("success", "Expedition creee.");
    } catch (err) {
      if (!handleAuthError(err)) notify("error", err.message);
    } finally {
      setLoading(false);
    }
  }

  function addFiles(files) {
    const selectedFiles = Array.from(files || []);
    if (selectedFiles.length === 0) return;

    const validItems = [];
    selectedFiles.forEach((file) => {
      const lowerName = (file.name || "").toLowerCase();
      const isExtensionAllowed = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
      if (!isExtensionAllowed) {
        notify("error", `Type non supporte: ${file.name}`);
        return;
      }
      if (file.size > MAX_UPLOAD_SIZE_BYTES) {
        notify("error", `${file.name} depasse ${MAX_UPLOAD_SIZE_MB} MB`);
        return;
      }
      validItems.push({ file, docType: "INVOICE" });
    });

    if (validItems.length > 0) {
      setUploadItems((prev) => [...prev, ...validItems]);
    }
  }

  function removeUploadItem(index) {
    setUploadItems((prev) => prev.filter((_, i) => i !== index));
  }

  async function onUpload() {
    if (!selectedShipmentId) {
      notify("error", "Selectionnez une expedition avant le televersement.");
      return;
    }
    if (uploadItems.length === 0) {
      notify("error", "Ajoutez au moins un document.");
      return;
    }
    setLoading(true);
    try {
      await uploadDocuments(selectedShipmentId, uploadItems, setUploadProgress);
      setUploadItems([]);
      setUploadProgress(0);
      notify("success", "Documents televerses.");
    } catch (err) {
      if (!handleAuthError(err)) notify("error", err.message);
    } finally {
      setLoading(false);
    }
  }

  async function onAnalyze() {
    if (!selectedShipmentId) {
      notify("error", "Selectionnez une expedition avant l'analyse.");
      return;
    }
    setLoading(true);
    try {
      const docs = await listDocuments(selectedShipmentId);
      if (!docs.length) {
        notify("error", "Aucun document televerse pour cette expedition.");
        setLoading(false);
        return;
      }
      const job = await startAnalysisJob(selectedShipmentId);
      setActiveJob(job);
      notify("success", `Job analyse #${job.id} lance.`);
    } catch (err) {
      if (!handleAuthError(err)) notify("error", err.message);
      setLoading(false);
    }
  }

  async function onAsk() {
    if (!selectedShipmentId || !chatQuestion.trim()) return;
    setLoading(true);
    try {
      const res = await askChat(selectedShipmentId, chatQuestion.trim());
      setChatAnswer(res.answer);
    } catch (err) {
      if (handleAuthError(err)) {
        setChatAnswer("");
      } else {
        setChatAnswer(`Erreur: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  }

  const issueByField = useMemo(() => {
    const map = {};
    (analysis?.issues || []).forEach((issue) => {
      map[issue.field] = issue.level;
    });
    return map;
  }, [analysis]);

  const criticalIssueRows = useMemo(() => {
    if (!analysis?.issues?.length) return [];
    return analysis.issues.filter((issue) => CRITICAL_CHECK_FIELDS[issue.field]);
  }, [analysis]);

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <form onSubmit={onLogin} className="w-full max-w-md rounded-xl bg-white p-6 shadow">
          <h1 className="mb-4 text-xl font-bold">Connexion</h1>
          <p className="mb-3 text-sm text-slate-600">Identifiants par defaut: admin / admin123</p>
          <input
            className="mb-2 w-full rounded border p-2"
            value={authForm.username}
            onChange={(e) => setAuthForm((p) => ({ ...p, username: e.target.value }))}
            placeholder="Nom d'utilisateur"
          />
          <input
            type="password"
            className="mb-3 w-full rounded border p-2"
            value={authForm.password}
            onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))}
            placeholder="Mot de passe"
          />
          <button className="w-full rounded bg-slate-900 px-4 py-2 text-white">Se connecter</button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6 text-slate-900">
      <div className="mx-auto grid max-w-7xl grid-cols-12 gap-6">
        <aside className="col-span-12 rounded-xl bg-slate-900 p-4 text-white lg:col-span-2">
          <h2 className="mb-4 text-sm font-bold uppercase tracking-wide">Analyseur documentaire</h2>
          <nav className="space-y-2 text-sm">
            <Link to="/" className="block rounded bg-slate-800 px-3 py-2">
              Operations
            </Link>
            <Link to="/analytics" className="block rounded px-3 py-2 hover:bg-slate-800">
              Statistiques
            </Link>
          </nav>
          <button
            className="mt-6 w-full rounded bg-red-500 px-3 py-2 text-sm"
            onClick={() => {
              localStorage.removeItem("token");
              setIsAuthenticated(false);
            }}
          >
            Deconnexion
          </button>
        </aside>

        <main className="col-span-12 space-y-6 lg:col-span-10">
          <header className="rounded-xl bg-white p-6 shadow-sm">
            <h1 className="text-2xl font-bold">Analyseur de coherence documentaire</h1>
            <p className="mt-1 text-sm text-slate-600">
              Controle automatique des fichiers PDF/documents selon la structure attendue.
            </p>
          </header>

          <Routes>
            <Route
              path="/"
              element={
                <>
                  <section className="grid gap-6 lg:grid-cols-3">
                    <div className="rounded-xl bg-white p-5 shadow-sm">
                      <h2 className="mb-3 text-lg font-semibold">Gestion des expeditions</h2>
                      <form onSubmit={onCreateShipment} className="space-y-2">
                        <input
                          value={newReference}
                          onChange={(e) => setNewReference(e.target.value)}
                          placeholder="Reference expedition"
                          className="w-full rounded border p-2"
                        />
                        <button disabled={loading} className="rounded bg-blue-600 px-4 py-2 text-white">
                          Creer
                        </button>
                      </form>

                      <div className="mt-3">
                        <input
                          placeholder="Rechercher une reference..."
                          className="w-full rounded border p-2 text-sm"
                          value={searchQ}
                          onChange={(e) => setSearchQ(e.target.value)}
                        />
                        <button className="mt-2 rounded bg-slate-700 px-3 py-1 text-xs text-white" onClick={refreshShipments}>
                          Filtrer
                        </button>
                      </div>

                      <div className="mt-4">
                        <label className="mb-1 block text-sm">Selectionner une expedition</label>
                        <select
                          value={selectedShipmentId}
                          onChange={(e) => setSelectedShipmentId(e.target.value)}
                          className="w-full rounded border p-2"
                        >
                          <option value="">-- Choisir --</option>
                          {shipments.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.reference} ({s.status})
                            </option>
                          ))}
                        </select>
                        <p className="mt-2 text-xs text-slate-500">Total expeditions: {totalShipments}</p>
                        <div className="mt-2 flex gap-2">
                          <button className="rounded border px-2 py-1 text-xs" onClick={() => setPage((p) => Math.max(1, p - 1))}>
                            Precedent
                          </button>
                          <button className="rounded border px-2 py-1 text-xs" onClick={() => setPage((p) => p + 1)}>
                            Suivant
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-xl bg-white p-5 shadow-sm lg:col-span-2">
                      <h2 className="mb-3 text-lg font-semibold">Televersement des documents</h2>
                      <p className="mb-3 text-xs text-slate-500">
                        Formats acceptes: {ALLOWED_EXTENSIONS.join(", ")} - Taille max: {MAX_UPLOAD_SIZE_MB} MB/fichier
                      </p>
                      <label
                        className="flex cursor-pointer items-center justify-center rounded-lg border-2 border-dashed border-slate-300 p-8 text-slate-600 hover:bg-slate-50"
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => {
                          e.preventDefault();
                          addFiles(e.dataTransfer.files);
                        }}
                      >
                        Glisser-deposer les PDF/images ici, ou cliquer pour selectionner
                        <input type="file" multiple className="hidden" onChange={(e) => addFiles(e.target.files)} />
                      </label>

                      {uploadProgress > 0 && (
                        <div className="mt-3">
                          <div className="h-2 w-full rounded bg-slate-200">
                            <div className="h-2 rounded bg-emerald-500" style={{ width: `${uploadProgress}%` }} />
                          </div>
                          <p className="mt-1 text-xs text-slate-500">Progression: {uploadProgress}%</p>
                        </div>
                      )}

                      <div className="mt-4 space-y-2">
                        {uploadItems.length === 0 && (
                          <p className="rounded border border-dashed p-3 text-xs text-slate-500">
                            Aucun fichier ajoute pour le moment.
                          </p>
                        )}
                        {uploadItems.map((item, idx) => (
                          <div key={`${item.file.name}-${idx}`} className="grid grid-cols-12 items-center gap-2 rounded border p-2">
                            <span className="col-span-6 truncate text-sm">{item.file.name}</span>
                            <span className="col-span-3 text-xs text-slate-500">{Math.round(item.file.size / 1024)} KB</span>
                            <select
                              className="col-span-3 rounded border p-1 text-sm"
                              value={item.docType}
                              onChange={(e) =>
                                setUploadItems((prev) => prev.map((it, i) => (i === idx ? { ...it, docType: e.target.value } : it)))
                              }
                            >
                              {DOC_TYPES.map((type) => (
                                <option key={type} value={type}>
                                  {type}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              className="col-span-12 rounded bg-red-50 px-2 py-1 text-xs text-red-700 hover:bg-red-100"
                              onClick={() => removeUploadItem(idx)}
                            >
                              Retirer
                            </button>
                          </div>
                        ))}
                      </div>

                      <div className="mt-4 flex gap-2">
                        <button
                          type="button"
                          disabled={loading || !selectedShipmentId || uploadItems.length === 0}
                          onClick={onUpload}
                          className="rounded bg-emerald-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Televerser
                        </button>
                        <button
                          type="button"
                          disabled={loading || !selectedShipmentId}
                          onClick={onAnalyze}
                          className="rounded bg-indigo-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Analyser
                        </button>
                        <button
                          type="button"
                          disabled={loading || uploadItems.length === 0}
                          onClick={() => setUploadItems([])}
                          className="rounded bg-slate-200 px-4 py-2 text-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Vider la liste
                        </button>
                        {activeJob && <span className="rounded bg-slate-100 px-3 py-2 text-xs">Job #{activeJob.id}: {activeJob.status}</span>}
                      </div>
                      {!selectedShipmentId && <p className="mt-2 text-xs text-amber-700">Choisis une expedition pour activer les actions.</p>}
                      {!!selectedShipmentId && uploadItems.length === 0 && (
                        <p className="mt-2 text-xs text-slate-500">Ajoute des fichiers pour activer le bouton Televerser.</p>
                      )}
                    </div>
                  </section>

                  {analysis && (
                    <section className="rounded-xl bg-white p-5 shadow-sm">
                      <div className="mb-3 flex items-center justify-between">
                        <h2 className="text-lg font-semibold">Tableau de coherence</h2>
                        <span
                          className={`rounded px-3 py-1 text-sm font-medium ${
                            analysis.status === "VALID"
                              ? "bg-emerald-100 text-emerald-700"
                              : analysis.status === "WARNING"
                              ? "bg-orange-100 text-orange-700"
                              : "bg-red-100 text-red-700"
                          }`}
                        >
                          {analysis.status}
                        </span>
                      </div>

                      <div className="overflow-x-auto">
                        <table className="min-w-full border-collapse text-sm">
                          <thead>
                            <tr className="bg-slate-100 text-left">
                              <th className="border p-2">Champ</th>
                              {analysis.documents.map((doc) => (
                                <th key={doc.id} className="border p-2">
                                  {doc.doc_type}
                                </th>
                              ))}
                              <th className="border p-2">Etat</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.keys(FIELD_LABELS).map((field) => {
                              const level = issueByField[field];
                              return (
                                <tr key={field}>
                                  <td className="border p-2 font-medium">{FIELD_LABELS[field]}</td>
                                  {analysis.documents.map((doc) => (
                                    <td key={`${doc.id}-${field}`} className="border p-2">
                                      {String(doc[field] ?? "") || "-"}
                                    </td>
                                  ))}
                                  <td
                                    className={`border p-2 font-semibold ${
                                      level === "ERROR"
                                        ? "bg-red-50 text-red-700"
                                        : level === "WARNING"
                                        ? "bg-orange-50 text-orange-700"
                                        : "bg-emerald-50 text-emerald-700"
                                    }`}
                                  >
                                    {level || "OK"}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  )}

                  {analysis && criticalIssueRows.length > 0 && (
                    <section className="rounded-xl bg-white p-5 shadow-sm">
                      <h2 className="mb-3 text-lg font-semibold">Controles critiques inter-documents</h2>
                      <div className="overflow-x-auto">
                        <table className="min-w-full border-collapse text-sm">
                          <thead>
                            <tr className="bg-slate-100 text-left">
                              <th className="border p-2">Controle</th>
                              {analysis.documents.map((doc) => (
                                <th key={`critical-head-${doc.id}`} className="border p-2">
                                  {doc.doc_type}
                                </th>
                              ))}
                              <th className="border p-2">Etat</th>
                            </tr>
                          </thead>
                          <tbody>
                            {criticalIssueRows.map((issue, idx) => (
                              <tr key={`${issue.field}-${idx}`}>
                                <td className="border p-2 font-medium">{CRITICAL_CHECK_FIELDS[issue.field]}</td>
                                {analysis.documents.map((doc) => (
                                  <td key={`${issue.field}-${doc.id}`} className="border p-2">
                                    {String(issue.values?.[doc.doc_type] ?? "") || "-"}
                                  </td>
                                ))}
                                <td
                                  className={`border p-2 font-semibold ${
                                    issue.level === "ERROR"
                                      ? "bg-red-50 text-red-700"
                                      : issue.level === "WARNING"
                                      ? "bg-orange-50 text-orange-700"
                                      : "bg-emerald-50 text-emerald-700"
                                  }`}
                                >
                                  {issue.level}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </section>
                  )}

                  <section className="rounded-xl bg-white p-5 shadow-sm">
                    <h2 className="mb-2 text-lg font-semibold">Assistant</h2>
                    <div className="flex gap-2">
                      <input
                        value={chatQuestion}
                        onChange={(e) => setChatQuestion(e.target.value)}
                        className="flex-1 rounded border p-2"
                        placeholder="Posez votre question..."
                      />
                      <button onClick={onAsk} className="rounded bg-slate-800 px-4 py-2 text-white" disabled={loading || !selectedShipment}>
                        Envoyer
                      </button>
                    </div>
                    {chatAnswer && <p className="mt-3 rounded bg-slate-100 p-3 text-sm">{chatAnswer}</p>}
                  </section>
                </>
              }
            />

            <Route
              path="/analytics"
              element={
                <section className="grid gap-4 md:grid-cols-3">
                  <div className="rounded-xl bg-white p-5 shadow-sm">
                    <h3 className="text-sm text-slate-500">Total expeditions</h3>
                    <p className="mt-2 text-2xl font-bold">{totalShipments}</p>
                  </div>
                  <div className="rounded-xl bg-white p-5 shadow-sm">
                    <h3 className="text-sm text-slate-500">Taux d'erreur</h3>
                    <p className="mt-2 text-2xl font-bold">{analysis?.status === "INCONSISTENT" ? "100%" : "0%"}</p>
                  </div>
                  <div className="rounded-xl bg-white p-5 shadow-sm">
                    <h3 className="text-sm text-slate-500">Anomalie la plus frequente</h3>
                    <p className="mt-2 text-sm font-semibold">{analysis?.issues?.[0]?.field || "N/A"}</p>
                  </div>
                </section>
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}
