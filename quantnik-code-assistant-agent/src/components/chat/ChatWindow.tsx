import React, { useCallback, useEffect, useRef } from "react";
import { useDrag } from "../../hooks/useDrag";
import { useResize } from "../../hooks/useResize";
import ChatLog from "./ChatLog";
import ChatInput from "./ChatInput";
import { useChat } from "../../hooks/useChat";
import { chimeSound, closeSound, dragLoopSound, dragStopSound, openSound, resizeLoopSound, resizeStopSound } from "../../lib/sounds";

type ModelOption = { label: string; value: string };
type LevelSetting = "" | "high" | "medium" | "low";
type RepoLockMode = "" | "new" | "existing";
type RepoFolderMode = "" | "new" | "existing";

type RepoLockResponse = {
  mode: Exclude<RepoLockMode, "">;
  folderMode: Exclude<RepoFolderMode, "">;
  localPath: string;
  branchName: string;
  requiresConfirmation?: boolean;
  warning?: string;
  inSync?: boolean;
};

const normalizeLevel = (value: string | null): LevelSetting => {
  const normalized = (value ?? "").trim().toLowerCase();
  return normalized === "high" || normalized === "medium" || normalized === "low" ? normalized : "";
};

const readSettingsFromUrl = () => {
  if (typeof window === "undefined") {
    return { repo: "", model: "", autonomy: "" as LevelSetting, reasoning: "" as LevelSetting };
  }
  const params = new URLSearchParams(window.location.search);
  return {
    repo: params.get("repo")?.trim() ?? "",
    model: params.get("model")?.trim() ?? "",
    autonomy: normalizeLevel(params.get("autonomy")),
    reasoning: normalizeLevel(params.get("reasoning"))
  };
};

export default function ChatWindow() {
  const initialSettings = React.useMemo(() => readSettingsFromUrl(), []);
  const modalRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = React.useState(true);
  const [maximized, setMaximized] = React.useState(false);
  const [repo, setRepo] = React.useState(initialSettings.repo);
  const [models, setModels] = React.useState<ModelOption[]>([]);
  const [model, setModel] = React.useState(initialSettings.model);
  const [autonomy, setAutonomy] = React.useState<LevelSetting>(initialSettings.autonomy);
  const [reasoning, setReasoning] = React.useState<LevelSetting>(initialSettings.reasoning);
  const [repoLocked, setRepoLocked] = React.useState(false);
  const [lockMode, setLockMode] = React.useState<RepoLockMode>("");
  const [lockFolderMode, setLockFolderMode] = React.useState<RepoFolderMode>("");
  const [lockFolderName, setLockFolderName] = React.useState("");
  const [lockBranchName, setLockBranchName] = React.useState("");
  const [lockInFlight, setLockInFlight] = React.useState(false);
  const [lockError, setLockError] = React.useState("");
  const [lockWarning, setLockWarning] = React.useState("");
  const [awaitingOverwriteConfirm, setAwaitingOverwriteConfirm] = React.useState(false);
  const [lockDetails, setLockDetails] = React.useState<RepoLockResponse | null>(null);
  const [syncInFlight, setSyncInFlight] = React.useState<"" | "pull" | "push">("");
  const [syncMessage, setSyncMessage] = React.useState("");
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [showAwaitingAlt, setShowAwaitingAlt] = React.useState(false);
  const { messages, commandOutput, loading, spinnerText, chatStatus, sendMessage } = useChat({
    onComplete: (timedOut) => {
      if (!timedOut) chimeSound.play();
    }
  });

  const statusByState = {
    awaiting: "Awaiting Command",
    executing: "Executing Command",
    complete: "Command Execution Complete",
    attention: "Attention"
  } as const;

  const isTerminalStatus = chatStatus === "complete" || chatStatus === "attention";
  const statusDisplay = isTerminalStatus && showAwaitingAlt ? "awaiting" : chatStatus;

  useEffect(() => {
    if (!isTerminalStatus) {
      setShowAwaitingAlt(false);
      return;
    }

    setShowAwaitingAlt(false);
    const id = window.setInterval(() => {
      setShowAwaitingAlt((prev) => !prev);
    }, 1200);

    return () => window.clearInterval(id);
  }, [isTerminalStatus, chatStatus]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/models")
      .then((res) => (res.ok ? res.json() : { models: [] }))
      .then((data) => {
        if (cancelled) return;
        const list = Array.isArray(data?.models)
          ? data.models
              .map((item: any) => {
                const label = typeof item?.label === "string" ? item.label : "";
                const value = typeof item?.value === "string" ? item.value : "";
                if (!label || !value) return null;
                return { label, value };
              })
              .filter((item: ModelOption | null): item is ModelOption => Boolean(item))
          : [];
        setModels(list);
      })
      .catch((err) => {
        console.error("failed to load model options", err);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (visible) {
      openSound.play();
    }
  }, [visible]);

  useEffect(() => {
    if (!settingsOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (settingsRef.current?.contains(target)) return;
      setSettingsOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [settingsOpen]);

  useEffect(() => () => dragLoopSound.stop(), []);

  useEffect(() => {
    if (!visible) return;
    const el = textareaRef.current;
    if (el) {
      el.focus();
    }
  }, [visible]);

  useDrag(modalRef, {
    onDragMoveStart: () => {
      if (!visible || maximized) return;
      dragLoopSound.play();
    },
    onDragMoveStop: () => {
      dragLoopSound.stop();
    },
    onDragEnd: () => {
      dragLoopSound.stop();
      dragStopSound.play();
    }
  });

  useResize(modalRef, {
    onResizeStart: () => {
      if (!visible || maximized) return;
      resizeLoopSound.play();
    },
    onResizeEnd: () => {
      resizeLoopSound.stop();
      resizeStopSound.play();
    }
  });

  useEffect(() => {
    if (!visible) {
      dragLoopSound.stop();
    }
  }, [visible]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const setOrDelete = (key: string, value: string) => {
      if (value) {
        url.searchParams.set(key, value);
      } else {
        url.searchParams.delete(key);
      }
    };
    setOrDelete("repo", repo.trim());
    setOrDelete("model", model.trim());
    setOrDelete("autonomy", autonomy);
    setOrDelete("reasoning", reasoning);
    window.history.replaceState({}, "", url.toString());
  }, [repo, model, autonomy, reasoning]);

  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    const id = requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
    return () => cancelAnimationFrame(id);
  }, [messages, loading, maximized]);

  const autoGrow = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const lineHeight = 24;
    const maxHeight = lineHeight * 5;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, []);

  // sendMessage now provided by useChat

  const handleSubmit = useCallback(
    (event: React.FormEvent) => {
      event.preventDefault();
      if (!repoLocked) return;
      const value = textareaRef.current?.value.trim() ?? "";
      if (!value) return;
      if (textareaRef.current) {
        textareaRef.current.value = "";
        autoGrow();
      }
      sendMessage(value, repo, model, autonomy, reasoning);
    },
    [autonomy, autoGrow, model, reasoning, repo, repoLocked, sendMessage]
  );

  const handleLockRepo = useCallback(async (overwriteExisting = false) => {
    if (lockInFlight) return;
    if (!lockFolderName.trim()) {
      setLockError("Provide the local folder name to create at project root.");
      return;
    }
    if (!lockFolderMode) {
      setLockError("Specify whether the local folder is new or existing.");
      return;
    }
    if (!lockMode) {
      setLockError("Choose whether to work with a new branch or existing branch.");
      return;
    }
    if (!lockBranchName.trim()) {
      setLockError(lockMode === "new" ? "Provide the new branch name to create." : "Provide the existing branch name to replicate.");
      return;
    }

    setLockError("");
    setLockWarning("");
    setSyncMessage("");
    setLockInFlight(true);
    try {
      const response = await fetch("/api/repo/lock", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          mode: lockMode,
          folderMode: lockFolderMode,
          folderName: lockFolderName.trim(),
          branchName: lockBranchName.trim(),
          overwriteExisting
        })
      });
      const payload = (await response.json().catch(() => null)) as (RepoLockResponse & { error?: string; details?: string }) | null;
      if (!response.ok || !payload) {
        throw new Error(payload?.details || payload?.error || `Request failed with HTTP ${response.status}`);
      }

      if (payload.requiresConfirmation) {
        setAwaitingOverwriteConfirm(true);
        setLockWarning(payload.warning ?? "Local folder differs from remote branch. Confirm overwrite to continue.");
        return;
      }

      setLockDetails({ mode: payload.mode, folderMode: payload.folderMode, localPath: payload.localPath, branchName: payload.branchName });
      setRepo(payload.localPath);
      setRepoLocked(true);
      setAwaitingOverwriteConfirm(false);
      setLockWarning("");
      setSettingsOpen(false);
      setSyncMessage(payload.inSync ? `Local workspace already in sync at ${payload.localPath}.` : `Local workspace ready at ${payload.localPath}.`);
    } catch (err) {
      setLockError(err instanceof Error ? err.message : String(err));
      setRepoLocked(false);
    } finally {
      setLockInFlight(false);
    }
  }, [lockBranchName, lockFolderMode, lockFolderName, lockInFlight, lockMode]);

  const handleSyncRepo = useCallback(
    async (direction: "pull" | "push") => {
      if (!lockDetails || syncInFlight) return;
      setSyncInFlight(direction);
      setSyncMessage("");
      try {
        const response = await fetch("/api/repo/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({
            direction,
            localPath: lockDetails.localPath,
            branchName: lockDetails.branchName
          })
        });
        const payload = (await response.json().catch(() => null)) as { error?: string; details?: string } | null;
        if (!response.ok) {
          throw new Error(payload?.details || payload?.error || `Request failed with HTTP ${response.status}`);
        }
        setSyncMessage(direction === "pull" ? "Pulled latest changes from remote branch." : "Pushed local changes to remote branch.");
      } catch (err) {
        setSyncMessage(err instanceof Error ? err.message : String(err));
      } finally {
        setSyncInFlight("");
      }
    },
    [lockDetails, syncInFlight]
  );

  return (
    <>
      {!visible && (
        <button
          type="button"
          className="chat-open-btn"
          onClick={() => setVisible(true)}
        >
          open chat
        </button>
      )}
      <div
        ref={modalRef}
        className={`chat-modal ${visible ? "visible" : ""} ${maximized ? "maximized" : ""}`}
        style={maximized ? undefined : { left: "50%", top: "50%", transform: "translate(-50%, -50%)" }}
        role="dialog"
        aria-modal="true"
        aria-label="Chat with repository"
      >
        <div className="chat-titlebar">
          <div className="chat-title-main">
            <span className="chat-brand-icon" aria-hidden="true">
              ✦
            </span>
            <span className="chat-title-text">QUANTNIK Coding Assistant</span>
          </div>
          <div className="chat-title-actions">
            <span
              className={`chat-status-pill chat-status-pill-${statusDisplay}${isTerminalStatus ? " chat-status-pill-alternating" : ""}`}
            >
              {statusByState[statusDisplay]}
            </span>
            <button
              type="button"
              className={`chat-settings-btn${settingsOpen ? " active" : ""}`}
              aria-label="Open chat settings"
              aria-expanded={settingsOpen}
              onMouseDown={(event) => event.stopPropagation()}
              onClick={() => setSettingsOpen((prev) => !prev)}
            >
              ⚙
            </button>
            <button
              type="button"
              className="chat-maximize-btn"
              onClick={() => setMaximized((prev) => !prev)}
              aria-label={maximized ? "restore" : "maximize"}
            >
              {maximized ? "↙" : "↗"}
            </button>
            <button
              type="button"
              className="chat-close-btn"
              onClick={() => {
                closeSound.play();
                setMaximized(false);
                setVisible(false);
              }}
            >
              ×
            </button>
          </div>
        </div>
        {settingsOpen && (
          <div
            ref={settingsRef}
            className="chat-settings-popup"
            role="dialog"
            aria-label="Chat settings"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="chat-settings-popup-header">
              <div>
                <div className="chat-settings-popup-title">Settings</div>
                <div className="chat-settings-popup-subtitle">Configure command defaults</div>
              </div>
              <button
                type="button"
                className="chat-settings-close-btn"
                aria-label="Close chat settings"
                onClick={() => setSettingsOpen(false)}
              >
                ×
              </button>
            </div>
            <div className="chat-settings-popup-content">
              <label className="chat-settings-field">
                <span>Repository Path</span>
                <input
                  type="text"
                  className="chat-repo-input"
                  value={repo}
                  disabled={repoLocked}
                  onChange={(event) => setRepo(event.target.value)}
                  placeholder={repoLocked ? "Repository path is locked by session setup" : "Repository path (optional)"}
                  aria-label="Repository path"
                />
                {repoLocked && <small className="chat-settings-hint">Repo path is locked for this session.</small>}
              </label>

              <label className="chat-settings-field">
                <span>Default model</span>
                <select
                  className="chat-model-select"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  aria-label="Model"
                >
                  <option value="">Default model (from env)</option>
                  {models.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>

              <div className="chat-settings-field-grid">
                <label className="chat-settings-field">
                  <span>Autonomy default</span>
                  <select
                    className="chat-autonomy-select"
                    value={autonomy}
                    onChange={(event) => setAutonomy(normalizeLevel(event.target.value))}
                    aria-label="Autonomy level"
                  >
                    <option value="">Default</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </label>

                <label className="chat-settings-field">
                  <span>Reasoning default</span>
                  <select
                    className="chat-reasoning-select"
                    value={reasoning}
                    onChange={(event) => setReasoning(normalizeLevel(event.target.value))}
                    aria-label="Reasoning level"
                  >
                    <option value="">Default</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </label>
              </div>
            </div>
          </div>
        )}
        <div className="chat-body">
          {!repoLocked ? (
            <div className="chat-lock-card" role="region" aria-label="Repository lock setup">
              <div className="chat-lock-title-row">
                <div>
                  <div className="chat-lock-title">Project Configuration</div>
                  <div className="chat-lock-subtitle">Please configure repository lock details to begin this session.</div>
                </div>
              </div>

              <div className="chat-lock-step">
                <div className="chat-lock-question">Enter local folder name at root:</div>
                <label className="chat-lock-field">
                  <input
                    type="text"
                    value={lockFolderName}
                    onChange={(event) => setLockFolderName(event.target.value)}
                    placeholder="example: feature-workspace"
                  />
                </label>
              </div>

              <div className="chat-lock-step">
                <div className="chat-lock-question">Is this local folder new or existing?</div>
                <div className="chat-lock-mode-buttons">
                  <button
                    type="button"
                    className={`chat-lock-mode-btn${lockFolderMode === "new" ? " active" : ""}`}
                    onClick={() => {
                      setLockFolderMode("new");
                      setAwaitingOverwriteConfirm(false);
                      setLockWarning("");
                    }}
                  >
                    New folder
                  </button>
                  <button
                    type="button"
                    className={`chat-lock-mode-btn${lockFolderMode === "existing" ? " active" : ""}`}
                    onClick={() => setLockFolderMode("existing")}
                  >
                    Existing folder
                  </button>
                </div>
              </div>

              <div className="chat-lock-step">
                <div className="chat-lock-question">Will you work with a new branch or an existing branch?</div>
                <div className="chat-lock-mode-buttons">
                  <button
                    type="button"
                    className={`chat-lock-mode-btn${lockMode === "new" ? " active" : ""}`}
                    onClick={() => setLockMode("new")}
                  >
                    New branch
                  </button>
                  <button
                    type="button"
                    className={`chat-lock-mode-btn${lockMode === "existing" ? " active" : ""}`}
                    onClick={() => setLockMode("existing")}
                  >
                    Existing branch
                  </button>
                </div>
              </div>

              <div className="chat-lock-grid">
                <label className="chat-lock-field">
                  <span>{lockMode === "existing" ? "Existing branch name" : "New branch name"}</span>
                  <input
                    type="text"
                    value={lockBranchName}
                    onChange={(event) => setLockBranchName(event.target.value)}
                    placeholder={lockMode === "existing" ? "example: release/1.2.0" : "example: feature/repo-lock"}
                  />
                </label>
              </div>

              {lockError && <div className="chat-lock-error">{lockError}</div>}
              {lockWarning && <div className="chat-lock-warning">{lockWarning}</div>}

              {awaitingOverwriteConfirm && lockFolderMode === "existing" ? (
                <button
                  type="button"
                  className="chat-lock-proceed-btn"
                  disabled={lockInFlight}
                  onClick={() => handleLockRepo(true)}
                >
                  {lockInFlight ? "Overwriting..." : "Confirm overwrite and continue"}
                </button>
              ) : null}

              <button type="button" className="chat-lock-proceed-btn" disabled={lockInFlight} onClick={() => handleLockRepo()}>
                {lockInFlight ? "Configuring..." : "Proceed"}
              </button>
            </div>
          ) : (
            <div className="chat-lock-status-bar" role="status" aria-live="polite">
              <div>
                <div className="chat-lock-status-title">Repository locked for this session</div>
                <div className="chat-lock-status-details">
                  {lockDetails?.mode === "new" ? "New branch" : "Existing branch"}: <strong>{lockDetails?.branchName}</strong> at <strong>{lockDetails?.localPath}</strong>
                </div>
              </div>
              <div className="chat-lock-status-actions">
                <button type="button" onClick={() => handleSyncRepo("pull")} disabled={syncInFlight !== ""}>
                  {syncInFlight === "pull" ? "Pulling..." : "Pull"}
                </button>
                <button type="button" onClick={() => handleSyncRepo("push")} disabled={syncInFlight !== ""}>
                  {syncInFlight === "push" ? "Pushing..." : "Push"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setRepoLocked(false);
                    setLockDetails(null);
                    setRepo("");
                    setLockWarning("");
                    setAwaitingOverwriteConfirm(false);
                    setSyncMessage("");
                  }}
                >
                  Unlock
                </button>
              </div>
              {syncMessage && <div className="chat-lock-sync-message">{syncMessage}</div>}
            </div>
          )}

          <ChatLog logRef={logRef} messages={messages} />
          <ChatInput
            textareaRef={textareaRef}
            onSubmit={handleSubmit}
            autoGrow={autoGrow}
            disabled={!repoLocked}
            loading={loading}
            spinnerText={spinnerText}
            commandOutput={commandOutput}
          />
        </div>
        <div className="chat-resize-corner" aria-hidden="true">
          ◢
        </div>
      </div>
    </>
  );
}
