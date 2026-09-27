"use client";

import dynamic from "next/dynamic";

const SignalOrb3D = dynamic(() => import("@/components/practice/signal-orb-3d"), {
  ssr: false,
  loading: () => (
    <main className="flex min-h-screen items-center justify-center bg-[#EFF4F1] px-6 text-[#20363D]">
      <div className="max-w-md text-center">
        <div aria-hidden="true" className="mx-auto mb-6 h-24 w-24 rounded-full border border-dashed border-[#3E7771]/50 bg-[radial-gradient(circle_at_34%_30%,#eff4f1_0%,#8baea7_38%,#3e7771_76%,#20363d_100%)]" />
        <h1 className="text-2xl font-semibold tracking-[-0.03em]">A signal, held in orbit.</h1>
        <p className="mt-3 text-sm leading-6 text-[#20363D]/70">The illustrated signal is ready while the interactive view loads.</p>
      </div>
    </main>
  ),
});

export default function ThreePlaygroundPage() {
  return <SignalOrb3D />;
}
