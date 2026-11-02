import React, { useEffect, useRef, useState } from "react";
import {
  Sparkles, Plus, X, ChevronLeft, ChevronRight, Mic, MicOff, Film,
  Download, ExternalLink, Check, Loader2, Sun, Moon, ImagePlus, Upload,
  Building2, MapPin, IndianRupee, Layers, User, Phone, Tag, Type,
  AlertCircle, Square, Monitor, Smartphone,
} from "lucide-react";
import "./VideoGenerator.css";

// 127.0.0.1 avoids the Windows IPv6 "localhost" problem.
const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const MIN_IMAGES = 4;
const MAX_IMAGES = 8;
const MAX_FILE_BYTES = 15 * 1024 * 1024;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const RENDER_STEPS = [
  "Checking details",
  "Preparing photos",
  "Writing voice-over",
  "Rendering scenes",
  "Encoding MP4",
];

const initialForm = {
  property_name: "Sunrise Heights",
  location: "Green Valley, Sample City",
  price: "₹ 65,00,000",
  property_type: "2-BHK Apartment",
  key_features: "Spacious balcony, Covered parking, 24/7 security, Near metro station, Modular kitchen",
  contact_name: "Sample Agent",
  contact_phone: "+91 00000 00000",
  cta_text: "Book your site visit today",
  narration_enabled: true,
  output_format: "landscape",
};

const REQUIRED = [
  ["property_name", "Property name"],
  ["location", "Location"],
  ["price", "Price"],
  ["property_type", "Property type"],
];

function readErrorMessage(data) {
  if (!data) return "Something went wrong. Please try again.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg || "Invalid input").join(" ");
  return "Something went wrong. Please try again.";
}

export default function VideoGenerator() {
  const [theme, setTheme] = useState(() =>
    window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  );
  const [form, setForm] = useState(initialForm);
  const [photos, setPhotos] = useState([]); // { id, file, url, name }
  const [status, setStatus] = useState("idle"); // idle | loading | done
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [result, setResult] = useState(null); // { videoUrl, script, format }
  const [dragging, setDragging] = useState(false);
  const [backend, setBackend] = useState("checking"); // checking | online | offline

  const formRef = useRef(null);
  const fileInput = useRef(null);
  const outputRef = useRef(null);
  const photosRef = useRef(photos);
  const abortRef = useRef(null); // AbortController for the active request

  // Theme
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // Keep the latest photos for cleanup
  useEffect(() => {
    photosRef.current = photos;
  }, [photos]);

  // On unmount: free preview URLs and cancel any running request
  useEffect(() => {
    return () => {
      photosRef.current.forEach((p) => URL.revokeObjectURL(p.url));
      abortRef.current?.abort();
    };
  }, []);

  // Backend health for the top bar
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/api/health`);
        if (alive) setBackend(res.ok ? "online" : "offline");
      } catch {
        if (alive) setBackend("offline");
      }
    };
    check();
    const id = setInterval(check, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Cycle the render step labels while generating
  useEffect(() => {
    if (status !== "loading") {
      setStepIndex(0);
      return;
    }
    const id = setInterval(() => setStepIndex((i) => Math.min(i + 1, RENDER_STEPS.length - 1)), 3500);
    return () => clearInterval(id);
  }, [status]);

  // Scroll to the finished video only once it is ready (not while rendering)
  useEffect(() => {
    if (status === "done") outputRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [status]);

  const setField = (name, value) => setForm((f) => ({ ...f, [name]: value }));

  const addFiles = (fileList) => {
    const files = Array.from(fileList);
    const room = MAX_IMAGES - photos.length;
    const valid = files.filter((f) => ACCEPTED_TYPES.includes(f.type) && f.size <= MAX_FILE_BYTES);

    const added = valid.slice(0, Math.max(room, 0)).map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
      url: URL.createObjectURL(file),
      name: "",
    }));
    setPhotos((prev) => [...prev, ...added]);

    if (valid.length !== files.length) setError("Only JPG, PNG and WEBP files under 15 MB are accepted.");
    else if (valid.length > room) setError(`You can add up to ${MAX_IMAGES} photos.`);
    else setError("");
  };

  const removePhoto = (id) => {
    setPhotos((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target) URL.revokeObjectURL(target.url);
      return prev.filter((p) => p.id !== id);
    });
  };

  const movePhoto = (index, dir) => {
    setPhotos((prev) => {
      const target = index + dir;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const renamePhoto = (id, name) =>
    setPhotos((prev) => prev.map((p) => (p.id === id ? { ...p, name } : p)));

  // Stop: cancels the request in the browser. The server may still finish its render in the background.
  const stopGeneration = () => {
    abortRef.current?.abort();
  };

  // Generate: submits the form through the browser so the normal validation runs
  const requestGenerate = () => {
    formRef.current?.requestSubmit();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    for (const [key, label] of REQUIRED) {
      if (!String(form[key]).trim()) {
        setError(`${label} is required.`);
        return;
      }
    }
    if (photos.length < MIN_IMAGES) {
      setError(`Add at least ${MIN_IMAGES} photos to continue.`);
      return;
    }

    setError("");
    setNotice("");
    setResult(null);
    setStatus("loading");

    const controller = new AbortController();
    abortRef.current = controller;

    const payload = {
      property_name: form.property_name.trim(),
      location: form.location.trim(),
      price: form.price.trim(),
      property_type: form.property_type.trim(),
      key_features: form.key_features.split(",").map((f) => f.trim()).filter(Boolean),
      contact_name: form.contact_name.trim(),
      contact_phone: form.contact_phone.trim(),
      cta_text: form.cta_text.trim(),
      narration_enabled: form.narration_enabled,
      output_format: form.output_format,
    };

    const body = new FormData();
    body.append("property", JSON.stringify(payload));
    body.append("image_names", JSON.stringify(photos.map((p) => p.name.trim())));
    photos.forEach((p) => body.append("images", p.file, p.file.name));

    try {
      const res = await fetch(`${API_URL}/api/generate-video-upload`, {
        method: "POST",
        body,
        signal: controller.signal,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(readErrorMessage(data));

      setResult({
        videoUrl: `${API_URL}${data.video_url}`,
        script: data.script || "",
        format: data.format || form.output_format,
      });
      setStatus("done");
    } catch (err) {
      if (err.name === "AbortError") {
        setNotice("Generation stopped.");
        setStatus("idle");
        return;
      }
      console.error(err);
      setError(
        err instanceof TypeError
          ? `Can't reach the server at ${API_URL}. Make sure the backend is running.`
          : err.message
      );
      setStatus("idle");
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  };

  const isLoading = status === "loading";
  const remaining = Math.max(MIN_IMAGES - photos.length, 0);
  const namedCount = photos.filter((p) => p.name.trim()).length;
  const showOutput = isLoading || (status === "done" && result);

  return (
    <div className="app">
      {/* Top bar */}
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="#top">
            <span className="brand-mark"><Sparkles size={15} /></span>
            <span className="brand-name">Property Studio</span>
          </a>

          <nav className="nav">
            <a href="#studio" className="nav-link is-active">Studio</a>
            <a href="#output" className="nav-link">Output</a>
          </nav>

          <div className="topbar-right">
            <span className={`status status-${backend}`} title={API_URL}>
              <span className="status-dot" />
              {backend === "online" ? "Backend online" : backend === "offline" ? "Backend offline" : "Connecting"}
            </span>
            <button
              type="button"
              className="icon-btn"
              onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
              aria-label="Toggle theme"
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            </button>
          </div>
        </div>
      </header>

      <main className="page" id="top">
        {/* Hero */}
        <section className="hero reveal">
          <div>
            <h1>Turn a listing into a video</h1>
          </div>
          <p>
            Fill in the details on the left and add photos on the right. Each photo name appears
            on screen and in the voice-over.
          </p>
        </section>

        {/* Toolbar */}
        <section className="toolbar card reveal" style={{ animationDelay: "80ms" }}>
          <div className="seg" role="group" aria-label="Voice-over">
            <button
              type="button"
              className={form.narration_enabled ? "is-active" : ""}
              onClick={() => setField("narration_enabled", true)}
            >
              <Mic size={14} /> Voice-over
            </button>
            <button
              type="button"
              className={!form.narration_enabled ? "is-active" : ""}
              onClick={() => setField("narration_enabled", false)}
            >
              <MicOff size={14} /> Silent
            </button>
          </div>

          <div className="seg" role="group" aria-label="Format">
            <button
              type="button"
              className={form.output_format === "landscape" ? "is-active" : ""}
              onClick={() => setField("output_format", "landscape")}
            >
              <Monitor size={14} /> Landscape
            </button>
            <button
              type="button"
              className={form.output_format === "vertical" ? "is-active" : ""}
              onClick={() => setField("output_format", "vertical")}
            >
              <Smartphone size={14} /> Vertical
            </button>
          </div>

          <span className="chip">
            <Film size={14} /> {form.output_format === "vertical" ? "1080 × 1920" : "1280 × 720"} · MP4 · 24 fps
          </span>

          <span className={`chip ${photos.length >= MIN_IMAGES ? "chip-ok" : ""}`}>
            <ImagePlus size={14} /> {photos.length} / {MAX_IMAGES} photos
          </span>

          <div className="toolbar-spacer" />

          <span className="toolbar-hint">
            {remaining > 0
              ? `Add ${remaining} more photo${remaining === 1 ? "" : "s"}`
              : `${namedCount} of ${photos.length} photos named`}
          </span>

          <button
            type="button"
            className={isLoading ? "btn-stop" : "btn-primary"}
            onClick={isLoading ? stopGeneration : requestGenerate}
          >
            {isLoading ? (
              <>
                <Square size={13} fill="currentColor" /> Stop generation
              </>
            ) : (
              "Generate video"
            )}
          </button>
        </section>

        {error && (
          <div className="alert reveal" role="alert">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {notice && !error && (
          <div className="notice reveal" role="status">
            {notice}
          </div>
        )}

        {/* Workspace */}
        <form id="studio" ref={formRef} className="workspace" onSubmit={handleSubmit} noValidate>
          {/* Details */}
          <section className="card details reveal" style={{ animationDelay: "140ms" }}>
            <header className="card-head">
              <h2>Details</h2>
              <span className="card-meta">Required fields marked by content</span>
            </header>

            <div className="fields">
              <Field icon={Building2} label="Property name" name="property_name" value={form.property_name} onChange={(e) => setField("property_name", e.target.value)} wide />
              <Field icon={MapPin} label="Location" name="location" value={form.location} onChange={(e) => setField("location", e.target.value)} />
              <Field icon={IndianRupee} label="Price" name="price" value={form.price} onChange={(e) => setField("price", e.target.value)} />
              <Field icon={Layers} label="Property type" name="property_type" value={form.property_type} onChange={(e) => setField("property_type", e.target.value)} />
              <Field icon={User} label="Contact name" name="contact_name" value={form.contact_name} onChange={(e) => setField("contact_name", e.target.value)} />
              <Field icon={Phone} label="Contact phone" name="contact_phone" value={form.contact_phone} onChange={(e) => setField("contact_phone", e.target.value)} />
              <Field
                icon={Tag}
                label="Key features"
                hint="Comma separated, up to 6"
                name="key_features"
                value={form.key_features}
                onChange={(e) => setField("key_features", e.target.value)}
                wide
              />
              <Field icon={Type} label="Closing line" name="cta_text" value={form.cta_text} onChange={(e) => setField("cta_text", e.target.value)} wide />
            </div>
          </section>

          {/* Photos */}
          <section className="card photos reveal" style={{ animationDelay: "200ms" }}>
            <header className="card-head">
              <h2>Photos</h2>
              <span className="card-meta">{photos.length} of {MAX_IMAGES}</span>
            </header>

            <div
              className={`dropzone ${dragging ? "is-over" : ""} ${photos.length === 0 ? "is-empty" : ""}`}
              onClick={() => fileInput.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                addFiles(e.dataTransfer.files);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && fileInput.current?.click()}
            >
              <span className="dropzone-icon">
                <Upload size={20} />
              </span>
              <div className="dropzone-text">
                <strong>Drop photos here or browse</strong>
                <span>JPG, PNG or WEBP · up to 15 MB each · {MIN_IMAGES} to {MAX_IMAGES} photos</span>
              </div>
              <input
                ref={fileInput}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                hidden
                onChange={(e) => {
                  addFiles(e.target.files);
                  e.target.value = "";
                }}
              />
            </div>

            {photos.length > 0 && (
              <ul className="tiles">
                {photos.map((p, i) => (
                  <li key={p.id} className="tile" style={{ animationDelay: `${i * 50}ms` }}>
                    <div className="tile-media">
                      <img src={p.url} alt={p.name || `Photo ${i + 1}`} />
                      <span className="tile-num">{i + 1}</span>
                      {p.name.trim() && <span className="tile-caption">{p.name}</span>}
                      <div className="tile-actions">
                        <button type="button" onClick={() => movePhoto(i, -1)} disabled={i === 0} aria-label="Move earlier">
                          <ChevronLeft size={15} />
                        </button>
                        <button type="button" onClick={() => movePhoto(i, 1)} disabled={i === photos.length - 1} aria-label="Move later">
                          <ChevronRight size={15} />
                        </button>
                        <button type="button" onClick={() => removePhoto(p.id)} aria-label="Remove photo" className="is-danger">
                          <X size={15} />
                        </button>
                      </div>
                    </div>
                    <input
                      className="tile-name"
                      placeholder="Name this photo"
                      value={p.name}
                      maxLength={40}
                      onChange={(e) => renamePhoto(p.id, e.target.value)}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </form>

        {/* Output: shown while rendering and after the video is ready */}
        {showOutput && (
          <section id="output" ref={outputRef} className="card output reveal">
            <header className="card-head">
              <h2>Your video</h2>
              <div className="output-actions">
                {status === "done" ? (
                  <span className="badge badge-ok"><Check size={13} /> Ready</span>
                ) : (
                  <>
                    <span className="badge"><Loader2 size={13} className="spin" /> Rendering</span>
                    <button type="button" className="btn-stop btn-stop-sm" onClick={stopGeneration}>
                      <Square size={11} fill="currentColor" /> Stop
                    </button>
                  </>
                )}
              </div>
            </header>

            {isLoading && (
              <div className="render">
                <div className="render-bar"><span /></div>
                <ol className="render-steps">
                  {RENDER_STEPS.map((label, i) => (
                    <li
                      key={label}
                      className={i < stepIndex ? "is-done" : i === stepIndex ? "is-active" : ""}
                    >
                      <span className="render-dot">{i < stepIndex ? <Check size={11} /> : i + 1}</span>
                      {label}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {status === "done" && result && (
              <div className="result">
                <video key={result.videoUrl} src={result.videoUrl} controls autoPlay loop playsInline />
                <div className="result-side">
                  <a className="btn-ghost" href={result.videoUrl} download="property_video.mp4">
                    <Download size={15} /> Download MP4
                  </a>
                  <a className="btn-ghost" href={result.videoUrl} target="_blank" rel="noreferrer">
                    <ExternalLink size={15} /> Open in new tab
                  </a>
                  {result.script && (
                    <details className="script">
                      <summary>Voice-over script</summary>
                      <p>{result.script}</p>
                    </details>
                  )}
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

function Field({ icon: Icon, label, hint, wide, ...inputProps }) {
  return (
    <label className={`field ${wide ? "is-wide" : ""}`}>
      <span className="field-label">
        <Icon size={13} />
        {label}
        {hint && <em>{hint}</em>}
      </span>
      <input type="text" className="field-input" {...inputProps} />
    </label>
  );
}