"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 6 — Dual-Mode Flocking                                  ║
╚══════════════════════════════════════════════════════════════════════╝

 Combines the projection model (Iteration 5) with the spatial Reynolds
 model (Iteration 3) into a single, switchable simulation. Press 'M'
 to toggle between modes at runtime.

 What we learn:
   • Config class — mutable parameters shared across the simulation
   • Mode dispatch — boid.flock() delegates to the active model
   • Keyboard input — 'M' toggles, ESC quits
   • Runtime mode switching — birds recompute via different algorithms
     on the very next frame
──────────────────────────────────────────────────────────────────────
"""
import math, random
from collections import defaultdict
import pygame, sys

WIDTH, HEIGHT = 1000, 700
NUM_BOIDS = 80
V0, BOID_SIZE, MAX_FORCE = 4.0, 3, 0.15
VISUAL_RANGE = 70
FPS = 60
MODE_PROJECTION, MODE_SPATIAL = 0, 1
_EPS = 1e-7

# ── Occlusion geometry (Iteration 4) ───────────────────────────────
def _normalise_interval(s, e):
    if s < 0: return [(s + 2*math.pi, 2*math.pi), (0, e)]
    if e > 2*math.pi: return [(s, 2*math.pi), (0, e - 2*math.pi)]
    return [(s, e)]
def _interval_covered(start, end, merged):
    cursor = start
    for ms, me in merged:
        if ms - _EPS <= cursor: cursor = max(cursor, me)
        if cursor >= end - _EPS: return True
        if ms > cursor + _EPS: break
    return cursor >= end - _EPS
def _merge_interval(start, end, merged):
    lo, hi, n = 0, len(merged), len(merged)
    while lo < hi: mid = (lo+hi)//2; lo, hi = (mid+1, hi) if merged[mid][0] < start else (lo, mid)
    merged.insert(lo, [start, end])
    if lo > 0 and merged[lo-1][1] >= merged[lo][0] - _EPS:
        merged[lo-1][1] = max(merged[lo-1][1], merged[lo][1]); merged.pop(lo); lo -= 1
    while lo < len(merged)-1 and merged[lo][1] >= merged[lo+1][0] - _EPS:
        merged[lo][1] = max(merged[lo][1], merged[lo+1][1]); merged.pop(lo+1)

class Config:
    """Mutable parameters — modified by keyboard, read by boids."""
    def __init__(self):
        self.mode = MODE_PROJECTION
        self.phi_p, self.phi_a, self.sigma = 0.03, 0.80, 4
    @property
    def phi_n(self): return max(0.0, 1.0 - self.phi_p - self.phi_a)

class SpatialGrid:
    def __init__(self, cs=VISUAL_RANGE):
        self.cs, self.cols, self.rows = cs, max(1,int(math.ceil(WIDTH/cs))), max(1,int(math.ceil(HEIGHT/cs)))
        self.cells = defaultdict(list)
    def rebuild(self, bs):
        self.cells.clear()
        for b in bs:
            cx, cy = int(b.position.x//self.cs)%self.cols, int(b.position.y//self.cs)%self.rows
            self.cells[(cx,cy)].append(b)
    def get_nearby(self, p, r):
        nearby = []
        for cx in range(int((p.x-r)//self.cs), int((p.x+r)//self.cs)+1):
            for cy in range(int((p.y-r)//self.cs), int((p.y+r)//self.cs)+1):
                nearby.extend(self.cells.get((cx%self.cols, cy%self.rows), ()))
        return nearby

class Boid:
    def __init__(self):
        self.position = pygame.Vector2(random.uniform(0,WIDTH), random.uniform(0,HEIGHT))
        a = random.uniform(0, 2*math.pi)
        self.velocity = pygame.Vector2(math.cos(a), math.sin(a)) * V0
        self.acceleration = pygame.Vector2(0,0)
        self._last_theta = 0.0

    def apply_force(self, f): self.acceleration += f

    def update(self):
        self.velocity += self.acceleration
        spd = self.velocity.length()
        if spd > V0: self.velocity.scale_to_length(V0)
        elif spd < V0*0.3:
            if spd > 0.001: self.velocity.scale_to_length(V0*0.3)
            else: self.velocity = pygame.Vector2(math.cos(random.uniform(0,2*math.pi)), math.sin(random.uniform(0,2*math.pi))) * V0*0.3
        self.position += self.velocity
        self.acceleration *= 0
        if self.position.x > WIDTH: self.position.x = 0
        elif self.position.x < 0: self.position.x = WIDTH
        if self.position.y > HEIGHT: self.position.y = 0
        elif self.position.y < 0: self.position.y = HEIGHT

    def flock(self, boids, config, grid):
        """Dispatch to active mode."""
        if config.mode == MODE_PROJECTION:
            self._flock_projection(boids, config)
        else:
            self._flock_spatial(boids, config, grid)

    def _flock_projection(self, boids, config):
        """Projection model (Iteration 5)."""
        # 1. Build angular intervals
        entries = []
        for other in boids:
            if other is self: continue
            d = (other.position - self.position).length()
            if d < 0.001: continue
            centre = math.atan2(other.position.y-self.position.y, other.position.x-self.position.x)
            if centre < 0: centre += 2*math.pi
            half = math.asin(min(BOID_SIZE/d, 1.0))
            entries.append((other, d, centre, half))
        if not entries: return

        # 2. Closest-first occlusion processing
        entries.sort(key=lambda x: x[1])
        merged, visible = [], []
        for other, dist, centre, half in entries:
            start, end = centre - half, centre + half
            is_visible = False
            for s, e in _normalise_interval(start, end):
                if not _interval_covered(s, e, merged):
                    is_visible = True
            if is_visible:
                visible.append((other, dist))
                for s, e in _normalise_interval(start, end):
                    _merge_interval(s, e, merged)

        # 3. δ̂ — sum of unit vectors to domain boundaries
        delta = pygame.Vector2(0, 0)
        for s, e in merged:
            delta += pygame.Vector2(math.cos(s), math.sin(s))
            delta += pygame.Vector2(math.cos(e), math.sin(e))
        if (len(merged) == 1 and merged[0][0] < 1e-9
                and merged[0][1] > 2*math.pi - 1e-9):
            delta = pygame.Vector2(0, 0)
        if delta.length() > 0:
            delta.normalize_ip()

        # 4. Θ = total occluded / 2π
        self._last_theta = min(sum(e - s for s, e in merged) / (2*math.pi), 1.0)

        # 5. Alignment with σ nearest visible neighbours
        aln = pygame.Vector2(0, 0)
        if visible:
            nearest = visible[:config.sigma]
            for nb, _ in nearest:
                aln += nb.velocity
            aln /= len(nearest)

        # 6. Noise
        na = random.uniform(0, 2*math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na))

        # 7. v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
        desired = delta * config.phi_p
        if aln.length() > 0.001:
            desired += aln.normalize() * config.phi_a
        elif self.velocity.length() > 0.001:
            desired += self.velocity.normalize() * config.phi_a
        desired += noise * config.phi_n
        if desired.length() < 0.001:
            desired = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        desired.normalize_ip(); desired *= V0

        # 8. Reynolds steering
        steer = desired - self.velocity
        if steer.length() > MAX_FORCE:
            steer.scale_to_length(MAX_FORCE)
        self.apply_force(steer)

    def _flock_spatial(self, boids, config, grid):
        """Spatial model (Iteration 3)."""
        candidates = grid.get_nearby(self.position, VISUAL_RANGE)
        sep, aln, coh = pygame.Vector2(0,0), pygame.Vector2(0,0), pygame.Vector2(0,0)
        count = 0
        for other in candidates:
            if other is self: continue
            d = self.position.distance_to(other.position)
            if d < VISUAL_RANGE:
                count += 1; aln += other.velocity; coh += other.position
                if d < VISUAL_RANGE*0.3:
                    diff = self.position - other.position
                    if d > 0.001: diff /= d
                    sep += diff
        if count > 0:
            aln /= count; coh /= count
            if aln.length() > 0.001: aln.scale_to_length(V0)
            aln -= self.velocity
            if aln.length() > MAX_FORCE: aln.scale_to_length(MAX_FORCE)
            coh -= self.position
            if coh.length() > 0.001: coh.scale_to_length(V0)
            coh -= self.velocity
            if coh.length() > MAX_FORCE: coh.scale_to_length(MAX_FORCE)
            if sep.length() > 0.001: sep.scale_to_length(V0)
            sep -= self.velocity
            if sep.length() > MAX_FORCE: sep.scale_to_length(MAX_FORCE)
        na = random.uniform(0, 2*math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na)) * MAX_FORCE*0.8
        self.apply_force(sep * config.phi_p*2.0)
        self.apply_force(aln * config.phi_a*1.2)
        self.apply_force(coh * config.phi_n*1.5)
        self.apply_force(noise)

    def draw(self, screen, config):
        dir = math.atan2(self.velocity.y, self.velocity.x) if self.velocity.length_squared() > 0.001 else 0
        tip = self.position + pygame.Vector2(math.cos(dir), math.sin(dir)) * BOID_SIZE*2.5
        bl = self.position + pygame.Vector2(math.cos(dir+2.3), math.sin(dir+2.3)) * BOID_SIZE*1.5
        br = self.position + pygame.Vector2(math.cos(dir-2.3), math.sin(dir-2.3)) * BOID_SIZE*1.5
        c = (200,210,230) if config.mode == MODE_PROJECTION else (230,200,160)
        pygame.draw.polygon(screen, c, [tip, bl, br])


# ── Setup ──────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Iteration 6 — Dual-Mode Flocking")
clock = pygame.time.Clock()
config = Config()
grid = SpatialGrid()
flock = [Boid() for _ in range(NUM_BOIDS)]

# ── Main loop ──────────────────────────────────────────────────────
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: running = False
            elif event.key == pygame.K_m:
                config.mode = 1 - config.mode
                print(f"MODE: {'PROJECTION' if config.mode==MODE_PROJECTION else 'SPATIAL'}")

    grid.rebuild(flock)
    for b in flock: b.flock(flock, config, grid)
    for b in flock: b.update()

    screen.fill((20,22,30))
    for b in flock: b.draw(screen, config)
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit(); sys.exit()
