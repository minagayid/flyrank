"use client";

import { useEffect, useRef, useState } from "react";

type ButtonState = "idle" | "loading" | "success" | "error";

export type StatefulButtonProps = {
  action: (signal: AbortSignal) => Promise<void>;
  disabled?: boolean;
  idleLabel?: string;
  loadingLabel?: string;
  successLabel?: string;
  errorLabel?: string;
};

const feedbackDuration = 1600;

export function StatefulButton({
  action,
  disabled = false,
  idleLabel = "Continue",
  loadingLabel = "Working",
  successLabel = "Done",
  errorLabel = "Try again",
}: StatefulButtonProps) {
  const [state, setState] = useState<ButtonState>("idle");
  const [announcement, setAnnouncement] = useState("Ready.");
  const controllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      runIdRef.current += 1;
      controllerRef.current?.abort();
      if (resetTimerRef.current !== null) {
        clearTimeout(resetTimerRef.current);
      }
    };
  }, []);

  function clearResetTimer() {
    if (resetTimerRef.current !== null) {
      clearTimeout(resetTimerRef.current);
      resetTimerRef.current = null;
    }
  }

  function cancelAction() {
    runIdRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    clearResetTimer();
    setState("idle");
    setAnnouncement("Action cancelled. Ready for another try.");
  }

  function showFeedback(nextState: "success" | "error", runId: number) {
    if (runId !== runIdRef.current) return;

    setState(nextState);
    setAnnouncement(
      nextState === "success"
        ? `${successLabel}.`
        : `${errorLabel}. You can try again when ready.`,
    );

    resetTimerRef.current = setTimeout(() => {
      if (runId !== runIdRef.current) return;
      setState("idle");
      setAnnouncement("Ready.");
      resetTimerRef.current = null;
    }, feedbackDuration);
  }

  async function handlePress() {
    if (disabled) return;
    if (state === "loading") {
      cancelAction();
      return;
    }

    clearResetTimer();
    const controller = new AbortController();
    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    controllerRef.current = controller;
    setState("loading");
    setAnnouncement(`${loadingLabel}. Activate the button again to cancel.`);

    try {
      await action(controller.signal);
      showFeedback("success", runId);
    } catch {
      if (!controller.signal.aborted) {
        showFeedback("error", runId);
      }
    } finally {
      if (runId === runIdRef.current) {
        controllerRef.current = null;
      }
    }
  }

  const labels: Record<ButtonState, string> = {
    idle: idleLabel,
    loading: `Cancel ${loadingLabel.toLowerCase()}`,
    success: successLabel,
    error: errorLabel,
  };
  const tones: Record<ButtonState, string> = {
    idle: "bg-[#183744] hover:bg-[#234b55]",
    loading: "bg-[#234b55]",
    success: "bg-[#205e4d]",
    error: "bg-[#8c392f]",
  };

  return (
    <span className="inline-flex flex-col items-start gap-2">
      <button
        type="button"
        disabled={disabled}
        aria-busy={state === "loading"}
        onClick={handlePress}
        className={`group inline-flex min-h-12 items-center justify-center gap-3 rounded-xl px-5 py-3 text-sm font-semibold text-white shadow-[0_8px_18px_-12px_rgba(24,55,68,0.9)] transition-[transform,opacity] duration-200 ease-out hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.99] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#a94734] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:hover:translate-y-0 disabled:active:scale-100 motion-reduce:transition-none motion-reduce:hover:translate-y-0 motion-reduce:active:scale-100 ${tones[state]}`}
      >
        <span aria-hidden="true" className="relative h-4 w-4 shrink-0">
          <svg
            viewBox="0 0 20 20"
            fill="none"
            className={`absolute inset-0 h-4 w-4 origin-center transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none motion-reduce:group-hover:translate-x-0 motion-reduce:group-focus-visible:translate-x-0 ${state === "idle" ? "scale-100 opacity-100 group-hover:translate-x-0.5 group-focus-visible:translate-x-0.5" : "scale-75 opacity-0"}`}
          >
            <path d="M3.5 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span
            className={`absolute inset-0 rounded-full border-2 border-white/35 border-t-white transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none ${state === "loading" ? "scale-100 opacity-100" : "scale-75 opacity-0"} ${state === "loading" ? "animate-spin motion-reduce:animate-none" : ""}`}
          />
          <svg
            viewBox="0 0 20 20"
            fill="none"
            className={`absolute inset-0 h-4 w-4 transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none ${state === "success" ? "scale-100 opacity-100" : "scale-75 opacity-0"}`}
          >
            <path d="m4.5 10.5 3.4 3.4 7.6-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <svg
            viewBox="0 0 20 20"
            fill="none"
            className={`absolute inset-0 h-4 w-4 transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none ${state === "error" ? "scale-100 opacity-100" : "scale-75 opacity-0"}`}
          >
            <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.8" />
            <path d="M10 6.5v4.2m0 2.8h.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </span>
        <span>{labels[state]}</span>
      </button>
      <span role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {announcement}
      </span>
    </span>
  );
}
