"use client";

import { useState } from "react";
import { StatefulButton } from "@/components/practice/stateful-button";

type DemoOutcome = "success" | "error";

function waitForRequest(outcome: DemoOutcome, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const finish = () => {
      signal.removeEventListener("abort", cancel);
      if (outcome === "success") {
        resolve();
      } else {
        reject(new Error("The sample service returned an error."));
      }
    };

    const timer = window.setTimeout(finish, 720);
    const cancel = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Request cancelled.", "AbortError"));
    };

    if (signal.aborted) {
      cancel();
    } else {
      signal.addEventListener("abort", cancel, { once: true });
    }
  });
}

const stateNotes = [
  { name: "Idle", note: "Ready for the next action.", mark: "bg-[#183744]" },
  { name: "Hover / focus", note: "A lift and a clear keyboard ring.", mark: "bg-[#3e7771]" },
  { name: "Loading", note: "Progress is announced; activate again to cancel.", mark: "bg-[#426f83]" },
  { name: "Success", note: "A checkmark confirms the result.", mark: "bg-[#205e4d]" },
  { name: "Error", note: "The action can be retried immediately.", mark: "bg-[#8c392f]" },
  { name: "Disabled", note: "Native disabled behavior prevents activation.", mark: "bg-[#aebbbd]" },
];

export default function MotionPlayground() {
  const [outcome, setOutcome] = useState<DemoOutcome>("success");

  return (
    <main className="min-h-screen bg-[#edf2f2] text-[#17323c]">
      <div className="mx-auto w-full max-w-6xl px-5 py-7 sm:px-8 sm:py-10 lg:px-12 lg:py-14">
        <header className="flex items-center gap-3">
          <span aria-hidden="true" className="grid h-10 w-10 place-items-center rounded-[13px] bg-[#183744] text-sm font-bold text-[#e3f1ec]">
            M
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight">Motion study</p>
            <p className="mt-1 text-xs text-[#536a67]">Interface practice · 01</p>
          </div>
        </header>

        <section className="mt-14 max-w-3xl sm:mt-20">
          <p className="text-sm font-medium text-[#3e7771]">Buttons with a brain</p>
          <h1 className="mt-3 max-w-2xl text-4xl font-semibold leading-[1.08] tracking-[-0.04em] sm:text-6xl">
            A button should answer back.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-[#52686f] sm:text-lg">
            Give each click a clear outcome. The small shift, wait, and confirmation make an action feel dependable.
          </p>
        </section>

        <div className="mt-10 grid gap-5 lg:mt-14 lg:grid-cols-[minmax(0,1.55fr)_minmax(275px,0.8fr)]">
          <section aria-labelledby="demo-heading" className="rounded-[24px] border border-[#d5e0df] bg-[#fbfcfa] p-6 shadow-[0_24px_70px_-54px_rgba(23,50,60,0.65)] sm:p-9">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#dce5e3] pb-6">
              <div>
                <h2 id="demo-heading" className="text-xl font-semibold tracking-[-0.02em]">Try the response</h2>
                <p className="mt-2 max-w-md text-sm leading-6 text-[#536a67]">
                  Pick a fixed result, then run the request. No random outcomes.
                </p>
              </div>
              <span className="rounded-full border border-[#d8e3e0] px-3 py-1.5 text-xs font-medium text-[#536a67]">720 ms sample</span>
            </div>

            <fieldset className="mt-7">
              <legend className="text-sm font-medium">Choose the result</legend>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  aria-pressed={outcome === "success"}
                  onClick={() => setOutcome("success")}
                  className={`min-h-10 rounded-lg border px-4 text-sm font-medium transition-[transform,opacity] duration-150 ease-out hover:-translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#a94734] motion-reduce:transition-none motion-reduce:hover:translate-y-0 ${outcome === "success" ? "border-[#3e7771] bg-[#e8f2ee] text-[#245b51]" : "border-[#d5e0df] bg-white text-[#52686f] hover:bg-[#f3f7f5]"}`}
                >
                  Always succeeds
                </button>
                <button
                  type="button"
                  aria-pressed={outcome === "error"}
                  onClick={() => setOutcome("error")}
                  className={`min-h-10 rounded-lg border px-4 text-sm font-medium transition-[transform,opacity] duration-150 ease-out hover:-translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#a94734] motion-reduce:transition-none motion-reduce:hover:translate-y-0 ${outcome === "error" ? "border-[#b95a45] bg-[#f8ece8] text-[#8c392f]" : "border-[#d5e0df] bg-white text-[#52686f] hover:bg-[#f3f7f5]"}`}
                >
                  Always fails
                </button>
              </div>
            </fieldset>

            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
              <StatefulButton
                action={(signal) => waitForRequest(outcome, signal)}
                idleLabel="Send response"
                loadingLabel="Sending"
                successLabel="Response sent"
                errorLabel="Send failed"
              />
              <p className="max-w-xs text-sm leading-6 text-[#536a67]">
                While it works, activate the button again to cancel and return to ready.
              </p>
            </div>

            <div className="mt-9 flex flex-col gap-2 border-t border-[#dce5e3] pt-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium">Disabled example</p>
                <p className="mt-1 text-xs leading-5 text-[#536a67]">Unavailable actions stay visibly quiet.</p>
              </div>
              <StatefulButton
                action={async () => undefined}
                idleLabel="Not available"
                disabled
              />
            </div>
          </section>

          <aside className="rounded-[24px] border border-[#d5e0df] bg-[#e5ecea] p-6 sm:p-8">
            <h2 className="text-lg font-semibold tracking-[-0.02em]">State key</h2>
            <p className="mt-2 text-sm leading-6 text-[#536a67]">Each state changes both the message and the cue.</p>
            <ul className="mt-6 divide-y divide-[#cfdad8]">
              {stateNotes.map((item) => (
                <li key={item.name} className="flex gap-3 py-3.5 first:pt-0 last:pb-0">
                  <span aria-hidden="true" className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${item.mark}`} />
                  <div>
                    <p className="text-sm font-medium">{item.name}</p>
                    <p className="mt-1 text-xs leading-5 text-[#536a67]">{item.note}</p>
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-7 border-t border-[#cfdad8] pt-5">
              <p className="text-sm font-medium">Motion follows the action</p>
              <p className="mt-2 text-sm leading-6 text-[#536a67]">
                A short lift marks hover and focus. The icon changes with a quick scale and fade; reduced-motion settings remove those transitions and the spinner rotation.
              </p>
            </div>
          </aside>
        </div>

        <footer className="mt-8 flex flex-col gap-2 border-t border-[#d5e0df] pt-5 text-xs leading-5 text-[#536a67] sm:flex-row sm:items-center sm:justify-between">
          <p>Keyboard: Tab to a control; use Enter or Space to activate it.</p>
          <p>Feedback remains visible for 1.6 seconds.</p>
        </footer>
      </div>
    </main>
  );
}
