"use client";

import {
  type KeyboardEvent,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { createPortal } from "react-dom";

const tabs = [
  {
    label: "Overview",
    title: "A useful first pass",
    body: "A small summary gives people enough context to choose their next step without making them scan every detail first.",
  },
  {
    label: "Evidence",
    title: "Show the reasons",
    body: "Pair each recommendation with the words or facts that support it. Clear evidence makes a suggestion easier to review and correct.",
  },
  {
    label: "History",
    title: "Keep a readable trail",
    body: "A short activity history helps a team understand what changed and pick up work after an interruption.",
  },
];

const focusableSelector = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type=hidden])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "iframe",
  "object",
  "embed",
  "[contenteditable='true']",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function getFocusableElements(container: HTMLElement) {
  return Array.from(container.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (element) =>
      !element.hidden &&
      element.getAttribute("aria-hidden") !== "true" &&
      element.getClientRects().length > 0 &&
      window.getComputedStyle(element).visibility !== "hidden",
  );
}

function ModalDialog() {
  const id = useId().replaceAll(":", "");
  const [open, setOpen] = useState(false);
  const [portalRoot, setPortalRoot] = useState<HTMLElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  function showDialog() {
    openerRef.current = triggerRef.current;

    if (!portalRoot) {
      const root = document.createElement("div");
      root.dataset.modalPortal = "accessible-widgets";
      document.body.append(root);
      setPortalRoot(root);
    }

    setOpen(true);
  }

  useLayoutEffect(() => {
    if (!open || !portalRoot || !dialogRef.current) return;

    const originalInertState = new Map<HTMLElement, boolean>();
    const fallbackFocusTarget = triggerRef.current;
    const backgroundElements = Array.from(document.body.children).filter(
      (element): element is HTMLElement =>
        element instanceof HTMLElement && element !== portalRoot,
    );
    const previousOverflow = document.body.style.overflow;

    for (const element of backgroundElements) {
      originalInertState.set(element, element.inert);
      element.inert = true;
    }

    document.body.style.overflow = "hidden";
    titleRef.current?.focus();

    return () => {
      for (const [element, wasInert] of originalInertState) {
        element.inert = wasInert;
      }

      document.body.style.overflow = previousOverflow;

      const returnTarget = openerRef.current;
      if (returnTarget?.isConnected) {
        returnTarget.focus();
      } else {
        fallbackFocusTarget?.focus();
      }
    };
  }, [open, portalRoot]);

  useLayoutEffect(
    () => () => {
      portalRoot?.remove();
    },
    [portalRoot],
  );

  function handleDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      return;
    }

    if (event.key !== "Tab" || !dialogRef.current) return;

    const focusable = getFocusableElements(dialogRef.current);
    if (focusable.length === 0) {
      event.preventDefault();
      dialogRef.current.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const focusedIndex = focusable.indexOf(document.activeElement as HTMLElement);

    if (event.shiftKey && focusedIndex <= 0) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (focusedIndex === -1 || focusedIndex === focusable.length - 1)) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={showDialog}
        className="inline-flex min-h-11 items-center justify-center rounded-full bg-slate-950 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sky-700"
      >
        Open sample dialog
      </button>

      {open && portalRoot
        ? createPortal(
            <div
              className="fixed inset-0 z-50 grid place-items-center bg-slate-950/55 p-4 sm:p-8"
              onMouseDown={(event) => {
                if (event.target === event.currentTarget) setOpen(false);
              }}
            >
              <div
                ref={dialogRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={`${id}-title`}
                onKeyDown={handleDialogKeyDown}
                tabIndex={-1}
                className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 text-slate-950 shadow-2xl sm:p-8"
              >
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close dialog"
                  className="absolute right-5 top-5 inline-flex size-11 items-center justify-center rounded-full border border-slate-200 text-xl leading-none text-slate-600 transition hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                >
                  <span aria-hidden="true">×</span>
                </button>
                <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-sky-800">
                  Review change
                </p>
                <h3
                  ref={titleRef}
                  id={`${id}-title`}
                  tabIndex={-1}
                  className="max-w-sm text-2xl font-semibold tracking-tight focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sky-700"
                >
                  Save this lead as a priority?
                </h3>
                <p className="mt-3 max-w-md text-sm leading-6 text-slate-600">
                  This sample confirmation keeps the next action explicit. Nothing is sent, deleted, or changed outside this demo.
                </p>

                <label
                  htmlFor={`${id}-note`}
                  className="mt-6 block text-sm font-semibold text-slate-800"
                >
                  Add a review note
                </label>
                <input
                  id={`${id}-note`}
                  type="text"
                  placeholder="Optional note"
                  className="mt-2 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-950 placeholder:text-slate-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                />

                <div className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="inline-flex min-h-11 items-center justify-center rounded-full border border-slate-300 px-5 text-sm font-semibold text-slate-800 transition hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="inline-flex min-h-11 items-center justify-center rounded-full bg-sky-800 px-5 text-sm font-semibold text-white transition hover:bg-sky-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
                  >
                    Confirm sample
                  </button>
                </div>
              </div>
            </div>,
            portalRoot,
          )
        : null}
    </>
  );
}

function TabsDemo() {
  const id = useId().replaceAll(":", "");
  const [activeIndex, setActiveIndex] = useState(0);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function handleTabKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const currentIndex = tabRefs.current.findIndex((tab) => tab === event.target);
    if (currentIndex < 0) return;

    const direction = window.getComputedStyle(event.currentTarget).direction;
    const forwardKey = direction === "rtl" ? "ArrowLeft" : "ArrowRight";
    const backwardKey = direction === "rtl" ? "ArrowRight" : "ArrowLeft";
    let nextIndex: number | null = null;

    if (event.key === forwardKey) {
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (event.key === backwardKey) {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tabs.length - 1;
    }

    if (nextIndex === null) return;
    event.preventDefault();
    setActiveIndex(nextIndex);
    tabRefs.current[nextIndex]?.focus();
  }

  return (
    <div>
      <div
        role="tablist"
        aria-label="Lead workspace sections"
        aria-orientation="horizontal"
        onKeyDown={handleTabKeyDown}
        className="flex flex-wrap gap-1 border-b border-slate-200"
      >
        {tabs.map((tab, index) => (
          <button
            key={tab.label}
            ref={(element) => {
              tabRefs.current[index] = element;
            }}
            type="button"
            role="tab"
            id={`${id}-tab-${index}`}
            aria-controls={`${id}-panel-${index}`}
            aria-selected={activeIndex === index}
            tabIndex={activeIndex === index ? 0 : -1}
            onFocus={() => setActiveIndex(index)}
            onClick={() => setActiveIndex(index)}
            className={`relative -mb-px inline-flex min-h-12 items-center border-b-2 px-4 text-sm font-semibold transition focus-visible:z-10 focus-visible:rounded-t-lg focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-sky-700 ${
              activeIndex === index
                ? "border-sky-800 text-sky-950"
                : "border-transparent text-slate-600 hover:text-slate-950"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {tabs.map((tab, index) => (
        <div
          key={tab.label}
          id={`${id}-panel-${index}`}
          role="tabpanel"
          aria-labelledby={`${id}-tab-${index}`}
          hidden={activeIndex !== index}
          tabIndex={0}
          className="rounded-b-xl p-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
        >
          <h3 className="text-base font-semibold text-slate-950">{tab.title}</h3>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">{tab.body}</p>
        </div>
      ))}
    </div>
  );
}

function DisclosureDemo() {
  const id = useId().replaceAll(":", "");
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200">
      <h3>
        <button
          type="button"
          id={`${id}-trigger`}
          aria-expanded={expanded}
          aria-controls={`${id}-panel`}
          onClick={() => setExpanded((value) => !value)}
          className="flex min-h-14 w-full items-center justify-between gap-4 px-5 text-left text-sm font-semibold text-slate-900 transition hover:bg-slate-50 focus-visible:relative focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-offset-[-3px] focus-visible:outline-sky-700"
        >
          <span>What makes this disclosure accessible?</span>
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="none"
            className={`size-5 shrink-0 text-slate-500 transition-transform ${expanded ? "rotate-180" : ""}`}
          >
            <path d="m5 7.5 5 5 5-5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </h3>
      <div
        id={`${id}-panel`}
        role="region"
        aria-labelledby={`${id}-trigger`}
        hidden={!expanded}
        className="border-t border-slate-200 px-5 py-4 text-sm leading-6 text-slate-600"
      >
        A native button supplies Enter and Space behavior. Its expanded state and controlled panel are connected with ARIA, and the content is removed from both view and the accessibility tree while collapsed.
      </div>
    </div>
  );
}

export default function AccessibleWidgets() {
  return (
    <div className="min-h-screen bg-[#f5f7f8] text-slate-950">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex min-h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
          <Link
            href="/"
            className="rounded-sm text-sm font-semibold tracking-tight text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sky-700"
          >
            Signal Desk <span className="font-normal text-slate-500">/ component lab</span>
          </Link>
          <span className="hidden text-xs font-medium uppercase tracking-[0.16em] text-slate-500 sm:inline">
            FE-03 · Interaction patterns
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-800">
            Built without component libraries
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
            Small controls. Clear behavior.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600">
            Try each pattern with a keyboard. Focus stays visible, state is exposed to assistive technology, and the dialog keeps the page behind it inactive until it closes.
          </p>
        </div>

        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          <section aria-labelledby="dialog-heading" className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">01 / modal</p>
                <h2 id="dialog-heading" className="mt-2 text-xl font-semibold tracking-tight">Review in context</h2>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">Focus contained</span>
            </div>
            <p className="mt-3 min-h-12 text-sm leading-6 text-slate-600">
              Opens a labelled dialog, moves focus inside, makes the background inert, and restores focus when it closes.
            </p>
            <div className="mt-6"><ModalDialog /></div>
            <p className="mt-4 text-xs leading-5 text-slate-500">Keyboard: Tab and Shift+Tab cycle inside · Escape closes</p>
          </section>

          <section aria-labelledby="tabs-heading" className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">02 / tabs</p>
                <h2 id="tabs-heading" className="mt-2 text-xl font-semibold tracking-tight">Move between views</h2>
              </div>
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">Automatic activation</span>
            </div>
            <p className="mt-3 min-h-12 text-sm leading-6 text-slate-600">
              One tab stop enters the set. Arrow keys move focus and select instantly loaded panels.
            </p>
            <div className="mt-5"><TabsDemo /></div>
            <p className="mt-3 text-xs leading-5 text-slate-500">Keyboard: Left/Right Arrow · Home/End · Tab leaves the tab list</p>
          </section>

          <section aria-labelledby="disclosure-heading" className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8 lg:col-span-2">
            <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
              <div className="max-w-md">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">03 / disclosure</p>
                <h2 id="disclosure-heading" className="mt-2 text-xl font-semibold tracking-tight">Reveal detail on request</h2>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  A button controls one labelled region. Its visible label and expanded state stay in sync.
                </p>
              </div>
              <div className="w-full max-w-2xl"><DisclosureDemo /></div>
            </div>
            <p className="mt-4 text-xs leading-5 text-slate-500">Keyboard: Tab to the heading button · Enter or Space toggles</p>
          </section>
        </div>

        <aside aria-label="Manual keyboard test reminder" className="mt-8 rounded-2xl border border-sky-200 bg-sky-50 px-5 py-4 text-sm leading-6 text-sky-950">
          <strong>Manual check:</strong> use Tab and Shift+Tab to move through the page, then try the key hints above. A visible focus ring should follow every focused control.
        </aside>
      </main>
    </div>
  );
}
