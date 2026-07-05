"""
╔══════════════════════════════════════════════════════════════════════╗
║  DATA LOADER — Real-World 3D Starling Trajectory Analysis           ║
╚══════════════════════════════════════════════════════════════════════╝

 Parse empirical 3D starling trajectory data (e.g., from Ballerini
 et al. 2008, or the STARFLAG dataset) and compute marginal opacity
 using the project's occlusion algorithms.

 Supported formats:
   - CSV:  frame, bird_id, x, y, z, vx, vy, vz
   - Simple:  x y z vx vy vz  (space-separated, per-frame blocks)

 Usage:
   from extensions.data_loader import load_trajectories, compute_opacity

   trajectories = load_trajectories("starling_data.csv")
   opacity = compute_opacity(trajectories, frame=42)
──────────────────────────────────────────────────────────────────────
"""

import csv
import math
import os


def load_trajectories(filepath: str) -> dict:
    """
    Load 3D bird trajectories from a CSV file.

    Expected CSV columns (header row required):
      frame, bird_id, x, y, z, vx, vy, vz

    Returns dict mapping frame_number → list of bird dicts:
      {
        0: [{"id": 1, "x": 100.0, "y": 200.0, "z": 50.0,
             "vx": 1.0, "vy": 0.5, "vz": 0.0}, ...],
        1: [...],
        ...
      }

    Complexity: O(N_rows) — single pass through the CSV.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Trajectory file not found: {filepath}")

    frames = {}

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)

        # Validate header
        required_cols = {'frame', 'bird_id', 'x', 'y', 'z', 'vx', 'vy', 'vz'}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            missing = required_cols - set(reader.fieldnames or [])
            raise ValueError(
                f"CSV missing required columns: {missing}. "
                f"Expected: frame,bird_id,x,y,z,vx,vy,vz"
            )

        for row in reader:
            frame = int(row['frame'])
            bird = {
                'id': int(row['bird_id']),
                'x': float(row['x']),
                'y': float(row['y']),
                'z': float(row['z']),
                'vx': float(row['vx']),
                'vy': float(row['vy']),
                'vz': float(row['vz']),
            }
            if frame not in frames:
                frames[frame] = []
            frames[frame].append(bird)

    return frames


def compute_opacity(trajectories: dict, frame: int,
                    bird_radius: float = 3.0) -> dict:
    """
    Compute marginal opacity (internal Θ and external Θ') for a
    specific frame from loaded trajectory data.

    Uses the project's angular interval occlusion algorithm
    (occlusion_geom) applied to the 2D projection of 3D positions
    onto the x-y plane.

    ── ALGORITHM ──

    For each bird i:
      1. Project all other birds onto the x-y plane.
      2. Compute angular intervals [centre−half, centre+half]
         for each other bird, where:
           centre = atan2(y_j − y_i,  x_j − x_i)
           half   = asin(bird_radius / d_ij)
      3. Merge intervals closest-first (occlusion).
      4. Θ_i = (sum of merged widths) / 2π — internal opacity.
      5. Average Θ_i over all birds → Θ (global internal opacity).

    For external opacity Θ':
      1. Place 12 observers on a circle of radius 2000 in the x-y plane.
      2. For each observer, compute angular intervals to all birds
         and merge them.
      3. Θ' = average fraction of 2π occluded across observers.

    Parameters
    ----------
    trajectories : dict — from load_trajectories()
    frame : int — which frame to analyse
    bird_radius : float — effective bird radius (default 3.0)

    Returns
    -------
    dict with keys:
      theta      — mean internal opacity Θ
      theta_ext  — mean external opacity Θ' (multi-viewpoint)
      alpha      — order parameter (alignment)
      n_birds    — number of birds in this frame
    """
    from occlusion_geom import _normalise_interval, _merge_all

    if frame not in trajectories:
        raise ValueError(f"Frame {frame} not found in trajectories")

    birds = trajectories[frame]
    n = len(birds)
    if n == 0:
        return {'theta': 0.0, 'theta_ext': 0.0, 'alpha': 0.0, 'n_birds': 0}

    # ═══════════════════════════════════════════════════════════════
    #  Internal opacity Θ — per-bird angular occlusion
    # ═══════════════════════════════════════════════════════════════
    #  For each bird, compute the fraction of 2π occluded by all
    #  other birds.  Average across the flock.

    theta_sum = 0.0

    for i, bird_i in enumerate(birds):
        intervals = []
        xi, yi = bird_i['x'], bird_i['y']

        for j, bird_j in enumerate(birds):
            if i == j:
                continue
            xj, yj = bird_j['x'], bird_j['y']
            dx = xj - xi
            dy = yj - yi
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.001:
                continue

            centre = math.atan2(dy, dx)
            if centre < 0:
                centre += 2 * math.pi
            half = math.asin(min(bird_radius / dist, 1.0))
            intervals.extend(
                _normalise_interval(centre - half, centre + half)
            )

        if intervals:
            merged = _merge_all(intervals)
            occluded = sum(e - s for s, e in merged)
            theta_i = min(occluded / (2 * math.pi), 1.0)
        else:
            theta_i = 0.0

        theta_sum += theta_i

    theta = theta_sum / n

    # ═══════════════════════════════════════════════════════════════
    #  External opacity Θ' — multi-viewpoint (K=12)
    # ═══════════════════════════════════════════════════════════════

    K = 12
    R_ext = 2000
    theta_ext_sum = 0.0

    for k in range(K):
        angle = 2 * math.pi * k / K
        vx = R_ext * math.cos(angle)
        vy = R_ext * math.sin(angle)

        intervals = []
        for bird in birds:
            dx = bird['x'] - vx
            dy = bird['y'] - vy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.001:
                continue
            centre = math.atan2(dy, dx)
            if centre < 0:
                centre += 2 * math.pi
            half = math.asin(min(bird_radius / dist, 1.0))
            intervals.extend(
                _normalise_interval(centre - half, centre + half)
            )

        if intervals:
            merged = _merge_all(intervals)
            occluded = sum(e - s for s, e in merged)
            theta_ext_sum += min(occluded / (2 * math.pi), 1.0)

    theta_ext = theta_ext_sum / K

    # ═══════════════════════════════════════════════════════════════
    #  Order parameter α — degree of flock alignment
    # ═══════════════════════════════════════════════════════════════
    #  α = |Σ v_i| / (N · v₀)  where v₀ is the mean speed.

    sum_vx = sum(b['vx'] for b in birds)
    sum_vy = sum(b['vy'] for b in birds)
    sum_vz = sum(b['vz'] for b in birds)
    total_speed = math.sqrt(sum_vx**2 + sum_vy**2 + sum_vz**2)

    mean_speed = sum(
        math.sqrt(b['vx']**2 + b['vy']**2 + b['vz']**2)
        for b in birds
    ) / n

    alpha = total_speed / (n * mean_speed) if mean_speed > 0 else 0.0

    return {
        'theta': theta,
        'theta_ext': theta_ext,
        'alpha': alpha,
        'n_birds': n,
    }


def compute_opacity_timeseries(trajectories: dict,
                                bird_radius: float = 3.0) -> list:
    """
    Compute opacity metrics for ALL frames in the trajectory dataset.

    Returns list of dicts sorted by frame number, each with:
      frame, theta, theta_ext, alpha, n_birds

    Useful for generating opacity time series plots from real data.

    Complexity: O(F · N² log N) where F = number of frames,
    N = birds per frame.
    """
    results = []
    for frame in sorted(trajectories.keys()):
        metrics = compute_opacity(trajectories, frame, bird_radius)
        metrics['frame'] = frame
        results.append(metrics)
    return results


def load_simple_format(filepath: str, bird_radius: float = 3.0) -> dict:
    """
    Load trajectories from a simple space-separated format.

    Each frame block:
      <num_birds>
      x y z vx vy vz
      x y z vx vy vz
      ...

    Parameters
    ----------
    filepath : str — path to data file
    bird_radius : float — effective bird radius

    Returns
    -------
    dict — same format as load_trajectories()
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    frames = {}
    frame = 0
    birds_in_frame = []
    reading_birds = False
    birds_expected = 0

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) == 1:
                # New frame header: number of birds
                if reading_birds and birds_in_frame:
                    frames[frame] = birds_in_frame
                    frame += 1
                birds_expected = int(parts[0])
                birds_in_frame = []
                reading_birds = True
            elif len(parts) >= 6 and reading_birds:
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                vx, vy, vz = float(parts[3]), float(parts[4]), float(parts[5])
                birds_in_frame.append({
                    'id': len(birds_in_frame) + 1,
                    'x': x, 'y': y, 'z': z,
                    'vx': vx, 'vy': vy, 'vz': vz,
                })
                if len(birds_in_frame) >= birds_expected:
                    frames[frame] = birds_in_frame
                    frame += 1
                    birds_in_frame = []
                    reading_birds = False

    return frames
