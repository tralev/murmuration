"""
╔══════════════════════════════════════════════════════════════════════╗
║  EXTENSION ORCHESTRATION — central hub for all extensions           ║
╚══════════════════════════════════════════════════════════════════════╝

 Single module that knows about every extension.  When you add a new
 extension, this is the only file (besides features.py, input_handler.py,
 and help_overlay.py) that needs to change — alg2.py and simulation.py
 stay untouched.

 Three public functions:

   init_ext_state()   → returns ext_state dict with all defaults
   apply_forces()     → called each frame between flock() and update()
   render()           → called each frame after the flock is drawn

 Flag-gated imports ensure disabled extensions are never loaded.
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame
from statistics import mean

import features


# ══════════════════════════════════════════════════════════════════════
#  Flag-gated imports — disabled extensions never load their module
# ══════════════════════════════════════════════════════════════════════

if features.ENABLE_THREAT:
    from extensions.threat import ThreatAgent, THREAT_RADIUS, THREAT_COLOR, flee_force

if features.ENABLE_WANDER:
    from extensions.wander import WanderConfig, flock_wander_center, wander_force

if features.ENABLE_ADAPTIVE_QUALITY:
    from extensions.adaptive_quality import AdaptiveQuality

if features.ENABLE_MEDIUM_PRESETS:
    from medium_presets import MediumConfig, MEDIUM_PRESETS

if features.ENABLE_FLOCK_SHAPE:
    from extensions.flock_shape import ShapeReport, analyze_shape

if features.ENABLE_LEADER:
    from extensions.leader import LeaderAnchor, LeaderConfig, leader_force, draw_anchors

if features.ENABLE_VACUOLE:
    from extensions.vacuole import VacuoleAgent, VacuoleConfig, vacuole_force, draw_vacuole

if features.ENABLE_SHELL:
    from extensions.shell_formation import ShellConfig, shell_force, draw_shells

if features.ENABLE_FLOW_FIELD:
    from extensions.flow_field import FlowConfig, flow_force, draw_flow


# ══════════════════════════════════════════════════════════════════════
#  ext_state initialisation
# ══════════════════════════════════════════════════════════════════════

def init_ext_state():
    """Return a dict with default values for every enabled extension.

    Called once at simulation startup by alg2.py.
    Mutations to the returned dict are tracked through the frame loop
    (input → update → render) so extensions can store per-frame state
    without global variables.
    """
    ext_state = {}

    if features.ENABLE_THREAT:
        ext_state['threat'] = None

    if features.ENABLE_WANDER:
        ext_state['wander_active'] = False
        ext_state['wander_cfg'] = WanderConfig()
        ext_state['wander_time'] = 0.0

    if features.ENABLE_ADAPTIVE_QUALITY:
        ext_state['aq'] = AdaptiveQuality()
        ext_state['aq_label'] = ""

    if features.ENABLE_MEDIUM_PRESETS:
        ext_state['medium'] = MediumConfig("grid")
        ext_state['medium_label'] = "MEDIUM grid"

    if features.ENABLE_H2_ROBUSTNESS:
        ext_state['h2_val'] = -1.0

    if features.ENABLE_SEASONAL:
        ext_state['seasonal_day'] = 1
        ext_state['seasonal_label'] = ""

    if features.ENABLE_FLOCK_SHAPE:
        ext_state['flock_shape'] = None

    if features.ENABLE_LEADER:
        ext_state['leader_active'] = False
        ext_state['leader_cfg'] = LeaderConfig()
        ext_state['leader_time'] = 0.0
        ext_state['leader_anchors'] = []

    if features.ENABLE_VACUOLE:
        ext_state['vacuole'] = None
        ext_state['vacuole_cfg'] = VacuoleConfig()
        ext_state['vacuole_time'] = 0.0

    if features.ENABLE_SHELL:
        ext_state['shell_active'] = False
        ext_state['shell_cfg'] = ShellConfig()
        ext_state['shell_time'] = 0.0
        ext_state['shell_assignments'] = []

    if features.ENABLE_FLOW_FIELD:
        ext_state['flow_active'] = False
        ext_state['flow_cfg'] = FlowConfig()
        ext_state['flow_time'] = 0.0
        ext_state['flow_gust'] = False
        ext_state['flow_gust_time'] = 0.0

    return ext_state


# ══════════════════════════════════════════════════════════════════════
#  Per-frame force application  (called from simulation.py)
# ══════════════════════════════════════════════════════════════════════

def apply_forces(flock, ext_state, clock):
    """Apply steering forces for all active extensions.

    Called each frame between flock() and update() in simulation.py.
    Mutates ext_state in place (time tracking, gust state, etc.) and
    applies forces directly to each boid via boid.apply_force().

    Parameters
    ----------
    flock     : list[Boid] — all birds
    ext_state : dict — mutable extension state (updated in place)
    clock     : pygame.time.Clock — for frame-rate-normalised timing
    """
    dt = 1.0 / max(clock.get_fps(), 1.0)

    # ── leader / attractor (O key) ────────────────────────────
    if features.ENABLE_LEADER and ext_state.get('leader_active'):
        cfg = ext_state.get('leader_cfg')
        ext_state['leader_time'] = ext_state.get('leader_time', 0.0) + dt
        for anchor in ext_state.get('leader_anchors', []):
            anchor.update(ext_state['leader_time'])
        for boid in flock:
            fx, fy = leader_force(boid.position, ext_state.get('leader_anchors', []), cfg)
            if fx != 0.0 or fy != 0.0:
                boid.apply_force(pygame.Vector2(fx, fy))

    # ── flow field (D key) ────────────────────────────────────
    if features.ENABLE_FLOW_FIELD and ext_state.get('flow_active'):
        cfg = ext_state.get('flow_cfg')
        ext_state['flow_time'] = ext_state.get('flow_time', 0.0) + dt
        # Gust management
        if ext_state.get('flow_gust'):
            ext_state['flow_gust_time'] = ext_state.get('flow_gust_time', 0.0) + dt
            if ext_state['flow_gust_time'] >= cfg.gust_duration:
                ext_state['flow_gust'] = False
                ext_state['flow_gust_time'] = 0.0
        elif random.random() < cfg.gust_chance * dt:
            ext_state['flow_gust'] = True
            ext_state['flow_gust_time'] = 0.0
        fx, fy = flow_force(cfg, ext_state['flow_time'],
                            ext_state.get('flow_gust', False),
                            ext_state.get('flow_gust_time', 0.0))
        for boid in flock:
            if fx != 0.0 or fy != 0.0:
                boid.apply_force(pygame.Vector2(fx, fy))

    # ── vacuole formation (E key) ─────────────────────────────
    if features.ENABLE_VACUOLE and ext_state.get('vacuole') is not None:
        vacuole = ext_state['vacuole']
        swarm_x = mean(b.position.x for b in flock)
        swarm_y = mean(b.position.y for b in flock)
        ext_state['vacuole_time'] = ext_state.get('vacuole_time', 0.0) + dt
        vacuole.update((swarm_x, swarm_y), ext_state['vacuole_time'])
        cfg = ext_state.get('vacuole_cfg')
        for boid in flock:
            fx, fy = vacuole_force(boid.position, vacuole.position(), cfg)
            if fx != 0.0 or fy != 0.0:
                boid.apply_force(pygame.Vector2(fx, fy))

    # ── shell formation (P key) ───────────────────────────────
    if features.ENABLE_SHELL and ext_state.get('shell_active'):
        cfg = ext_state.get('shell_cfg')
        ext_state['shell_time'] = ext_state.get('shell_time', 0.0) + dt
        swarm_x = mean(b.position.x for b in flock)
        swarm_y = mean(b.position.y for b in flock)
        assignments = ext_state.get('shell_assignments', [])
        t = ext_state['shell_time']
        for i, boid in enumerate(flock):
            if i < len(assignments):
                sidx, phase, direction = assignments[i]
                fx, fy = shell_force(
                    boid.position, (swarm_x, swarm_y),
                    sidx, phase, direction, t, cfg)
                if fx != 0.0 or fy != 0.0:
                    boid.apply_force(pygame.Vector2(fx, fy))

    # ── wander behaviour (W key) ──────────────────────────────
    if features.ENABLE_WANDER and ext_state.get('wander_active'):
        ext_state['wander_time'] = ext_state.get('wander_time', 0.0) + dt
        centre = flock_wander_center(
            ext_state['wander_time'], ext_state.get('wander_cfg'))
        for boid in flock:
            fx, fy = wander_force(boid.position, centre, ext_state.get('wander_cfg'))
            boid.apply_force(pygame.Vector2(fx, fy))

    # ── threat agent (T key) ──────────────────────────────────
    if features.ENABLE_THREAT and ext_state.get('threat') is not None:
        threat = ext_state['threat']
        swarm_x = mean(b.position.x for b in flock)
        swarm_y = mean(b.position.y for b in flock)
        threat.update((swarm_x, swarm_y))
        for boid in flock:
            fx, fy = flee_force(boid.position, threat.position())
            if fx != 0.0 or fy != 0.0:
                boid.apply_force(pygame.Vector2(fx, fy))

    # ── medium presets (N key) ────────────────────────────────
    if features.ENABLE_MEDIUM_PRESETS:
        medium = ext_state.get('medium')
        if medium is not None and medium.name != 'grid':
            dvx, dvy = medium.drift_velocity()
            for boid in flock:
                tax, tay = medium.turbulence_accel()
                boid.apply_force(pygame.Vector2(tax + dvx, tay + dvy))

    # ── flock shape analysis (Y key — per frame) ──────────────
    if features.ENABLE_FLOCK_SHAPE:
        ext_state['flock_shape'] = analyze_shape(flock)

    # ── adaptive quality (A key) ──────────────────────────────
    if features.ENABLE_ADAPTIVE_QUALITY:
        aq = ext_state.get('aq')
        if aq is not None and aq.enabled:
            fps_val = max(clock.get_fps(), 1.0)
            now_ms = pygame.time.get_ticks()
            aq.update(fps_val, now_ms, len(flock))
            ext_state['aq_label'] = f"AQ tier {aq.tier}"


# ══════════════════════════════════════════════════════════════════════
#  Extension rendering  (called from alg2.py)
# ══════════════════════════════════════════════════════════════════════

def render(screen, ext_state, flock, font_small):
    """Render visual overlays for all active extensions.

    Called each frame after the flock is drawn in alg2.py.
    Reads ext_state; does not mutate it.

    Parameters
    ----------
    screen     : pygame.Surface
    ext_state  : dict — extension state (read-only)
    flock      : list[Boid] — needed for shell centre and flock_shape
    font_small : pygame.font.Font — for text overlays
    """
    # ── Threat agent ──────────────────────────────────────────
    if features.ENABLE_THREAT and ext_state.get('threat') is not None:
        ext_state['threat'].draw(screen, None)

    # ── Adaptive quality badge ────────────────────────────────
    if features.ENABLE_ADAPTIVE_QUALITY and ext_state.get('aq_label'):
        aq_surf = font_small.render(ext_state['aq_label'], True, (200, 160, 80))
        screen.blit(aq_surf, (10, 10))

    # ── Medium label ──────────────────────────────────────────
    if features.ENABLE_MEDIUM_PRESETS:
        med_label = ext_state.get('medium_label', '')
        if med_label:
            med_surf = font_small.render(med_label, True, (160, 200, 220))
            screen.blit(med_surf, (10, 28))

    # ── Seasonal label ────────────────────────────────────────
    if features.ENABLE_SEASONAL and ext_state.get('seasonal_label'):
        seas_surf = font_small.render(ext_state['seasonal_label'], True, (140, 200, 140))
        screen.blit(seas_surf, (10, 46))

    # ── Flock shape report ────────────────────────────────────
    if features.ENABLE_FLOCK_SHAPE and ext_state.get('flock_shape') is not None:
        sr = ext_state['flock_shape']
        shape_surf = font_small.render(
            f"aspect={sr.aspect_ratio:.1f}  orient={math.degrees(sr.orientation):.0f}°  m*={sr.suggested_m:.1f}",
            True, (180, 220, 160))
        screen.blit(shape_surf, (10, 64))

    # ── Leader anchors ────────────────────────────────────────
    if features.ENABLE_LEADER and ext_state.get('leader_active'):
        draw_anchors(screen, ext_state['leader_anchors'], ext_state.get('leader_cfg'))

    # ── Vacuole cavity ────────────────────────────────────────
    if features.ENABLE_VACUOLE and ext_state.get('vacuole') is not None:
        draw_vacuole(screen, ext_state['vacuole'], ext_state.get('vacuole_cfg'))

    # ── Shell rings ───────────────────────────────────────────
    if features.ENABLE_SHELL and ext_state.get('shell_active') and len(flock) > 0:
        cx = mean(b.position.x for b in flock)
        cy = mean(b.position.y for b in flock)
        draw_shells(screen, (cx, cy), ext_state.get('shell_cfg'))

    # ── Flow field wind indicator ─────────────────────────────
    if features.ENABLE_FLOW_FIELD and ext_state.get('flow_active'):
        draw_flow(screen, ext_state.get('flow_cfg'),
                  ext_state.get('flow_time', 0.0),
                  ext_state.get('flow_gust', False))
