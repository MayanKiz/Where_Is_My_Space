"use client";

import {
  ArrowLeft, ArrowUpRight, CheckCircle2, CircleAlert, CloudUpload, Database,
  FileVideo2, HardDrive, LockKeyhole, MonitorUp, Radio, RefreshCw, Smartphone,
  ShieldCheck, Square, Video, Wifi, X,
} from "lucide-react";
import Link from "next/link";
import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  CaptureSource, UploadJobResponse, UploadSourceType,
  listCaptureSources, registerCaptureSource, uploadVideo,
} from "@/lib/api";
import "./capture.css";

type Mode = "camera" | "screen" | "file" | "external";
type Feedback = { kind: "success" | "error" | "info"; message: string };

function recorderMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = [
    "video/mp4;codecs=avc1.42E01E",
    "video/mp4",
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

function suggestedFileName(type: "camera" | "screen", mimeType: string): string {
  const extension = mimeType.includes("mp4") ? "mp4" : "webm";
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `wims-${type}-${timestamp}.${extension}`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const modeCards: { id: Mode; title: string; description: string; icon: typeof Video }[] = [
  { id: "camera", title: "Phone camera", description: "Use the rear camera and record a clip.", icon: Video },
  { id: "screen", title: "Screen share", description: "Capture a playable video, where supported.", icon: MonitorUp },
  { id: "file", title: "Video file", description: "Upload an existing MP4 or WebM recording.", icon: FileVideo2 },
  { id: "external", title: "CCTV / IP camera", description: "Register an RTSP / RTSPS source.", icon: Radio },
];

export default function CapturePage() {
  const [mode, setMode] = useState<Mode>("camera");
  const [accessCode, setAccessCode] = useState("");
  const [accessInput, setAccessInput] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [sourceName, setSourceName] = useState("Phone camera");
  const [deviceLabel, setDeviceLabel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [recordedFile, setRecordedFile] = useState<File | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [job, setJob] = useState<UploadJobResponse | null>(null);
  const [sources, setSources] = useState<CaptureSource[]>([]);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [screenShareAvailable, setScreenShareAvailable] = useState(false);
  const [externalName, setExternalName] = useState("");
  const [rtspUrl, setRtspUrl] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [cameraName, setCameraName] = useState("Phone camera");

  const liveVideoRef = useRef<HTMLVideoElement>(null);
  const recordedVideoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const recordTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const uploadAbortRef = useRef(false);

  useEffect(() => {
    setScreenShareAvailable(
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices &&
      typeof navigator.mediaDevices.getDisplayMedia === "function",
    );
    const savedCode = window.sessionStorage.getItem("wims-capture-code");
    if (savedCode) {
      setAccessInput(savedCode);
      void authorize(savedCode, true);
    }
    // On unmount, camera/screen permissions are released below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (liveVideoRef.current && stream) {
      liveVideoRef.current.srcObject = stream;
      void liveVideoRef.current.play().catch(() => undefined);
    }
  }, [stream]);

  useEffect(() => {
    if (recordedVideoRef.current && previewUrlRef.current) {
      recordedVideoRef.current.src = previewUrlRef.current;
      recordedVideoRef.current.load();
    }
  }, [recordedFile]);

  const stopStream = useCallback(() => {
    if (recordTimeoutRef.current) {
      clearTimeout(recordTimeoutRef.current);
      recordTimeoutRef.current = null;
    }
    const active = streamRef.current;
    active?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStream(null);
    setIsRecording(false);
  }, []);

  useEffect(() => () => {
    const active = streamRef.current;
    active?.getTracks().forEach((track) => track.stop());
    if (recordTimeoutRef.current) clearTimeout(recordTimeoutRef.current);
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
  }, []);

  async function authorize(code: string, silent = false) {
    if (!code.trim()) {
      setFeedback({ kind: "error", message: "Enter the WIMS Capture access code." });
      return;
    }
    setAuthBusy(true);
    setFeedback(null);
    try {
      const loaded = await listCaptureSources(code.trim());
      setAccessCode(code.trim());
      setAccessInput(code.trim());
      window.sessionStorage.setItem("wims-capture-code", code.trim());
      setSources(loaded);
      setAuthorized(true);
      if (!silent) setFeedback({ kind: "success", message: "This device is connected to WIMS Capture." });
    } catch (error) {
      setAuthorized(false);
      setAccessCode("");
      window.sessionStorage.removeItem("wims-capture-code");
      if (!silent) setFeedback({ kind: "error", message: error instanceof Error ? error.message : "Could not connect to WIMS." });
    } finally {
      setAuthBusy(false);
    }
  }

  async function refreshSources() {
    try {
      setSources(await listCaptureSources(accessCode));
    } catch (error) {
      setFeedback({ kind: "error", message: error instanceof Error ? error.message : "Could not refresh sources." });
    }
  }

  function chooseMode(next: Mode) {
    if (isRecording) return;
    if (streamRef.current) stopStream();
    setMode(next);
    setFeedback(null);
    setJob(null);
    if (next === "camera") setSourceName("Phone camera");
    if (next === "screen") setSourceName("Screen recording");
    if (next === "file") setSourceName("Uploaded video");
  }

  async function startCamera() {
    setFeedback(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setFeedback({ kind: "error", message: "This browser cannot open the camera. Open WIMS Capture over HTTPS in a modern browser." });
      return;
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = media;
      setStream(media);
      setRecordedFile(null);
      setSourceName(cameraName.trim() || "Phone camera");
      setFeedback({ kind: "info", message: "Camera preview is ready. Start recording when the area is in view." });
    } catch (error) {
      setFeedback({ kind: "error", message: error instanceof Error ? error.message : "Camera permission was not granted." });
    }
  }

  async function startScreenShare() {
    setFeedback(null);
    const getDisplayMedia = navigator.mediaDevices?.getDisplayMedia;
    if (!getDisplayMedia) {
      setFeedback({ kind: "error", message: "Screen sharing is not supported in this browser. Use your phone's built-in screen recorder, then choose Video file." });
      return;
    }
    try {
      const media = await getDisplayMedia.call(navigator.mediaDevices, { video: true, audio: false });
      media.getVideoTracks()[0]?.addEventListener("ended", () => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
        else stopStream();
      }, { once: true });
      streamRef.current = media;
      setStream(media);
      setRecordedFile(null);
      setSourceName("Screen recording");
      setFeedback({ kind: "info", message: "Screen is being shared. Start recording, then play the video you want WIMS to inspect." });
    } catch (error) {
      setFeedback({ kind: "error", message: error instanceof Error ? error.message : "Screen sharing was cancelled or blocked." });
    }
  }

  function startRecording() {
    const active = streamRef.current;
    if (!active) {
      setFeedback({ kind: "error", message: mode === "camera" ? "Start the camera preview first." : "Start screen sharing first." });
      return;
    }
    if (typeof MediaRecorder === "undefined") {
      setFeedback({ kind: "error", message: "This browser cannot record the selected source. Try recording on your phone and uploading the saved video." });
      return;
    }
    const mimeType = recorderMimeType();
    if (!mimeType) {
      setFeedback({ kind: "error", message: "No supported browser recording format was found. Use the phone&apos;s built-in recorder and upload its video." });
      return;
    }
    try {
      chunksRef.current = [];
      const recorder = new MediaRecorder(active, { mimeType });
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => setFeedback({ kind: "error", message: "The browser could not record this source. Try a shorter clip." });
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType });
        if (!blob.size) {
          setFeedback({ kind: "error", message: "No video data was recorded. Try again." });
          stopStream();
          return;
        }
        const name = suggestedFileName(mode === "screen" ? "screen" : "camera", blob.type);
        const captured = new File([blob], name, { type: blob.type });
        if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = URL.createObjectURL(captured);
        setRecordedFile(captured);
        setFile(null);
        setSourceName(mode === "screen" ? "Screen recording" : (cameraName.trim() || "Phone camera"));
        stopStream();
        setFeedback({ kind: "success", message: `Recording ready (${formatBytes(captured.size)}). Review it, then upload to WIMS.` });
      };
      recorder.start(1000);
      setIsRecording(true);
      setFeedback({ kind: "info", message: "Recording locally on this device. Stop when the desired view has been captured." });
      recordTimeoutRef.current = setTimeout(() => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      }, 90_000);
    } catch (error) {
      setFeedback({ kind: "error", message: error instanceof Error ? error.message : "Could not start recording." });
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0] ?? null;
    if (!chosen) return;
    const suffix = chosen.name.toLowerCase();
    if (!(suffix.endsWith(".mp4") || suffix.endsWith(".webm"))) {
      setFile(null);
      setFeedback({ kind: "error", message: "Choose an MP4 or WebM video." });
      event.target.value = "";
      return;
    }
    if (chosen.size > 100 * 1024 * 1024) {
      setFile(null);
      setFeedback({ kind: "error", message: "This file is over the current 100 MB upload limit." });
      event.target.value = "";
      return;
    }
    setFile(chosen);
    setRecordedFile(null);
    setJob(null);
    setSourceName(chosen.name.replace(/\.(mp4|webm)$/i, "").slice(0, 120) || "Uploaded video");
    setFeedback({ kind: "info", message: "Video selected locally. Upload sends it to private temporary storage and creates a job record." });
  }

  async function sendVideo(sourceType: UploadSourceType, inputFile: File) {
    setIsUploading(true);
    setUploadProgress(0);
    setJob(null);
    setFeedback({ kind: "info", message: "Saving source metadata, then uploading the video to private temporary storage…" });
    try {
      const source = await registerCaptureSource({
        name: sourceName.trim() || (sourceType === "phone_camera" ? "Phone camera" : sourceType === "screen_share" ? "Screen recording" : inputFile.name),
        source_type: sourceType,
        device_label: deviceLabel.trim() || (/Android|iPhone|iPad/i.test(navigator.userAgent) ? "Mobile device" : "Browser device"),
      }, accessCode);
      setSources((current) => [source, ...current.filter((entry) => entry.id !== source.id)]);
      const result = await uploadVideo(inputFile, sourceType, source.id, accessCode, setUploadProgress);
      setJob(result);
      setFile(null);
      setRecordedFile(null);
      setFeedback({
        kind: "success",
        message: "Upload saved to private temporary storage and the job metadata is in Supabase. AI analysis is not enabled yet, so no occupancy result has been calculated.",
      });
      await refreshSources();
    } catch (error) {
      setFeedback({ kind: "error", message: error instanceof Error ? error.message : "The upload could not be completed." });
    } finally {
      setIsUploading(false);
    }
  }

  async function registerExternalCamera() {
    if (!externalName.trim()) {
      setFeedback({ kind: "error", message: "Give this camera a name first." });
      return;
    }
    if (!/^rtsps?:\/\//i.test(rtspUrl.trim())) {
      setFeedback({ kind: "error", message: "Enter a valid rtsp:// or rtsps:// camera URL." });
      return;
    }
    setIsRegistering(true);
    setFeedback(null);
    try {
      const source = await registerCaptureSource({
        name: externalName.trim(),
        source_type: "rtsp_camera",
        device_label: "External IP camera",
        rtsp_url: rtspUrl.trim(),
      }, accessCode);
      setSources((current) => [source, ...current.filter((entry) => entry.id !== source.id)]);
      setExternalName("");
      setRtspUrl("");
      setFeedback({ kind: "success", message: "Camera metadata registered. The RTSP URL is encrypted server-side; the actual stream connector/AI worker is still a separate step." });
    } catch (error) {
      setFeedback({ kind: "error", message: error instanceof Error ? error.message : "Could not register this camera." });
    } finally {
      setIsRegistering(false);
    }
  }

  const currentVideo = recordedFile ?? file;
  const typeLabel = (sourceType: string) => ({
    phone_camera: "Phone camera",
    screen_share: "Screen capture",
    uploaded_video: "Video upload",
    rtsp_camera: "IP camera",
  }[sourceType] ?? sourceType);

  if (!authorized) {
    return <main className="capture-app">
      <header className="capture-topbar"><Link href="/" className="capture-back"><ArrowLeft size={16} /> WIMS Dashboard</Link><span className="capture-product-mark"><MapPinMark /> WIMS CAPTURE</span></header>
      <section className="access-layout">
        <div className="capture-kicker"><LockKeyhole size={13} /> DEVICE PAIRING</div>
        <h1>Connect this<br /><span>capture device.</span></h1>
        <p className="capture-lead">Use one shared beta access code from the project owner. This pairs the phone or browser with the WIMS source registry; it is not an account login.</p>
        <form className="access-card" onSubmit={(event) => { event.preventDefault(); void authorize(accessInput); }}>
          <label htmlFor="capture-code">WIMS Capture access code</label>
          <input id="capture-code" autoComplete="one-time-code" value={accessInput} onChange={(event) => setAccessInput(event.target.value)} placeholder="Enter shared access code" />
          <button className="capture-primary" type="submit" disabled={authBusy}>{authBusy ? "Connecting…" : "Connect device"} <ArrowUpRight size={15} /></button>
          {feedback && <FeedbackView feedback={feedback} />}
          <div className="access-note"><ShieldCheck size={14} /> The code is kept in this tab&apos;s session only.</div>
        </form>
        <div className="access-foot">The backend must be deployed and configured before this device can connect.</div>
      </section>
    </main>;
  }

  return <main className="capture-app">
    <header className="capture-topbar">
      <Link href="/" className="capture-back"><ArrowLeft size={16} /> Dashboard</Link>
      <span className="capture-product-mark"><MapPinMark /> WIMS CAPTURE</span>
      <button type="button" className="capture-exit" onClick={() => { stopStream(); window.sessionStorage.removeItem("wims-capture-code"); setAuthorized(false); setAccessCode(""); setAccessInput(""); }}><LockKeyhole size={13} /> Disconnect</button>
    </header>

    <div className="capture-main">
      <section className="capture-intro">
        <div className="capture-kicker"><Smartphone size={13} /> MOBILE SOURCE STUDIO <span className="kicker-dot" /> BETA</div>
        <h1>Bring the space<br /><span>into focus.</span></h1>
        <p>Capture from a phone camera, share a screen where supported, upload a recording, or register another IP camera—all from this app.</p>
        <div className="capture-benefits"><span><LockKeyhole size={13} /> Temporary video storage</span><span><Database size={13} /> Source metadata in Supabase</span></div>
      </section>

      <section className="capture-workbench">
        <div className="source-mode-header">
          <div><div className="workbench-title">Add a video source</div><div className="workbench-subtitle">Choose how WIMS receives the footage.</div></div>
          <span className="secure-tag"><span /> PAIRED DEVICE</span>
        </div>

        <div className="source-mode-grid">
          {modeCards.map((option) => {
            const Icon = option.icon;
            return <button type="button" key={option.id} className={`source-mode-card ${mode === option.id ? "selected" : ""}`} onClick={() => chooseMode(option.id)} disabled={isRecording || isUploading}>
              <span className="mode-icon"><Icon size={19} /></span><span className="mode-title">{option.title}</span><span className="mode-description">{option.description}</span>{mode === option.id && <span className="mode-check"><CheckCircle2 size={15} /></span>}
            </button>;
          })}
        </div>

        <div className="capture-form-grid">
          <div className="capture-field"><label htmlFor="source-name">{mode === "external" ? "Camera name" : "Source name"}</label><input id="source-name" value={mode === "external" ? externalName : mode === "camera" ? cameraName : sourceName} onChange={(event) => mode === "external" ? setExternalName(event.target.value) : mode === "camera" ? setCameraName(event.target.value) : setSourceName(event.target.value)} placeholder="e.g. Library rear camera" /></div>
          <div className="capture-field"><label htmlFor="device-label">Device label <span>(optional)</span></label><input id="device-label" value={deviceLabel} onChange={(event) => setDeviceLabel(event.target.value)} placeholder="e.g. Mayank's phone" /></div>
        </div>

        {mode === "camera" && <div className="capture-mode-body">
          {stream ? <div className="camera-frame live-frame"><video ref={liveVideoRef} autoPlay playsInline muted aria-label="Live phone camera preview" /><div className="frame-badge"><span className="record-dot" /> CAMERA PREVIEW</div></div> : recordedFile ? <VideoPreview file={recordedFile} videoRef={recordedVideoRef} /> : <div className="empty-preview"><span className="large-mode-icon"><Video size={25} /></span><strong>Use this device&apos;s camera</strong><span>On your phone, the rear camera is preferred. Allow camera access when prompted.</span></div>}
          {!stream && !recordedFile && <button type="button" className="capture-primary full" onClick={() => void startCamera()}><Video size={16} /> Open phone camera</button>}
          {stream && !isRecording && <button type="button" className="capture-primary full" onClick={startRecording}><span className="record-dot dark" /> Start recording</button>}
          {isRecording && <button type="button" className="capture-stop full" onClick={stopRecording}><Square size={14} fill="currentColor" /> Stop & prepare clip <span className="record-live">REC</span></button>}
          {recordedFile && !stream && <div className="captured-file"><CheckCircle2 size={15} /><span><strong>Clip ready</strong><small>{recordedFile.name} · {formatBytes(recordedFile.size)}</small></span><button type="button" onClick={() => { setRecordedFile(null); setFeedback(null); }} aria-label="Discard recorded clip"><X size={15} /></button></div>}
          <p className="mode-hint">Recording stays on this device until you press Upload. Maximum capture length: 90 seconds in this prototype.</p>
        </div>}

        {mode === "screen" && <div className="capture-mode-body">
          {stream ? <div className="camera-frame live-frame"><video ref={liveVideoRef} autoPlay playsInline muted aria-label="Shared screen preview" /><div className="frame-badge"><span className="record-dot" /> SCREEN PREVIEW</div></div> : recordedFile ? <VideoPreview file={recordedFile} videoRef={recordedVideoRef} /> : <div className="empty-preview"><span className="large-mode-icon"><MonitorUp size={25} /></span><strong>Capture a screen or playing video</strong><span>Screen sharing varies by mobile browser. If unsupported, record your screen using the phone's built-in recorder and upload that file.</span></div>}
          {!stream && !recordedFile && <button type="button" className="capture-primary full" onClick={() => void startScreenShare()} disabled={!screenShareAvailable}><MonitorUp size={16} /> {screenShareAvailable ? "Choose screen to share" : "Screen share unavailable in this browser"}</button>}
          {stream && !isRecording && <button type="button" className="capture-primary full" onClick={startRecording}><span className="record-dot dark" /> Start recording shared screen</button>}
          {isRecording && <button type="button" className="capture-stop full" onClick={stopRecording}><Square size={14} fill="currentColor" /> Stop & prepare clip <span className="record-live">REC</span></button>}
          {recordedFile && !stream && <div className="captured-file"><CheckCircle2 size={15} /><span><strong>Screen clip ready</strong><small>{recordedFile.name} · {formatBytes(recordedFile.size)}</small></span><button type="button" onClick={() => { setRecordedFile(null); setFeedback(null); }} aria-label="Discard screen clip"><X size={15} /></button></div>}
          <p className="mode-hint">Screen audio capture is not enabled in this prototype. Use a sample video without needing audio.</p>
        </div>}

        {mode === "file" && <div className="capture-mode-body">
          <button type="button" className="file-drop" onClick={() => fileInputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const dropped = event.dataTransfer.files?.[0]; if (dropped) { const fakeEvent = { target: { files: [dropped], value: "" } } as unknown as ChangeEvent<HTMLInputElement>; onFileChange(fakeEvent); } }}>
            <span className="large-mode-icon"><CloudUpload size={25} /></span><strong>{file ? file.name : "Choose or drop a video file"}</strong><span>{file ? formatBytes(file.size) + " · Ready for upload" : "MP4 or WebM · Up to 100 MB per file"}</span><em>Browse files</em>
          </button>
          <input ref={fileInputRef} className="sr-only" type="file" accept=".mp4,.webm,video/mp4,video/webm" onChange={onFileChange} />
          {file && <div className="captured-file"><FileVideo2 size={15} /><span><strong>File selected</strong><small>{file.name} · {formatBytes(file.size)}</small></span><button type="button" onClick={() => { setFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }} aria-label="Remove selected video"><X size={15} /></button></div>}
          <p className="mode-hint">The browser sends the chosen file directly to the WIMS API over HTTPS. It is stored in private temporary storage and expires automatically if not processed.</p>
        </div>}

        {mode === "external" && <div className="capture-mode-body">
          <div className="external-info"><Radio size={19} /><div><strong>Register an IP camera</strong><span>Use the RTSP / RTSPS URL supplied by the camera administrator. URLs are encrypted by the API before being saved; the browser never receives them back from the source list.</span></div></div>
          <div className="capture-field"><label htmlFor="rtsp-url">RTSP / RTSPS stream URL</label><input id="rtsp-url" type="password" autoComplete="off" value={rtspUrl} onChange={(event) => setRtspUrl(event.target.value)} placeholder="rtsp://camera-host:554/…" /><small>Use credentials only for a camera you are authorized to access. They are sent over HTTPS to the WIMS backend.</small></div>
          <button type="button" className="capture-primary full" onClick={() => void registerExternalCamera()} disabled={isRegistering}><Wifi size={16} /> {isRegistering ? "Saving camera metadata…" : "Register camera"}</button>
          <p className="mode-hint">This step registers its metadata and encrypted URL. Connecting to the stream and analysing it requires the RTSP worker, which is not enabled yet.</p>
        </div>}

        {(mode === "file" && file || (mode === "camera" || mode === "screen") && recordedFile) && <button type="button" className="capture-primary full upload-action" onClick={() => currentVideo && void sendVideo(mode === "camera" ? "phone_camera" : mode === "screen" ? "screen_share" : "uploaded_video", currentVideo)} disabled={isUploading || !currentVideo}>
          {isUploading ? <><RefreshCw size={15} className="spinning" /> Uploading {uploadProgress}%</> : <><CloudUpload size={16} /> Upload to WIMS <ArrowUpRight size={14} /></>}
        </button>}
        {isUploading && <div className="upload-progress" role="progressbar" aria-valuenow={uploadProgress} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${uploadProgress}%` }} /></div>}

        {feedback && <FeedbackView feedback={feedback} />}
        {job && <div className="job-result"><div className="job-result-icon"><CheckCircle2 size={17} /></div><div className="job-result-main"><strong>Upload received · Job {job.id.slice(0, 8)}</strong><span>{job.original_filename} · {formatBytes(job.size_bytes)} · status: {job.status}</span><small>Metadata saved. AI detection is not active yet, so this is not an occupancy result.</small></div><button type="button" className="job-copy" onClick={() => { void navigator.clipboard?.writeText(job.id); setFeedback({ kind: "success", message: "Job ID copied." }); }}>Copy ID</button></div>}
      </section>

      <section className="registered-sources">
        <div className="registered-header"><div><div className="workbench-title">Registered sources</div><div className="workbench-subtitle">Metadata saved through this capture app.</div></div><button type="button" className="refresh-button" onClick={() => void refreshSources()}><RefreshCw size={13} /> Refresh</button></div>
        {sources.length ? <div className="source-list">{sources.map((source) => <div className="source-row" key={source.id}><span className={`source-type-icon ${source.source_type === "rtsp_camera" ? "violet" : ""}`}>{source.source_type === "rtsp_camera" ? <Radio size={16} /> : source.source_type === "phone_camera" ? <Video size={16} /> : source.source_type === "screen_share" ? <MonitorUp size={16} /> : <FileVideo2 size={16} />}</span><span className="source-row-main"><strong>{source.name}</strong><small>{typeLabel(source.source_type)} · {source.device_label || "Device not labelled"}</small></span><span className="source-status">{source.status}</span></div>)}</div> : <div className="empty-sources"><Database size={17} /><span>No sources registered yet. Add a phone, upload, or camera source above.</span></div>}
        <div className="source-security-note"><LockKeyhole size={13} /> Private source registry. RTSP addresses are not displayed here.</div>
      </section>

      <footer className="capture-footer"><span><ShieldCheck size={14} /> Use footage you have permission to capture.</span><Link href="/">Return to WIMS dashboard <ArrowUpRight size={13} /></Link></footer>
      <p className="capture-build-note"><HardDrive size={12} /> Current stage: secure source metadata + temporary upload. AI inference and continuous live streaming are not yet enabled.</p>
    </div>
  </main>;
}

function MapPinMark() {
  return <span className="mini-brand-glyph"><span /><span /><span /></span>;
}

function FeedbackView({ feedback }: { feedback: Feedback }) {
  const Icon = feedback.kind === "success" ? CheckCircle2 : feedback.kind === "error" ? CircleAlert : Wifi;
  return <div className={`capture-feedback ${feedback.kind}`} role="status"><Icon size={15} /><span>{feedback.message}</span></div>;
}

function VideoPreview({ file, videoRef }: { file: File; videoRef: React.RefObject<HTMLVideoElement | null> }) {
  return <div className="camera-frame recorded-frame"><video ref={videoRef} controls playsInline aria-label="Captured video review" /><div className="frame-badge"><CheckCircle2 size={12} /> REVIEW CLIP</div></div>;
}
