"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

type MaterialMode = "glass" | "ceramic";

type SceneController = {
  draw: () => void;
  rotate: (radians: number) => void;
  setMaterial: (mode: MaterialMode) => void;
  dispose: () => void;
};

type SceneStatus = { revision: number; state: "ready" | "error" };

function SignalOrbFallback({ turn, materialMode }: { turn: number; materialMode: MaterialMode }) {
  return (
    <div
      aria-hidden="true"
      className="relative flex aspect-square w-full max-w-[27rem] items-center justify-center"
    >
      <div
        className="absolute inset-[10%] rounded-full border border-dashed border-[#3E7771]/35"
        style={{ transform: `rotate(${turn}deg)` }}
      />
      <div
        className="absolute inset-[19%] rounded-full border border-[#A86F2C]/35"
        style={{ transform: `rotate(${-turn * 0.6}deg)` }}
      />
      <div
        className="absolute inset-[28%] rounded-full border border-[#3E7771]/25"
        style={{ transform: `rotate(${turn * 0.35}deg)` }}
      />
      <div
        className="relative h-[39%] w-[39%] rounded-full border border-[#3E7771]/30"
        style={{
          background: materialMode === "glass"
            ? "radial-gradient(circle at 34% 30%, #eff4f1 0%, #8baea7 34%, #3e7771 72%, #20363d 100%)"
            : "radial-gradient(circle at 34% 30%, #eff4f1 0%, #c5acb8 34%, #7d526a 72%, #20363d 100%)",
          boxShadow: "inset -12px -16px 28px rgba(32,54,61,.2), 0 24px 60px rgba(32,54,61,.14)",
        }}
      />
      <span className="absolute right-[17%] top-[30%] h-2.5 w-2.5 rounded-full bg-[#A86F2C] ring-4 ring-[#A86F2C]/15" />
      <span className="absolute bottom-[23%] left-[24%] h-2 w-2 rounded-full bg-[#7D526A] ring-4 ring-[#7D526A]/15" />
    </div>
  );
}

export default function SignalOrb3D() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const controllerRef = useRef<SceneController | null>(null);
  const materialRef = useRef<MaterialMode>("glass");
  const [materialMode, setMaterialMode] = useState<MaterialMode>("glass");
  const [reducedMotion, setReducedMotion] = useState<boolean | null>(null);
  const [preferenceRevision, setPreferenceRevision] = useState(0);
  const [sceneStatus, setSceneStatus] = useState<SceneStatus | null>(null);
  const [fallbackTurn, setFallbackTurn] = useState(0);

  const sceneReady = reducedMotion === false
    && sceneStatus?.revision === preferenceRevision
    && sceneStatus?.state === "ready";
  const sceneError = reducedMotion === false
    && sceneStatus?.revision === preferenceRevision
    && sceneStatus?.state === "error";

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncPreference = () => {
      setReducedMotion(media.matches);
      setPreferenceRevision((revision) => revision + 1);
    };
    syncPreference();
    media.addEventListener("change", syncPreference);
    return () => media.removeEventListener("change", syncPreference);
  }, []);

  useEffect(() => {
    if (reducedMotion !== false) return;

    let disposed = false;
    let frame = 0;
    let observer: ResizeObserver | undefined;
    let removeCanvasHandlers = () => {};
    let removeVisibilityHandler = () => {};
    const canvas = canvasRef.current;

    if (!canvas) return;

    const initialize = async () => {
      try {
        const THREE = await import("three");
        if (disposed) return;

        const renderer = new THREE.WebGLRenderer({
          canvas,
          alpha: true,
          antialias: window.devicePixelRatio <= 1.5,
          powerPreference: "low-power",
        });
        const pixelRatioLimit = window.innerWidth < 640 ? 1.25 : 1.5;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, pixelRatioLimit));
        renderer.setClearColor(0xeff4f1, 0);

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 40);
        camera.position.set(0, 0, 6.4);

        const root = new THREE.Group();
        scene.add(root);

        const orbGeometry = new THREE.SphereGeometry(1.12, 56, 40);
        const glassMaterial = new THREE.MeshPhysicalMaterial({
          color: 0x3e7771,
          metalness: 0.08,
          roughness: 0.2,
          clearcoat: 0.8,
          clearcoatRoughness: 0.14,
          transparent: true,
          opacity: 0.86,
        });
        const ceramicMaterial = new THREE.MeshPhysicalMaterial({
          color: 0x7d526a,
          metalness: 0.12,
          roughness: 0.43,
          clearcoat: 0.28,
          clearcoatRoughness: 0.35,
        });
        const orb = new THREE.Mesh(orbGeometry, glassMaterial);
        root.add(orb);

        const ringMaterial = new THREE.MeshBasicMaterial({
          color: 0x3e7771,
          transparent: true,
          opacity: 0.52,
        });
        const brassMaterial = new THREE.MeshBasicMaterial({
          color: 0xa86f2c,
          transparent: true,
          opacity: 0.8,
        });
        const rings = [
          { geometry: new THREE.TorusGeometry(1.53, 0.009, 8, 144), rotation: [0.88, 0.18, 0.22] },
          { geometry: new THREE.TorusGeometry(1.82, 0.007, 8, 144), rotation: [0.28, 1.08, -0.38] },
          { geometry: new THREE.TorusGeometry(1.34, 0.006, 8, 144), rotation: [-0.62, 0.62, 0.82] },
        ];
        for (const [index, ring] of rings.entries()) {
          const mesh = new THREE.Mesh(ring.geometry, index === 1 ? brassMaterial : ringMaterial);
          mesh.rotation.set(ring.rotation[0], ring.rotation[1], ring.rotation[2]);
          root.add(mesh);
        }

        const nodes = [
          new THREE.Vector3(1.57, 0.68, 0.1),
          new THREE.Vector3(-1.42, -0.76, 0.24),
          new THREE.Vector3(0.12, 1.78, 0.06),
        ];
        const nodeGeometry = new THREE.SphereGeometry(0.045, 12, 10);
        for (const [index, point] of nodes.entries()) {
          const node = new THREE.Mesh(nodeGeometry, index === 1 ? brassMaterial : ringMaterial);
          node.position.copy(point);
          root.add(node);
        }

        scene.add(new THREE.HemisphereLight(0xeff4f1, 0x20363d, 2.15));
        const keyLight = new THREE.DirectionalLight(0xffffff, 3.2);
        keyLight.position.set(-3.2, 4.1, 5.2);
        scene.add(keyLight);
        const edgeLight = new THREE.PointLight(0xa86f2c, 14, 12, 2);
        edgeLight.position.set(3.4, -1.5, 2.2);
        scene.add(edgeLight);

        const draw = () => renderer.render(scene, camera);
        const setMaterial = (mode: MaterialMode) => {
          orb.material = mode === "glass" ? glassMaterial : ceramicMaterial;
          draw();
        };
        const rotate = (radians: number) => {
          root.rotation.y += radians;
          draw();
        };

        const resize = () => {
          const rect = canvas.parentElement?.getBoundingClientRect();
          if (!rect) return;
          const width = Math.max(1, rect.width);
          const height = Math.max(1, rect.height);
          renderer.setSize(width, height, false);
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
          draw();
        };
        resize();
        if (canvas.parentElement && "ResizeObserver" in window) {
          observer = new ResizeObserver(resize);
          observer.observe(canvas.parentElement);
        } else {
          window.addEventListener("resize", resize);
        }

        let dragging = false;
        let lastX = 0;
        let lastY = 0;
        const onPointerDown = (event: PointerEvent) => {
          dragging = true;
          lastX = event.clientX;
          lastY = event.clientY;
          canvas.setPointerCapture(event.pointerId);
        };
        const onPointerMove = (event: PointerEvent) => {
          if (!dragging) return;
          const dx = event.clientX - lastX;
          const dy = event.clientY - lastY;
          lastX = event.clientX;
          lastY = event.clientY;
          root.rotation.y += dx * 0.008;
          root.rotation.x = Math.max(-0.7, Math.min(0.7, root.rotation.x + dy * 0.006));
          draw();
        };
        const onPointerUp = () => {
          dragging = false;
        };
        canvas.addEventListener("pointerdown", onPointerDown);
        canvas.addEventListener("pointermove", onPointerMove);
        canvas.addEventListener("pointerup", onPointerUp);
        canvas.addEventListener("pointercancel", onPointerUp);
        removeCanvasHandlers = () => {
          canvas.removeEventListener("pointerdown", onPointerDown);
          canvas.removeEventListener("pointermove", onPointerMove);
          canvas.removeEventListener("pointerup", onPointerUp);
          canvas.removeEventListener("pointercancel", onPointerUp);
        };

        const animate = () => {
          if (document.hidden) return;
          root.rotation.y += 0.0018;
          root.rotation.z = Math.sin(performance.now() * 0.00022) * 0.035;
          draw();
          frame = window.requestAnimationFrame(animate);
        };
        const onVisibilityChange = () => {
          window.cancelAnimationFrame(frame);
          if (!document.hidden) frame = window.requestAnimationFrame(animate);
        };
        document.addEventListener("visibilitychange", onVisibilityChange);
        removeVisibilityHandler = () => document.removeEventListener("visibilitychange", onVisibilityChange);
        frame = window.requestAnimationFrame(animate);

        controllerRef.current = {
          draw,
          rotate,
          setMaterial,
          dispose: () => {
            window.cancelAnimationFrame(frame);
            observer?.disconnect();
            window.removeEventListener("resize", resize);
            removeCanvasHandlers();
            removeVisibilityHandler();
            orbGeometry.dispose();
            nodeGeometry.dispose();
            glassMaterial.dispose();
            ceramicMaterial.dispose();
            ringMaterial.dispose();
            brassMaterial.dispose();
            for (const ring of rings) ring.geometry.dispose();
            renderer.dispose();
          },
        };
        if (materialRef.current !== "glass") setMaterial(materialRef.current);
        setSceneStatus({ revision: preferenceRevision, state: "ready" });
      } catch {
        if (!disposed) {
          setSceneStatus({ revision: preferenceRevision, state: "error" });
        }
      }
    };

    void initialize();
    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
      removeCanvasHandlers();
      removeVisibilityHandler();
      controllerRef.current?.dispose();
      controllerRef.current = null;
    };
  }, [preferenceRevision, reducedMotion]);

  useEffect(() => {
    controllerRef.current?.setMaterial(materialMode);
  }, [materialMode]);

  const turn = (direction: number) => {
    const radians = direction * (Math.PI / 12);
    setFallbackTurn((current) => current + direction * 15);
    controllerRef.current?.rotate(radians);
  };

  const toggleMaterial = () => {
    const next = materialMode === "glass" ? "ceramic" : "glass";
    materialRef.current = next;
    setMaterialMode(next);
  };

  const showFallback = !sceneReady || reducedMotion;

  return (
    <main className="min-h-screen bg-[#EFF4F1] text-[#20363D]">
      <header className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-5 py-5 sm:px-8 lg:px-12">
        <Link href="/" className="text-sm font-semibold tracking-[-0.02em] text-[#20363D] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#3E7771]">
          Signal Desk
        </Link>
        <nav aria-label="Playground" className="flex items-center gap-4 text-sm text-[#20363D]/75">
          <Link className="underline decoration-[#3E7771]/40 underline-offset-4 hover:text-[#3E7771] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#3E7771]" href="/playground/shader">Shader study</Link>
          <Link className="underline decoration-[#3E7771]/40 underline-offset-4 hover:text-[#3E7771] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#3E7771]" href="/">Back to inbox</Link>
        </nav>
      </header>

      <div className="mx-auto grid w-full max-w-7xl gap-8 px-5 pb-12 pt-4 sm:px-8 md:grid-cols-[minmax(18rem,0.8fr)_minmax(25rem,1.2fr)] md:items-center md:gap-12 md:py-12 lg:px-12">
        <section className="order-2 max-w-xl md:order-1">
          <p className="mb-4 font-mono text-xs text-[#7D526A]">Playground / 3D signal study</p>
          <h1 className="max-w-[12ch] text-4xl font-semibold leading-[1.08] tracking-[-0.045em] sm:text-5xl">
            A signal, held in orbit.
          </h1>
          <p className="mt-5 max-w-[38rem] text-base leading-7 text-[#20363D]/78">
            A small interactive object for the moment before a studio decides what to answer. Drag the glass to turn its signal paths, or change the surface to see how material alters the reading.
          </p>

          <div className="mt-8 flex flex-wrap gap-2.5">
            <button
              type="button"
              onClick={toggleMaterial}
              className="min-h-11 rounded-full border border-[#20363D]/20 bg-[#EFF4F1] px-4 text-sm font-medium text-[#20363D] transition-colors hover:border-[#3E7771] hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[#3E7771]"
            >
              Switch to {materialMode === "glass" ? "ceramic" : "sea glass"} material
            </button>
            <button
              type="button"
              onClick={() => turn(-1)}
              aria-label="Turn the signal left"
              className="min-h-11 rounded-full border border-[#20363D]/20 px-4 text-sm font-medium text-[#20363D] transition-colors hover:border-[#3E7771] hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[#3E7771]"
            >
              Turn left
            </button>
            <button
              type="button"
              onClick={() => turn(1)}
              aria-label="Turn the signal right"
              className="min-h-11 rounded-full border border-[#20363D]/20 px-4 text-sm font-medium text-[#20363D] transition-colors hover:border-[#3E7771] hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[#3E7771]"
            >
              Turn right
            </button>
          </div>

          <p aria-live="polite" className="mt-4 text-sm text-[#20363D]/70">
            Surface: {materialMode === "glass" ? "sea glass" : "mineral ceramic"}.
            {reducedMotion ? " Still view is on for your motion preference." : ""}
            {sceneError ? " The 3D view is unavailable here; the illustrated view is ready." : ""}
          </p>

          <div className="mt-9 border-l-2 border-[#A86F2C] pl-4 text-sm leading-6 text-[#20363D]/72">
            <p className="font-medium text-[#20363D]">A note on rendering</p>
            <p className="mt-1 max-w-[52ch]">
              The scene uses a few lightweight meshes and caps device pixel ratio at 1.5. It pauses while this page is hidden; actual frame rate and battery use still depend on the device and browser.
            </p>
          </div>
        </section>

        <figure className="order-1 flex min-h-[19rem] items-center justify-center overflow-hidden rounded-[2rem] border border-[#D2DEDA] bg-white/55 p-4 sm:min-h-[28rem] md:order-2 md:p-8">
          <div className="relative aspect-square w-full max-w-[34rem]">
            {showFallback ? <SignalOrbFallback turn={fallbackTurn} materialMode={materialMode} /> : null}
            <canvas
              ref={canvasRef}
              aria-hidden="true"
              className={`absolute inset-0 h-full w-full touch-pan-y ${sceneReady ? "opacity-100" : "opacity-0"}`}
              style={{ cursor: sceneReady ? "grab" : "default" }}
            />
            <figcaption className="sr-only">
              An orbiting signal orb with three thin paths and small brass markers. Use the turn buttons to rotate the view or change its surface material.
            </figcaption>
          </div>
        </figure>
      </div>

      <footer className="mx-auto w-full max-w-7xl px-5 pb-7 text-xs text-[#536A67] sm:px-8 lg:px-12">
        {reducedMotion === null ? "Preparing the still illustration…" : reducedMotion ? "Static illustration shown because reduced motion is enabled." : sceneReady ? "Drag the orb to inspect it." : "Showing the static illustration while the 3D scene loads."}
      </footer>
    </main>
  );
}
