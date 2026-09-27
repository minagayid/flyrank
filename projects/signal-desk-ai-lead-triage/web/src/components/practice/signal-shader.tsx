"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

type ShaderStatus = { revision: number; state: "ready" | "error" };

const vertexSource = `
attribute vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

const fragmentSource = `
precision mediump float;
uniform float u_time;
uniform vec2 u_resolution;

const float PI = 3.14159265359;

void main() {
  vec2 centered = (gl_FragCoord.xy - 0.5 * u_resolution) / min(u_resolution.x, u_resolution.y);
  float portrait = 1.0 - step(u_resolution.x, u_resolution.y);
  vec2 center = mix(vec2(0.42, 0.02), vec2(0.0, 0.16), portrait);
  vec2 point = centered - center;
  float radius = length(point);
  float angle = atan(point.y, point.x);
  float time = u_time;

  float breathing = sin(time * 0.42) * 0.018;
  float outerBand = 0.5 + breathing + 0.022 * sin(angle * 4.0 + time * 0.16);
  float innerBand = 0.34 + 0.014 * sin(angle * 7.0 - time * 0.1);
  float outerLine = 1.0 - smoothstep(0.006, 0.02, abs(radius - outerBand));
  float innerLine = 1.0 - smoothstep(0.005, 0.016, abs(radius - innerBand));
  float core = 1.0 - smoothstep(0.19, 0.225, radius);
  float halo = exp(-max(radius - 0.2, 0.0) * 8.0) * smoothstep(0.2, 0.38, radius);

  float polarMark = fract((angle + PI) * 15.9155);
  float ticks = (1.0 - smoothstep(0.0, 0.025, abs(polarMark - 0.5)))
    * (1.0 - smoothstep(0.53, 0.66, radius)) * step(0.55, radius);
  float scan = 1.0 - smoothstep(0.0, 0.006, abs(point.y - sin(point.x * 5.0 + time * 0.24) * 0.025));
  scan *= (1.0 - smoothstep(0.2, 0.45, abs(point.x))) * (1.0 - core);

  vec3 paper = vec3(0.937, 0.957, 0.945);
  vec3 tide = vec3(0.243, 0.466, 0.443);
  vec3 deep = vec3(0.125, 0.212, 0.239);
  vec3 brass = vec3(0.659, 0.435, 0.173);
  vec3 berry = vec3(0.49, 0.322, 0.416);

  vec3 color = paper;
  color = mix(color, tide, halo * 0.14);
  color = mix(color, tide, outerLine * 0.75);
  color = mix(color, deep, innerLine * 0.92);
  color = mix(color, deep, core * 0.25);
  color += tide * core * (0.08 + 0.05 * sin(time * 0.72));
  color = mix(color, brass, ticks * 0.82);
  color = mix(color, berry, scan * 0.46);

  float grain = sin(gl_FragCoord.x * 0.17) * sin(gl_FragCoord.y * 0.11) * 0.003;
  color += vec3(grain);
  gl_FragColor = vec4(color, 1.0);
}
`;

function compileShader(gl: WebGLRenderingContext, kind: number, source: string) {
  const shader = gl.createShader(kind);
  if (!shader) throw new Error("Could not create shader.");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const detail = gl.getShaderInfoLog(shader) || "Shader compilation failed.";
    gl.deleteShader(shader);
    throw new Error(detail);
  }
  return shader;
}

function StaticSignalField() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden bg-[#EFF4F1]">
      <div className="absolute right-[-18rem] top-[10%] h-[min(70vw,44rem)] w-[min(70vw,44rem)] rounded-full border border-[#3E7771]/30 sm:right-[2%]">
        <div className="absolute inset-[12%] rounded-full border border-[#A86F2C]/35" />
        <div className="absolute inset-[24%] rounded-full border border-[#3E7771]/40" />
        <div className="absolute inset-[34%] rounded-full bg-[radial-gradient(circle_at_35%_30%,#eff4f1_0%,#8baea7_38%,#3e7771_76%,#20363d_100%)] shadow-[0_22px_70px_rgba(32,54,61,.12)]" />
      </div>
      <div className="absolute inset-x-0 bottom-[16%] h-px bg-[linear-gradient(90deg,transparent,#7D526A55,transparent)]" />
    </div>
  );
}

export default function SignalShader() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pausedRef = useRef(false);
  const runnerRef = useRef<{ start: () => void; stop: () => void } | null>(null);
  const [reducedMotion, setReducedMotion] = useState<boolean | null>(null);
  const [preferenceRevision, setPreferenceRevision] = useState(0);
  const [paused, setPaused] = useState(false);
  const [shaderStatus, setShaderStatus] = useState<ShaderStatus | null>(null);

  const shaderReady = reducedMotion === false
    && shaderStatus?.revision === preferenceRevision
    && shaderStatus?.state === "ready";
  const shaderError = reducedMotion === false
    && shaderStatus?.revision === preferenceRevision
    && shaderStatus?.state === "error";

  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncPreference = () => {
      setReducedMotion(preference.matches);
      setPreferenceRevision((revision) => revision + 1);
    };
    syncPreference();
    preference.addEventListener("change", syncPreference);
    return () => preference.removeEventListener("change", syncPreference);
  }, []);

  useEffect(() => {
    if (reducedMotion !== false) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    let disposed = false;
    let frame = 0;
    let readyFrame = 0;
    let program: WebGLProgram | null = null;
    let buffer: WebGLBuffer | null = null;
    let gl: WebGLRenderingContext | null = null;
    let resizeObserver: ResizeObserver | undefined;
    let contextLost = false;

    try {
      gl = canvas.getContext("webgl", {
        alpha: false,
        antialias: false,
        powerPreference: "low-power",
      });
      if (!gl) throw new Error("WebGL is unavailable.");

      const vertexShader = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
      const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
      program = gl.createProgram();
      if (!program) throw new Error("Could not create shader program.");
      gl.attachShader(program, vertexShader);
      gl.attachShader(program, fragmentShader);
      gl.linkProgram(program);
      gl.deleteShader(vertexShader);
      gl.deleteShader(fragmentShader);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(program) || "Shader link failed.");
      }

      gl.useProgram(program);
      buffer = gl.createBuffer();
      if (!buffer) throw new Error("Could not create shader geometry.");
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(
        gl.ARRAY_BUFFER,
        new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
        gl.STATIC_DRAW,
      );
      const position = gl.getAttribLocation(program, "a_position");
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      const timeLocation = gl.getUniformLocation(program, "u_time");
      const resolutionLocation = gl.getUniformLocation(program, "u_resolution");
      const start = performance.now();

      const render = (now: number) => {
        if (!gl || !program || contextLost) return;
        gl.useProgram(program);
        gl.uniform1f(timeLocation, (now - start) / 1000);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
      };
      const resize = () => {
        if (!gl) return;
        const ratioLimit = window.innerWidth < 640 ? 1.2 : 1.5;
        const ratio = Math.min(window.devicePixelRatio || 1, ratioLimit);
        const width = Math.max(1, Math.floor(window.innerWidth * ratio));
        const height = Math.max(1, Math.floor(window.innerHeight * ratio));
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
        gl.uniform2f(resolutionLocation, width, height);
        render(pausedRef.current ? start : performance.now());
      };
      const tick = (now: number) => {
        if (document.hidden || contextLost) return;
        render(now);
        frame = window.requestAnimationFrame(tick);
      };
      const stop = () => {
        window.cancelAnimationFrame(frame);
        frame = 0;
        render(start);
      };
      const begin = () => {
        if (document.hidden || frame || disposed || contextLost) return;
        frame = window.requestAnimationFrame(tick);
      };
      const onVisibilityChange = () => {
        if (document.hidden) stop();
        else if (!pausedRef.current) begin();
      };
      const onContextLost = (event: Event) => {
        event.preventDefault();
        contextLost = true;
        window.cancelAnimationFrame(readyFrame);
        runnerRef.current?.stop();
        setShaderStatus({ revision: preferenceRevision, state: "error" });
      };

      resize();
      window.addEventListener("resize", resize);
      document.addEventListener("visibilitychange", onVisibilityChange);
      canvas.addEventListener("webglcontextlost", onContextLost);
      if ("ResizeObserver" in window) {
        resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(document.documentElement);
      }
      runnerRef.current = { start: begin, stop };
      if (!pausedRef.current) begin();
      readyFrame = window.requestAnimationFrame(() => {
        if (!disposed && !contextLost) {
          setShaderStatus({ revision: preferenceRevision, state: "ready" });
        }
      });

      return () => {
        disposed = true;
        stop();
        window.cancelAnimationFrame(readyFrame);
        runnerRef.current = null;
        window.removeEventListener("resize", resize);
        document.removeEventListener("visibilitychange", onVisibilityChange);
        canvas.removeEventListener("webglcontextlost", onContextLost);
        resizeObserver?.disconnect();
        if (gl && buffer) gl.deleteBuffer(buffer);
        if (gl && program) gl.deleteProgram(program);
      };
    } catch {
      if (!disposed) {
        setShaderStatus({ revision: preferenceRevision, state: "error" });
      }
      if (gl && buffer) gl.deleteBuffer(buffer);
      if (gl && program) gl.deleteProgram(program);
      return;
    }
  }, [preferenceRevision, reducedMotion]);

  useEffect(() => {
    if (paused) runnerRef.current?.stop();
    else runnerRef.current?.start();
  }, [paused]);

  const togglePause = () => {
    const next = !pausedRef.current;
    pausedRef.current = next;
    setPaused(next);
  };

  const fallbackVisible = reducedMotion !== false || !shaderReady;
  const canAnimate = reducedMotion === false && shaderReady;

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#EFF4F1] text-[#20363D]">
      {fallbackVisible ? <StaticSignalField /> : null}
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className={`pointer-events-none fixed inset-0 z-0 h-full w-full ${shaderReady ? "opacity-100" : "opacity-0"}`}
      />

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-7xl flex-col px-5 sm:px-8 lg:px-12">
        <header className="flex items-center justify-between gap-4 py-5">
          <Link href="/" className="text-sm font-semibold tracking-[-0.02em] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#3E7771]">
            Signal Desk
          </Link>
          <nav aria-label="Playground" className="flex items-center gap-4 text-sm text-[#20363D]/75">
            <Link className="underline decoration-[#3E7771]/40 underline-offset-4 hover:text-[#3E7771] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#3E7771]" href="/playground/3d">3D study</Link>
            <Link className="underline decoration-[#3E7771]/40 underline-offset-4 hover:text-[#3E7771] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#3E7771]" href="/">Back to inbox</Link>
          </nav>
        </header>

        <section className="flex flex-1 items-center py-12 sm:py-20">
          <div className="max-w-xl rounded-[1.75rem] border border-[#D2DEDA] bg-[#EFF4F1]/90 p-6 shadow-[0_18px_55px_rgba(32,54,61,.08)] backdrop-blur-sm sm:p-10">
            <p className="mb-4 font-mono text-xs text-[#7D526A]">Playground / shader study</p>
            <h1 className="max-w-[12ch] text-4xl font-semibold leading-[1.08] tracking-[-0.045em] sm:text-5xl">
              Listen for the signal.
            </h1>
            <p className="mt-5 max-w-[39rem] text-base leading-7 text-[#20363D]/78">
              A living field of orbit paths and scan marks, composed to sit behind the words that help a studio decide what deserves attention. The animation stays quiet so the inquiry can stay clear.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={togglePause}
                disabled={!canAnimate}
                className="min-h-11 rounded-full bg-[#20363D] px-5 text-sm font-medium text-[#EFF4F1] transition-colors hover:bg-[#3E7771] focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[#3E7771] disabled:cursor-not-allowed disabled:bg-[#D2DEDA] disabled:text-[#20363D]/60"
              >
                {reducedMotion ? "Animation off by preference" : shaderError ? "Animation unavailable" : paused ? "Resume shader" : "Pause shader"}
              </button>
              <Link href="/" className="min-h-11 rounded-full border border-[#20363D]/20 px-5 py-3 text-sm font-medium transition-colors hover:border-[#3E7771] hover:bg-white/70 focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[#3E7771]">
                Review the inbox
              </Link>
            </div>

            <p aria-live="polite" className="mt-5 text-sm leading-6 text-[#20363D]/78">
              {reducedMotion ? "A still signal is shown because reduced motion is enabled." : shaderError ? "WebGL could not start, so the still signal remains available." : paused ? "The signal is paused." : shaderReady ? "The signal moves gently while this tab is visible." : "Preparing the still signal…"}
            </p>
          </div>
        </section>

        <footer className="flex flex-col gap-1 border-t border-[#D2DEDA]/80 py-5 text-xs leading-5 text-[#536A67] sm:flex-row sm:items-center sm:justify-between">
          <p>Original GLSL fragment shader with a still illustration for reduced motion and unsupported graphics.</p>
          <p>Full-screen drawing; DPR is capped at 1.5. Frame rate and battery use vary by device.</p>
        </footer>
      </div>
      <p className="sr-only">A calm signal field with concentric orbit lines, a shaded core, brass index ticks, and a slow scan mark.</p>
    </main>
  );
}
