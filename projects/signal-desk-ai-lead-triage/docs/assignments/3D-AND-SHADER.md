# 3D and shader playgrounds

These two optional exercises give Signal Desk a small visual study without placing graphics work on the inbox route.

## 3D signal study

Route: `/playground/3d`

The scene is a Three.js orb with three orbit paths and brass signal markers. Drag the canvas to inspect it; the turn buttons also work without a pointer. The surface button switches between sea glass and mineral ceramic, changing color, roughness, transparency, and clearcoat. The canvas is loaded as a client-only route chunk, and Three.js is imported only after the route is opened and the reduced-motion preference has been checked.

The canvas is decorative to assistive technology. A caption describes the object, and a static illustration is shown while loading, when WebGL is unavailable, and when reduced motion is enabled. Turning the scene with the buttons remains available in the still view.

## Full-screen shader study

Route: `/playground/shader`

The original WebGL fragment shader combines orbit contours, a shaded core, polar index marks, and a scan line. It uses `u_time` for its slow motion and `u_resolution` for aspect-aware placement. The page can pause and resume the animation. It stops drawing while the document is hidden and uses a CSS illustration for reduced motion or when WebGL cannot start.

## Performance and access

The 3D renderer caps device pixel ratio at 1.5 (1.25 on narrow screens) and uses a compact scene. The shader caps it at 1.5 (1.2 on narrow screens); full-screen fragment work still scales with the device's pixel count. Both graphics pause or stay still when appropriate. These are implementation choices, not benchmark results: frame rate, thermal impact, and battery use vary by browser and hardware, and no performance measurement has been recorded.

Both routes use the product palette, sentence-case copy, visible focus states, direct controls, and a mobile layout. The graphics do not carry the only copy or required actions.

## Skills practiced

- Building a small Three.js scene from geometry, materials, lights, and a camera.
- Handling pointer gestures, resize observation, page visibility, WebGL cleanup, and reduced-motion preferences.
- Writing a WebGL fragment shader with time and resolution uniforms, compiling it at runtime, and keeping a static fallback.
- Capping drawing resolution and describing performance limits without presenting an estimate as a measurement.

## Verification record

The source was reviewed for the listed controls, fallbacks, cleanup, and reduced-motion/visibility behavior. Automated tests, a browser run, and performance profiling were not performed for this assignment.
