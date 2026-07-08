"""
╔══════════════════════════════════════════════════════════════════════╗
║  EXTENSION INPUT — keyboard toggles for the optional extensions       ║
╚══════════════════════════════════════════════════════════════════════╝

 Why this module exists
 ──────────────────────
 The core 2D input handler (`input_handler.py`) owns the *fixed*
 controls — presets, mode, φ/σ tuning, boid count, pause/reset, focal
 bird. Every *optional* extension (threat, wander, leader, …) also
 wants a key, but wiring those into the core handler made it grow a
 branch per extension and forced an edit to core code every time a new
 extension was added.

 This module holds all of that extension key handling in one place, so:

   • the core input handler stays extension-agnostic — it delegates any
     unrecognised key here with a single call;
   • adding a new extension touches only the extension side (this file
     + orchestration.py + features.py), never the core loop;
   • a disabled extension (its `features.ENABLE_*` flag off) simply does
     not claim its key — the key falls through and does nothing, so any
     subset of extensions can be enabled independently.

 Each handler below is labelled with the feature it toggles and the key
 that triggers it. Extension modules are imported lazily inside each
 branch (not at module load) so a disabled extension is never imported
 and the flag can be flipped at runtime in tests.

 Dependencies:  pygame (key constants), features (ENABLE_* flags)
──────────────────────────────────────────────────────────────────────
"""

import pygame

import features


def handle_ext_key(key, config, flock, ext_state) -> bool:
    """Dispatch a KEYDOWN to the extension that owns *key*.

    Parameters
    ----------
    key       : int — the pygame key constant from the KEYDOWN event
    config    : Config — read for parameters (e.g. σ for the H₂ metric)
    flock     : list[Boid] — read by extensions that seed from positions
    ext_state : dict — mutated in place to store per-extension state

    Returns
    -------
    bool — True if an *enabled* extension consumed the key (so the core
    handler should stop), False otherwise (key falls through unchanged).
    """
    # ── T — Threat agent (Roadmap 7): spawn/remove a predator the flock
    #        flees from, with escape-wave propagation. ────────────────
    if key == pygame.K_t and features.ENABLE_THREAT:
        from extensions.threat import ThreatAgent
        if ext_state.get('threat') is None:
            ext_state['threat'] = ThreatAgent()
            print("Threat agent SPAWNED — birds will flee!")
        else:
            ext_state['threat'] = None
            print("Threat agent REMOVED")
        return True

    # ── W — Wander (Roadmap 10c): toggle the shared moving attractor
    #        that makes the flock explore when idle. ─────────────────
    if key == pygame.K_w and features.ENABLE_WANDER:
        ext_state['wander_active'] = not ext_state.get('wander_active', False)
        print(f"Wander behaviour: {'ON' if ext_state['wander_active'] else 'OFF'}")
        return True

    # ── A — Adaptive quality (Roadmap 15): toggle FPS-driven quality
    #        degradation on/off. ───────────────────────────────────
    if key == pygame.K_a and features.ENABLE_ADAPTIVE_QUALITY:
        aq = ext_state.get('aq')
        if aq is not None:
            enabled = aq.toggle()
            print(f"Adaptive quality: {'ON' if enabled else 'OFF (full quality)'}")
            ext_state['aq_label'] = f"AQ tier {aq.tier}" if enabled else ""
        return True

    # ── N — Medium presets (companion mediumPresets): cycle the ambient
    #        medium (grid → air → dust → starlight → …). ────────────
    if key == pygame.K_n and features.ENABLE_MEDIUM_PRESETS:
        from medium_presets import apply_medium, MEDIUM_PRESETS
        medium = ext_state.get('medium')
        if medium is not None:
            names = list(MEDIUM_PRESETS)
            nxt = names[(names.index(medium.name) + 1) % len(names)]
            ext_state['medium_label'] = apply_medium(medium, nxt)
            print(ext_state['medium_label'])
        return True

    # ── J — H₂ robustness (Roadmap 6): one-shot readout of the consensus
    #        robustness norm and cost-optimal neighbour count m*. ───
    if key == pygame.K_j and features.ENABLE_H2_ROBUSTNESS:
        from extensions.h2_robustness import h2_norm, cost_optimal_m
        positions = [(b.position.x, b.position.y) for b in flock]
        ext_state['h2_val'] = h2_norm(positions, config.sigma)
        best_m, _ = cost_optimal_m(positions)
        print(f"H₂={ext_state['h2_val']:.4f}  cost-optimal m*={best_m}")
        return True

    # ── C — Seasonal (Roadmap 5): advance the day-of-year to sample the
    #        Goodenough seasonal flock-size curve. ─────────────────
    if key == pygame.K_c and features.ENABLE_SEASONAL:
        from extensions.seasonal import seasonal_size_factor
        day = (ext_state.get('seasonal_day', 1) % 365) + 30   # jump 30 days
        ext_state['seasonal_day'] = day
        factor = seasonal_size_factor(day)
        ext_state['seasonal_label'] = f"Day {day}: flock factor {factor:.2f}"
        print(ext_state['seasonal_label'])
        return True

    # ── Y — Flock shape (Roadmap 6): the analysis runs every frame in
    #        simulation.py; the key just acknowledges the feature. ──
    if key == pygame.K_y and features.ENABLE_FLOCK_SHAPE:
        return True

    # ── O — Leader / attractor (Priority 5): spawn/remove Lissajous
    #        anchor points the flock is drawn toward. ──────────────
    if key == pygame.K_o and features.ENABLE_LEADER:
        if ext_state.get('leader_active'):
            ext_state['leader_active'] = False
            ext_state['leader_anchors'] = []
            print("Leader system: OFF")
        else:
            from extensions.leader import LeaderAnchor, LeaderConfig
            cfg = ext_state.get('leader_cfg', LeaderConfig())
            ext_state['leader_active'] = True
            ext_state['leader_anchors'] = [
                LeaderAnchor(config=cfg) for _ in range(cfg.anchor_count)]
            ext_state['leader_time'] = 0.0
            print(f"Leader system: ON ({cfg.anchor_count} anchor(s))")
        return True

    # ── D — Flow field (Priority 10b): toggle an environmental wind /
    #        drift field with gusts. ──────────────────────────────
    if key == pygame.K_d and features.ENABLE_FLOW_FIELD:
        from extensions.flow_field import FlowConfig
        if ext_state.get('flow_active'):
            ext_state['flow_active'] = False
            print("Flow field DISABLED")
        else:
            cfg = ext_state.get('flow_cfg', FlowConfig())
            ext_state['flow_cfg'] = cfg
            ext_state['flow_active'] = True
            ext_state['flow_time'] = 0.0
            ext_state['flow_gust'] = False
            ext_state['flow_gust_time'] = 0.0
            print(f"Flow field ENABLED — wind angle {cfg.wind_angle:.2f} rad")
        return True

    # ── E — Vacuole (Priority 5): spawn/remove an orbiting repulsor that
    #        carves a moving cavity in the flock. ─────────────────
    if key == pygame.K_e and features.ENABLE_VACUOLE:
        from extensions.vacuole import VacuoleAgent, VacuoleConfig
        if ext_state.get('vacuole') is None:
            cfg = ext_state.get('vacuole_cfg', VacuoleConfig())
            ext_state['vacuole'] = VacuoleAgent(config=cfg)
            ext_state['vacuole_time'] = 0.0
            print("Vacuole SPAWNED — birds will be pushed outward!")
        else:
            ext_state['vacuole'] = None
            print("Vacuole REMOVED")
        return True

    # ── P — Shell formation (Priority 5): toggle birds orbiting the
    #        leader in concentric geometric shells. ───────────────
    if key == pygame.K_p and features.ENABLE_SHELL:
        from extensions.shell_formation import ShellConfig, assign_shells
        if ext_state.get('shell_active'):
            ext_state['shell_active'] = False
            ext_state['shell_assignments'] = []
            print("Shell formation: OFF")
        else:
            cfg = ext_state.get('shell_cfg', ShellConfig())
            ext_state['shell_active'] = True
            ext_state['shell_time'] = 0.0
            ext_state['shell_assignments'] = assign_shells(flock, cfg)
            print(f"Shell formation: ON ({len(cfg.radii)} shells, "
                  f"{len(flock)} birds)")
        return True

    # Key not owned by any enabled extension — let the core handler have it.
    return False
