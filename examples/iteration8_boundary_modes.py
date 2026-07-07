"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 8 — Boundary Modes                                      ║
╚══════════════════════════════════════════════════════════════════════╝

 Two boundary handling strategies, switchable at runtime.

   • TOROIDAL WRAP (default) — birds exiting one edge re-enter from
     the opposite edge. Creates an infinite, periodic universe.

   • MARGIN KEEP-WITHIN-BOUNDS — birds near the edge are nudged
     toward the center. Creates a bounded arena with wall avoidance.

 What we learn:
   • Toroidal wrap: if x > WIDTH → x = 0 (modulo-like)
   • Margin nudge: velocity is pushed away from walls when close
   • Nudge timing — applied BEFORE the speed clamp so nudge doesn't
     cause runaway speed
   • Hard clamp — margin mode also clamps position to [0, WIDTH]
   • Runtime toggle — press 'B' to switch between modes
──────────────────────────────────────────────────────────────────────
"""

# ── Boundary constants ─────────────────────────────────────────────
MARGIN_BOUNDARY = False         # False = toroidal, True = margin
BOUNDARY_MARGIN = 200           # px from edge to start turning
BOUNDARY_TURN_FACTOR = 1        # velocity nudge strength

# ── Boundary handling snippet (insert in Boid.update()) ────────────

def apply_boundary_nudge(boid):
    """
    Margin mode: nudge velocity away from walls BEFORE speed clamp.
    This ensures the nudge is absorbed by the clamp same-frame,
    preventing speed from exceeding V₀.
    """
    if boid.position.x < BOUNDARY_MARGIN:
        boid.velocity.x += BOUNDARY_TURN_FACTOR
    if boid.position.x > WIDTH - BOUNDARY_MARGIN:
        boid.velocity.x -= BOUNDARY_TURN_FACTOR
    if boid.position.y < BOUNDARY_MARGIN:
        boid.velocity.y += BOUNDARY_TURN_FACTOR
    if boid.position.y > HEIGHT - BOUNDARY_MARGIN:
        boid.velocity.y -= BOUNDARY_TURN_FACTOR


def apply_position_boundary(boid):
    """
    After speed clamp and position update, handle boundary:
      - Toroidal: wrap around to opposite edge
      - Margin: hard clamp to [0, WIDTH]×[0, HEIGHT]
    """
    if MARGIN_BOUNDARY:
        boid.position.x = max(0, min(WIDTH, boid.position.x))
        boid.position.y = max(0, min(HEIGHT, boid.position.y))
    else:
        if boid.position.x > WIDTH:
            boid.position.x = 0
        elif boid.position.x < 0:
            boid.position.x = WIDTH
        if boid.position.y > HEIGHT:
            boid.position.y = 0
        elif boid.position.y < 0:
            boid.position.y = HEIGHT


# ══════════════════════════════════════════════════════════════════════
#  INTEGRATION EXAMPLE — Updated Boid.update() with boundary modes
# ══════════════════════════════════════════════════════════════════════
#
#  def update(self):
#      self.velocity += self.acceleration
#
#      # ── 1. Margin nudge (BEFORE speed clamp) ──
#      if MARGIN_BOUNDARY:
#          apply_boundary_nudge(self)
#
#      # ── 2. Speed clamp ──
#      speed = self.velocity.length()
#      if speed > V0:  self.velocity.scale_to_length(V0)
#      elif speed < V0 * 0.3:  ...  # floor as before
#
#      # ── 3. Position update ──
#      self.position += self.velocity
#      self.acceleration *= 0
#
#      # ── 4. Boundary handling ──
#      apply_position_boundary(self)
#
#  The nudge runs BEFORE the clamp so the clamp absorbs the nudge
#  same-frame. Speed never exceeds V₀ even with continuous nudging.
#  This eliminates wall-jitter from the speed floor.


# ── Key insight: why nudge before clamp? ───────────────────────────
"""
If the nudge runs AFTER the clamp:
  1. Speed is clamped to V₀
  2. Nudge adds +1 to velocity → speed = V₀ + 1 (exceeds V₀!)
  3. Next frame: clamp reduces speed, nudge adds +1 again
  4. Result: speed oscillates V₀ ↔ V₀+1 every frame → wall jitter

If the nudge runs BEFORE the clamp:
  1. Nudge adds +1 → speed = V₀ + 1
  2. Clamp reduces to V₀ (absorbing the nudge same-frame)
  3. Result: smooth, speed stays at V₀, no oscillation
"""
