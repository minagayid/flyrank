"use client";

import dynamic from "next/dynamic";

const SignalShader = dynamic(() => import("@/components/practice/signal-shader"), {
  ssr: false,
  loading: () => (
    <main className="flex min-h-screen items-center justify-center overflow-hidden bg-[#EFF4F1] px-6 text-[#20363D]">
      <div className="relative flex min-h-[22rem] max-w-md flex-col items-center justify-center text-center">
        <div aria-hidden="true" className="absolute h-64 w-64 rounded-full border border-dashed border-[#3E7771]/40">
          <div className="absolute inset-[15%] rounded-full border border-[#A86F2C]/35" />
          <div className="absolute inset-[30%] rounded-full bg-[radial-gradient(circle_at_34%_30%,#eff4f1_0%,#8baea7_38%,#3e7771_76%,#20363d_100%)]" />
        </div>
        <div className="relative rounded-3xl border border-[#D2DEDA] bg-[#EFF4F1]/90 p-7 backdrop-blur-sm">
          <h1 className="text-2xl font-semibold tracking-[-0.03em]">Listen for the signal.</h1>
          <p className="mt-3 text-sm leading-6 text-[#20363D]/70">The still signal is ready while the shader loads.</p>
        </div>
      </div>
    </main>
  ),
});

export default function ShaderPlaygroundPage() {
  return <SignalShader />;
}
