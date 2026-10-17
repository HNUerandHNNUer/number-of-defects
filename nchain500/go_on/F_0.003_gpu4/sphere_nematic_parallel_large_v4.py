#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spherical nematic topology, deterministic subprocess parallel implementation.

Publishes results/defect_results.dat, results/delaunay.dat and
<input-dir>/defect_out/defect_out-*.xyz (particles plus charged-face markers).
Spyder and command line both launch ordinary persistent Python subprocesses.
No fork, multiprocessing pickle, Numba, random recovery or inserted charge.
No 0.5-radian hard rejection: large edges are sampling warnings only.
Undefined geometry/directors still fail rather than fabricate valid results.

Default: 30 beads/chain, center=(0,0,0), resource-bounded automatic workers,
600 seconds maximum per frame. See settings below and --help.
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
              'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
from dataclasses import dataclass, asdict
import glob
import fnmatch
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
import traceback

import numpy as np
import scipy
from scipy.spatial import ConvexHull, cKDTree
try:
    from scipy.spatial import QhullError
except ImportError:
    # Older SciPy releases expose this exception only in the qhull module.
    from scipy.spatial.qhull import QhullError

VERSION = '2.0.0'
RUNTIME_REVISION = 'large-io-v4'


class ValidationError(ValueError):
    """Input or discrete topological construction cannot be certified."""


@dataclass(frozen=True)
class Settings:
    chain_length: int = 30
    director_source: str = 'chains'
    center: tuple = (0.0, 0.0, 0.0)
    max_radial_deviation: float = 0.02
    duplicate_tolerance: float = 1e-10
    min_tangent_norm: float = 1e-12
    tangent_tolerance: float = 1e-8
    quantization_tolerance: float = 1e-8
    area_tolerance: float = 1e-8
    max_edge_angle: float = float(np.pi)
    branch_tolerance: float = 1e-10
    warn_edge_margin: float = 0.05
    smooth_k: int = 0
    smooth_length: float = 0.0
    low_order_warning: float = 0.2
    save_mesh: bool = False


def dot(a, b):
    return np.einsum('...i,...i->...', a, b)


def unit(v, threshold=1e-12, label='vector'):
    v = np.asarray(v, dtype=np.float64)
    norms = np.linalg.norm(v, axis=-1)
    if not np.isfinite(v).all() or np.any(norms <= threshold):
        raise ValidationError(f'Undefined/non-finite {label}; no arbitrary direction substituted')
    return v / norms[..., None]


def parallel_transport(v, a, b):
    """Exact Levi-Civita transport along the minor great-circle arc a -> b.

    a,b: unit radial vectors; v tangent at a. Supports broadcasting.
    PT(v) = v - (v.b)/(1+a.b) * (a+b).
    """
    denominator = 1.0 + dot(a, b)
    if np.any(denominator <= 1e-12):
        raise ValidationError('Antipodal/near-antipodal transport is ambiguous')
    return v - (dot(v, b) / denominator)[..., None] * (a + b)


def sphere_geometry(coords, settings):
    coords = np.asarray(coords, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 3 or len(coords) < 4:
        raise ValidationError('Need at least four 3D surface points')
    if not np.isfinite(coords).all():
        raise ValidationError('Non-finite positions')
    center = np.asarray(settings.center, dtype=np.float64)
    displacement = coords - center
    scale = float(np.max(np.abs(displacement)))
    if not np.isfinite(scale) or scale == 0:
        raise ValidationError('Zero/non-finite coordinate scale')
    # Work on a dimensionless sphere: no fixed physical radius cutoff.
    displacement = displacement / scale
    lengths = np.linalg.norm(displacement, axis=1)
    if np.any(lengths == 0):
        raise ValidationError('A particle coincides with the specified sphere center')
    mean_length = float(lengths.mean())
    radius = mean_length * scale
    deviation = float(np.max(np.abs(lengths / mean_length - 1)))
    if deviation > settings.max_radial_deviation:
        raise ValidationError(f'Not a sufficiently thin sphere about the supplied center: '
                              f'max radial deviation={deviation:.6g}; '
                              f'limit={settings.max_radial_deviation}')
    u = displacement / lengths[:, None]
    nearest, _ = cKDTree(u).query(u, k=2)
    if float(nearest[:, 1].min()) <= settings.duplicate_tolerance:
        raise ValidationError('Duplicate/nearly coincident angular samples; not jittered or dropped')
    return u, radius, deviation


def chain_directors(u, chain_length, settings):
    """Same central/end differences as old code, with undefined vectors rejected.

    Rows MUST be consecutive beads on consecutive chains. No arbitrary reshaping
    inferred from particle count, no silent remainder, no guessed chain ordering.
    """
    if chain_length < 2 or len(u) % chain_length:
        raise ValidationError('Particle count must be divisible by chain_length >= 2')
    chains = u.reshape(-1, chain_length, 3)
    t = np.empty_like(chains)
    t[:, 0] = chains[:, 1] - chains[:, 0]
    t[:, -1] = chains[:, -1] - chains[:, -2]
    t[:, 1:-1] = 0.5 * (chains[:, 2:] - chains[:, :-2])
    t = t.reshape(-1, 3)
    t -= dot(t, u)[:, None] * u
    return unit(t, settings.min_tangent_norm, 'chain tangent')


def validate_directors(directors, u, settings):
    d = unit(directors, settings.min_tangent_norm, 'director')
    if d.shape != u.shape:
        raise ValidationError('Director and coordinate shapes differ')
    radial = dot(d, u)
    if np.max(np.abs(radial)) > settings.tangent_tolerance:
        raise ValidationError('Supplied directors are not tangent to the sphere')
    return unit(d - radial[:, None] * u, settings.min_tangent_norm, 'tangent director')


def coarse_grain(u, d, radius, settings):
    """Optional sign-invariant Q average in transported tangent planes.

    Deliberately OFF by default. Both k and physical Gaussian length must be
    supplied. This changes the measured field and requires a scale study.
    No masking or filling of undefined/zero order is performed.
    """
    if settings.smooth_k == 0:
        return d, np.ones(len(u), dtype=np.float64)
    k = settings.smooth_k
    if not 2 <= k <= min(256, len(u)) or settings.smooth_length <= 0:
        raise ValidationError('Smoothing requires 2 <= k <= min(256,N) and positive length')
    distances, ids = cKDTree(u).query(u, k=k)
    basis = np.eye(3)[np.argmin(np.abs(u), axis=1)]
    e1 = unit(np.cross(u, basis))
    e2 = np.cross(u, e1)
    output = np.empty_like(d)
    order = np.empty(len(u))
    # Batches bound temporary memory independently of N*k.
    for start in range(0, len(u), 2048):
        stop = min(start + 2048, len(u))
        ix = ids[start:stop]
        target = u[start:stop, None, :]
        transported = parallel_transport(d[ix], u[ix], target)
        x = dot(transported, e1[start:stop, None, :])
        y = dot(transported, e2[start:stop, None, :])
        arc = radius * 2 * np.arcsin(np.clip(distances[start:stop] / 2, 0, 1))
        weights = np.exp(-0.5 * (arc / settings.smooth_length) ** 2)
        denom = weights.sum(axis=1)
        real = (weights * (x*x - y*y)).sum(axis=1) / denom
        imag = (weights * (2*x*y)).sum(axis=1) / denom
        s = np.hypot(real, imag)
        if np.any(s <= settings.min_tangent_norm):
            raise ValidationError('Coarse-grained Q vanishes at a vertex; director undefined')
        angle = 0.5 * np.arctan2(imag, real)
        output[start:stop] = (np.cos(angle)[:, None] * e1[start:stop] +
                              np.sin(angle)[:, None] * e2[start:stop])
        order[start:stop] = s
    return output, order


def build_mesh(u, settings):
    """Closed, outward spherical Delaunay triangulation via the convex hull.

    No random Qhull joggle. Every point must be a hull vertex. The origin must
    lie strictly inside; hemispherical data are rejected. Smaller unobserved
    gaps below the edge-length threshold are necessarily interpolated.
    """
    try:
        hull = ConvexHull(u)
    except QhullError as exc:
        raise ValidationError(f'Cannot construct a nondegenerate spherical hull: {exc}') from exc
    if len(hull.vertices) != len(u):
        raise ValidationError('Not every sample is a distinct hull vertex')
    if np.any(hull.equations[:, 3] >= -settings.duplicate_tolerance):
        raise ValidationError('Sphere center is not strictly inside hull; coverage is incomplete')
    faces = hull.simplices.astype(np.int64, copy=True)
    a, b, c = (u[faces[:, i]] for i in range(3))
    orientation = dot(a, np.cross(b, c))
    swap = orientation < 0
    faces[swap, 1], faces[swap, 2] = faces[swap, 2].copy(), faces[swap, 1].copy()
    # Canonical cyclic rotation + sorting keeps output stable under face enumeration.
    first = np.argmin(faces, axis=1)
    faces = np.take_along_axis(faces, (first[:, None] + np.arange(3)) % 3, axis=1)
    faces = faces[np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0]))]
    directed = np.stack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=1)
    sign = np.where(directed[..., 0] < directed[..., 1], 1, -1)
    pairs = np.sort(directed.reshape(-1, 2), axis=1)
    # A bijective integer key preserves EXACTLY the old lexicographic edge order.
    # Scalar sorting avoids NumPy's expensive structured-row unique(axis=0).
    n_vertices = len(u)
    if n_vertices <= 3037000499:  # n_vertices**2 fits in signed int64
        keys = pairs[:, 0] * n_vertices + pairs[:, 1]
        unique, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
        edges = np.column_stack((unique // n_vertices, unique % n_vertices))
    else:
        edges, inverse, counts = np.unique(pairs, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.reshape(-1, 3)
    incidence = np.bincount(inverse.ravel(), weights=sign.ravel(), minlength=len(edges))
    chi = len(u) - len(edges) + len(faces)
    if np.any(counts != 2) or np.any(incidence != 0) or chi != 2:
        raise ValidationError('Mesh is not a consistently oriented closed sphere (chi != 2)')
    a, b, c = (u[faces[:, i]] for i in range(3))
    area = 2 * np.arctan2(dot(a, np.cross(b, c)),
                          1.0 + dot(a, b) + dot(b, c) + dot(c, a))
    if np.any(area <= 0) or np.any(area >= 2*np.pi):
        raise ValidationError('Degenerate or excessively large spherical face')
    if abs(float(area.sum()) - 4 * np.pi) > settings.area_tolerance:
        raise ValidationError('Spherical face areas do not sum to 4*pi')
    edge_angle = np.arccos(np.clip(dot(u[edges[:, 0]], u[edges[:, 1]]), -1, 1))
    return faces, edges, inverse, sign, area, edge_angle


def identify(coords, directors=None, settings=None):
    """Return discrete face defects and numerical/resolution diagnostics.

    For each canonical edge i<j compute a SINGLE nematic angle delta_ij and
    reuse delta_ji=-delta_ij on the other incident face. For an outward face:
        q_f = (sum_boundary(delta) + Omega_f) / (2*pi).
    Omega_f is the exact solid angle, not an empirical charge correction.
    Each q_f must already be a half integer to within roundoff tolerance.
    """
    settings = settings or Settings()
    u, radius, deviation = sphere_geometry(coords, settings)
    if directors is None:
        d = chain_directors(u, settings.chain_length, settings)
    else:
        d = validate_directors(directors, u, settings)
    d, order = coarse_grain(u, d, radius, settings)
    faces, edges, inverse, sign, area, angles = build_mesh(u, settings)
    i, j = edges.T
    transported = parallel_transport(d[i], u[i], u[j])
    cosine = dot(transported, d[j])
    sine = dot(u[j], np.cross(transported, d[j]))
    delta = 0.5 * np.arctan2(2 * sine * cosine, cosine*cosine - sine*sine)
    margin = np.pi / 2 - np.abs(delta)
    if np.any(margin <= settings.branch_tolerance):
        raise ValidationError('An edge has an ambiguous nematic 90-degree rotation; '
                              'refine sampling or supply resolved directors, not a guessed branch')
    face_delta = np.sum(sign * delta[inverse], axis=1)
    q_raw = (face_delta + area) / (2 * np.pi)
    double_charge = np.rint(2 * q_raw).astype(np.int64)
    residual = np.abs(q_raw - 0.5 * double_charge)
    if float(residual.max()) > settings.quantization_tolerance:
        raise ValidationError(f'Non-half-integer local index: residual={residual.max():.6g}')
    # Assertion, not repair. NEVER change a charge to force this equality.
    if int(double_charge.sum()) != 4:
        raise ValidationError('Quantized net charge is not +2; no charge was added/removed')
    edge_cancellation = float(face_delta.sum())
    if abs(edge_cancellation) > settings.area_tolerance:
        raise ValidationError('Shared-edge rotations failed to cancel')
    mask = double_charge != 0
    centers = unit(u[faces].sum(axis=1)) * radius + np.asarray(settings.center)
    face_margin = margin[inverse].min(axis=1)
    face_order = order[faces].min(axis=1)
    warnings = []
    if float(angles.max()) > 0.5:
        warnings.append('Sparse angular sampling: max edge exceeds 0.5 rad; not a radius failure')
    if np.any(margin < settings.warn_edge_margin):
        warnings.append('Near-90-degree edges: indices may change under small director perturbations')
    if settings.smooth_k and np.any(order < settings.low_order_warning):
        warnings.append('Low coarse-grained nematic order: the local director is poorly resolved')
    if np.any(np.abs(double_charge) > 1):
        warnings.append('Composite face charge: refine before interpreting a physical core count')
    diag = {
        'status': 'topology_valid_with_warnings' if warnings else 'topology_valid',
        'physical_accuracy_certified': False,
        'field_definition': 'transported_Q_smoothed' if settings.smooth_k else 'unsmoothed_directors',
        'n_vertices': len(u), 'n_edges': len(edges), 'n_faces': len(faces), 'euler_characteristic': 2,
        'radius': radius, 'max_relative_radial_deviation': deviation,
        'sum_solid_angle': float(area.sum()), 'edge_rotation_cancellation': edge_cancellation,
        'max_quantization_residual': float(residual.max()), 'net_charge_raw': float(q_raw.sum()),
        'net_charge': float(0.5 * double_charge.sum()), 'charged_faces': int(mask.sum()),
        'max_edge_angle_rad': float(angles.max()), 'minimum_branch_margin_rad': float(margin.min()),
        'near_branch_edges': int(np.count_nonzero(margin < settings.warn_edge_margin)),
        'minimum_order': float(order.min()), 'mean_order': float(order.mean()),
        'order_definition': ('transported local Q amplitude' if settings.smooth_k else
                             'unit-director placeholder; NOT a measured local nematic order'),
        'low_order_vertices': int(np.count_nonzero(order < settings.low_order_warning)) if settings.smooth_k else 0,
        'warnings': warnings,
        'charge_counts': {str(int(k)): int(np.count_nonzero(double_charge == k))
                          for k in np.unique(double_charge[mask])},
        'charge_counts_key': 'twice the physical charge; e.g. 1 means +1/2',
        'location_definition': 'normalized spherical face barycenter, not a fitted defect-core position',
    }
    return {'faces': faces, 'edges': edges, 'double_charge': double_charge, 'q_raw': q_raw,
            'solid_angle': area, 'delta': delta, 'face_delta': face_delta, 'u': u, 'directors': d,
            'order': order, 'face_margin': face_margin, 'face_order': face_order,
            'edge_angles': angles, 'edge_ids': inverse, 'positions': centers,
            'mask': mask, 'diagnostics': diag}


def load_frame(path, settings):
    """Converted XYZ: type x y z [dx dy dz], or NPZ coords/directors/timestep.

    File bytes are read once for both SHA-256 and parsing. Raw dumps, multiple
    frames and invalid row counts are rejected. XYZ row order is preserved.
    """
    path = Path(path)
    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    number = re.search(r'(\d+)$', path.stem)
    fallback = int(number.group(1)) if number else None
    if path.suffix.lower() == '.npz':
        with np.load(io.BytesIO(payload), allow_pickle=False) as f:
            coords = np.asarray(f['coords'], dtype=np.float64)
            directors = np.asarray(f['directors'], dtype=np.float64)
            t = int(f['timestep'].item()) if 'timestep' in f else fallback
        types = np.ones(len(coords), dtype=np.int64)
        box = np.full(3, np.nan)
    else:
        text = payload.decode('utf-8-sig')
        stream = io.StringIO(text)
        first = stream.readline().strip()
        if not first.isdigit():
            raise ValidationError('Expected converted XYZ with particle count on line 1; raw dump not accepted')
        n = int(first)
        header = stream.readline()
        if 'BoxSize:' not in header:
            raise ValidationError('Missing BoxSize in converted XYZ header')
        box = np.asarray([float(x) for x in header.split('BoxSize:', 1)[1].split()], dtype=float)
        if box.shape != (3,) or not np.isfinite(box).all() or np.any(box <= 0):
            raise ValidationError('Invalid box size')
        data = np.loadtxt(stream, dtype=np.float64, ndmin=2)
        required = 7 if settings.director_source == 'columns' else 4
        if data.shape != (n, required) or not np.isfinite(data).all():
            raise ValidationError(f'Expected exactly {n} rows and {required} columns')
        if not np.equal(data[:, 0], np.rint(data[:, 0])).all():
            raise ValidationError('Particle types must be integers')
        types = data[:, 0].astype(np.int64)
        coords = data[:, 1:4]
        directors = data[:, 4:7] if settings.director_source == 'columns' else None
        match = re.search(r'Timestep:\s*(-?\d+)', header)
        t = int(match.group(1)) if match else fallback
    if t is None:
        raise ValidationError('Timestep missing in header and filename')
    if fallback is not None and t != fallback:
        raise ValidationError(f'Filename timestep {fallback} disagrees with header timestep {t}')
    return coords, directors, types, box, t, sha



# ================= User settings (Spyder F5 / runfile) =================
INPUT_DIRECTORY = None  # None: directory containing this script, independent of Spyder cwd
INPUT_PATTERN = 'out-*.xyz'
OUTPUT_DIRECTORY = 'results'
XYZ_OUTPUT_DIRECTORY = 'defect_out'  # Relative to INPUT_DIRECTORY; '.' puts XYZ beside input.
BEADS_PER_CHAIN = 30
SPHERE_CENTER = (0.0, 0.0, 0.0)
WORKERS = 0  # 0: automatic; positive: requested upper bound, still resource-limited
FRAME_TIMEOUT_SECONDS = 600.0
PROGRESS_INTERVAL_SECONDS = 2.0  # 0 restores one progress line per frame
SCRATCH_DIRECTORY = None  # Optional LOCAL SSD for worker DAT spools; None uses per-frame files
# ======================================================================

import queue
import shutil
import subprocess
import tempfile
import threading

DELAUNAY_HEADER = ('# timestep voronoi_x voronoi_y voronoi_z triangle_idx1 '
                   'triangle_idx2 triangle_idx3 delta_theta charge\n')


def write_numeric_table(stream, table, formats, binary=False):
    """Same printf formatting as np.savetxt; bounded, batched writes.

    Python float conversion is exact for float64. No reduced precision, changed
    delimiter or altered row order. Chunk size bounds temporary string memory.
    """
    row_format = '\t'.join(formats) + '\n'
    for start in range(0, len(table), 4096):
        block = ''.join(row_format % tuple(row) for row in table[start:start+4096].tolist())
        stream.write(block.encode('ascii') if binary else block)


def write_defect_xyz(target, coords, box, timestep, result):
    """Legacy four-column XYZ: type 1 beads; 2/3 = +/-1/2; 4/5 = +/-1.

    Markers use the existing normalized face barycenters, without merging,
    smoothing or modifying the counted charges. Higher charges use types
    2*abs(double_charge) (+1 for negative). Input particle order is retained.
    NPZ inputs without box metadata use a plain XYZ comment, not a fake box.
    """
    mask = result['mask']
    charge = result['double_charge'][mask]
    marker_types = 2 * np.abs(charge) + (charge < 0)
    positions = np.concatenate((coords, result['positions'][mask]), axis=0)
    types = np.concatenate((np.ones(len(coords), dtype=np.int64), marker_types))
    with Path(target).open('w', encoding='utf-8', newline='\n', buffering=1 << 20) as f:
        f.write(f'{len(positions)}\n')
        comment = f'Atoms. Timestep: {timestep:9d}'
        if np.isfinite(box).all():
            comment += ', BoxSize: ' + ' '.join(f'{v:18.15E}' for v in box)
        f.write(comment + '\n')
        write_numeric_table(f, np.column_stack((types, positions)),
                            ['%d', '%.15E', '%.15E', '%.15E'])


def worker_compute(task, spool=None):
    settings = Settings(**task['settings'])
    coords, directors, types, box, timestep, sha = load_frame(task['path'], settings)
    result = identify(coords, directors, settings)
    faces = result['faces']
    u = result['u']
    # Dual Voronoi vertices: outward spherical circumcenters, NOT face barycenters.
    a, b, c = (u[faces[:, i]] for i in range(3))
    normal = unit(np.cross(b-a, c-a), label='face normal')
    normal *= np.where(dot(normal, a) < 0, -1., 1.)[:, None]
    centers = normal * result['diagnostics']['radius'] + np.asarray(settings.center)
    corrected_angle = result['face_delta'] + result['solid_angle']
    q = result['double_charge'] * 0.5
    # Same nine-column schema and zero-based triangle indices as the old script.
    # delta_theta now means curvature-corrected winding, so q=delta_theta/(2*pi).
    table = np.column_stack((np.full(len(faces), timestep, dtype=np.int64), centers,
                             faces, corrected_angle, q))
    target = Path(task['output'])
    formats = ['%d','%.6f','%.6f','%.6f','%d','%d','%d','%.6f','%.6f']
    segment = {}
    if spool is None:
        with target.open('w', encoding='utf-8', newline='\n', buffering=1 << 20) as f:
            write_numeric_table(f, table, formats)
    else:
        start = spool.tell()
        write_numeric_table(spool, table, formats, binary=True)
        end = spool.tell()
        spool.flush()  # A reported frame must be fully readable even after shutdown.
        segment = {'data_file': task['spool_output'], 'offset': start, 'length': end-start}
    if 'xyz_output' in task:
        write_defect_xyz(task['xyz_output'], coords, box, timestep, result)
    diag = result['diagnostics']
    return {'index': task['index'], 'timestep': timestep, 'counts': diag['charge_counts'],
            'net': diag['net_charge'], 'total': diag['charged_faces'],
            'max_edge': diag['max_edge_angle_rad'], 'near_branch': diag['near_branch_edges'],
            **segment}


def worker_loop():
    # stdout is a machine protocol. All progress is printed by the supervisor.
    spool = None
    spool_path = None
    try:
        for line in sys.stdin:
            task = json.loads(line)
            try:
                if 'spool_output' in task:
                    if spool is None:
                        spool_path = task['spool_output']
                        spool = open(spool_path, 'wb', buffering=1 << 20)
                    elif spool_path != task['spool_output']:
                        raise RuntimeError('Worker spool changed unexpectedly')
                result = worker_compute(task, spool)
                message = {'ok': True, 'result': result}
            except BaseException as exc:
                message = {'ok': False, 'index': task.get('index'), 'path': task.get('path'),
                           'error': str(exc), 'traceback': traceback.format_exc()}
            sys.stdout.write(json.dumps(message, ensure_ascii=True) + '\n')
            sys.stdout.flush()
            if not message['ok']:
                return 2
        return 0
    finally:
        if spool is not None:
            spool.close()


def supervise(tasks, workers, timeout, progress_interval=PROGRESS_INTERVAL_SECONDS,
              spool_directory=None):
    """Persistent subprocesses; no interactive-kernel function pickling.

    A parent-owned timer bounds every assigned frame, including worker startup.
    Native crash: detected via exit code. Live hang: terminated on timeout.
    Only processes launched here are ever terminated. Kernel-level unkillable
    I/O cannot be universally fixed by a Python program.
    """
    events = queue.Queue()
    processes = []
    source = iter(tasks)
    results = []
    stopped = threading.Event()
    executable = sys.executable
    if os.name == 'nt' and Path(executable).name.lower() == 'pythonw.exe':
        alternative = Path(executable).with_name('python.exe')
        if alternative.is_file():
            executable = str(alternative)

    def read_output(state):
        for line in state['process'].stdout:
            events.put((state, line))
        events.put((state, None))

    def read_errors(state):
        for line in state['process'].stderr:
            state['stderr'] = (state['stderr'] + line)[-12000:]

    def dispatch(state):
        task = next(source, None)
        if task is not None and spool_directory is not None:
            task = dict(task, spool_output=str(Path(spool_directory)/f'worker_{state["process"].pid}.dat'))
        state['task'] = task
        if task is None:
            state['process'].stdin.close()
            return
        state['since'] = time.monotonic()
        state['process'].stdin.write(json.dumps(task, ensure_ascii=True) + '\n')
        state['process'].stdin.flush()

    try:
        for _ in range(min(workers, len(tasks))):
            proc = subprocess.Popen([executable, '-u', str(Path(__file__).resolve()), '--worker'],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                    errors='replace', bufsize=1,
                                    creationflags=(subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0),
                                    env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1'))
            state = {'process': proc, 'task': None, 'since': 0., 'stderr': ''}
            processes.append(state)
            threading.Thread(target=read_output, args=(state,), daemon=True).start()
            threading.Thread(target=read_errors, args=(state,), daemon=True).start()
            dispatch(state)
        last_report = time.monotonic()
        last_progress = last_report
        while len(results) < len(tasks):
            try:
                state, line = events.get(timeout=0.2)
            except queue.Empty:
                state, line = None, None
            if state is not None and state['task'] is not None:
                if line is None:
                    raise RuntimeError(f'Worker PID={state["process"].pid} exited without a result '
                                       f'for {state["task"]["path"]}. {state["stderr"]}')
                message = json.loads(line)
                if not message['ok']:
                    raise RuntimeError(f'{message["path"]}: {message["error"]}\n{message["traceback"]}')
                record = message['result']
                if record['index'] != state['task']['index']:
                    raise RuntimeError('Worker result/task mismatch')
                results.append(record)
                if (len(results) == len(tasks) or progress_interval == 0
                        or time.monotonic()-last_progress >= progress_interval):
                    print(f'[{len(results)}/{len(tasks)}] {Path(state["task"]["path"]).name}: '
                          f'defects={record["total"]}, net={record["net"]:+g}', flush=True)
                    last_progress = time.monotonic()
                dispatch(state)
            now = time.monotonic()
            for st in processes:
                if st['task'] is not None and now-st['since'] > timeout:
                    raise TimeoutError(f'Frame timeout after {timeout:g}s: {st["task"]["path"]}; '
                                       f'worker PID={st["process"].pid}. Increase --timeout only '
                                       'if a legitimate frame needs more time.')
            if now-last_report >= 30:
                active = [f'PID={st["process"].pid} {Path(st["task"]["path"]).name}'
                          for st in processes if st['task'] is not None]
                print('[waiting] ' + '; '.join(active), flush=True)
                last_report = now
        return results
    finally:
        stopped.set()
        # Bounded shutdown; never wait forever for a dead or stalled worker.
        for st in processes:
            p = st['process']
            if p.poll() is None:
                try:
                    p.terminate()
                except OSError:
                    pass
        for st in processes:
            p = st['process']
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    p.kill()
                except OSError:
                    pass
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    print(f'Cannot reap PID={p.pid}; inspect OS/storage state.', flush=True)
            if p.stdin and not p.stdin.closed:
                p.stdin.close()


def publish_pair(work, output, xyz_names=(), xyz_work=None, xyz_output=None):
    """Publish only after all frames succeed; rollback ordinary commit errors."""
    xyz_work = work if xyz_work is None else xyz_work
    xyz_output = output if xyz_output is None else xyz_output
    entries = [(work/name, output/name) for name in ('defect_results.dat', 'delaunay.dat')]
    entries += [(xyz_work/name, xyz_output/name) for name in xyz_names]
    if any(dest.is_dir() for _, dest in entries):
        raise ValidationError('An output filename is occupied by a directory')
    moved = []
    published = []
    try:
        for source, dest in entries:
            if dest.exists():
                backup = source.with_name(source.name + '.previous')
                os.replace(dest, backup)
                moved.append((backup, dest))
        last_report = time.monotonic()
        for index, (source, dest) in enumerate(entries):
            os.replace(source, dest)
            published.append(dest)
            if time.monotonic()-last_report >= 2:
                print(f'[publish] {index+1}/{len(entries)}', flush=True)
                last_report = time.monotonic()
    except BaseException:
        for dest in published:
            dest.unlink(missing_ok=True)
        for backup, dest in moved:
            os.replace(backup, dest)
        raise


def kernel_session():
    return 'ipykernel' in sys.modules or 'spyder_kernels' in sys.modules


def process_alive(pid):
    """Conservative liveness check for migration from legacy PID-only locks."""
    if pid <= 0:
        return True
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if handle:
            kernel.CloseHandle(handle)
            return True
        return ctypes.get_last_error() != 87  # Access denied means possibly alive.
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class OutputLock:
    """OS-held lock; the persistent file's existence does NOT mean busy.

    Never unlink the file: replacing a locked inode would allow two owners.
    A process crash releases the OS lock; normal/Spyder interruption closes it.
    PID-only files from older versions are migrated conservatively.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.file = None

    def acquire(self):
        try:
            fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
        except FileExistsError:
            fd = os.open(str(self.path), os.O_RDWR)
            created = False
        self.file = os.fdopen(fd, 'r+b', buffering=0)
        locked = False
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            self.file.seek(0)
            previous = self.file.read().decode('utf-8', errors='replace').strip()
            if not created and previous.isdigit():
                pid = int(previous)
                # Spyder executes successive runs in the same persistent kernel.
                # A new sequential run may recover its own old PID-only sentinel.
                if pid != os.getpid() and process_alive(pid):
                    raise RuntimeError(f'Legacy output lock {self.path} belongs to live PID={pid}. '
                                       'Its running state cannot be inferred from a PID-only file. '
                                       'Rerun in the original Spyder kernel, or stop that old task/kernel first.')
                print(f'[lock] Recovered legacy lock: {self.path.name}, PID={pid}', flush=True)
            elif not created and not previous.startswith('{"lock_format": "sphere-os-lock-v1"'):
                raise RuntimeError(f'Unrecognized legacy lock: {self.path}; verify its owner before removing it.')
            metadata = {'lock_format': 'sphere-os-lock-v1', 'pid': os.getpid(),
                        'script': str(Path(__file__).resolve()), 'started': time.time()}
            data = json.dumps(metadata, ensure_ascii=True).encode('utf-8')
            self.file.seek(0)
            self.file.write(data)
            self.file.truncate()
            return self
        except BaseException as exc:
            self.close()
            if not locked and isinstance(exc, OSError):
                raise RuntimeError(f'Output lock unavailable: {self.path}. Another task may be running, '
                                   'or the filesystem does not support locking. Do not delete an active lock.') from exc
            raise

    def close(self):
        if self.file is not None:
            self.file.close()  # Closing releases the OS lock, including on Windows.
            self.file = None


def select_workers(requested, paths, max_frame_bytes=None):
    """Respect affinity/scheduler limits; optional psutil supplies memory headroom."""
    try:
        cpus = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        cpus = os.cpu_count() or 1
    for name in ('SLURM_CPUS_PER_TASK', 'NSLOTS'):
        value = os.environ.get(name, '')
        if value.isdigit() and int(value) > 0:
            cpus = min(cpus, int(value))
    # cgroup v2 CPU quotas (e.g. containers).
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota != 'max':
            cpus = min(cpus, max(1, int(quota)//int(period)))
    except (OSError, ValueError):
        pass
    available = None
    try:
        import psutil
        available = psutil.virtual_memory().available
        if requested == 0:
            cpus = min(cpus, psutil.cpu_count(logical=False) or cpus)
    except ImportError:
        try:
            info = Path('/proc/meminfo').read_text()
            available = int(re.search(r'MemAvailable:\s+(\d+)', info).group(1))*1024
        except (OSError, AttributeError, ValueError):
            pass
    if available is None and os.name == 'nt':
        try:
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong) for name in
                    ('total_phys', 'avail_phys', 'total_page', 'avail_page',
                     'total_virtual', 'avail_virtual', 'avail_extended')]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                available = status.avail_phys
        except (AttributeError, OSError):
            pass
    try:
        cap = Path('/sys/fs/cgroup/memory.max').read_text().strip()
        used = int(Path('/sys/fs/cgroup/memory.current').read_text())
        if cap != 'max':
            remaining = max(0, int(cap)-used)
            available = remaining if available is None else min(available, remaining)
    except (OSError, ValueError):
        pass
    workers = min(requested or min(4, cpus), cpus, len(paths))
    # Conservative heuristic, not a guarantee for arbitrary compressed NPZ files.
    if max_frame_bytes is None:
        max_frame_bytes = max(p.stat().st_size for p in paths)
    estimate = max(256 << 20, max_frame_bytes*256)
    if available is not None:
        workers = min(workers, max(1, int(available*0.5)//estimate))
    return max(1, workers)


def merge_spools(records, destination):
    """Copy exact byte ranges in timestep order; no text parsing or rounding."""
    handles = {}
    last_report = time.monotonic()
    try:
        with destination.open('wb', buffering=1 << 20) as target:
            target.write(DELAUNAY_HEADER.encode('utf-8'))
            for i, record in enumerate(records):
                if 'data_file' not in record:
                    with (destination.parent/f'frame_{record["index"]}.dat').open('rb') as source:
                        shutil.copyfileobj(source, target, length=1 << 20)
                    if time.monotonic()-last_report >= 2:
                        print(f'[merge] {i+1}/{len(records)}', flush=True)
                        last_report = time.monotonic()
                    continue
                name = record['data_file']
                if name not in handles:
                    handles[name] = open(name, 'rb', buffering=1 << 20)
                source = handles[name]
                source.seek(record['offset'])
                remaining = record['length']
                while remaining:
                    data = source.read(min(remaining, 1 << 20))
                    if not data:
                        raise IOError(f'Truncated worker spool: {name}')
                    target.write(data)
                    remaining -= len(data)
                if time.monotonic()-last_report >= 2:
                    print(f'[merge] {i+1}/{len(records)}', flush=True)
                    last_report = time.monotonic()
    finally:
        for handle in handles.values():
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', default=INPUT_DIRECTORY,
                        help='Default: directory containing this script; explicit relative paths use cwd')
    parser.add_argument('--pattern', default=INPUT_PATTERN)
    parser.add_argument('--output', default=OUTPUT_DIRECTORY,
                        help='DAT directory relative to input directory, or an absolute path')
    parser.add_argument('--xyz-output', default=XYZ_OUTPUT_DIRECTORY,
                        help='XYZ directory relative to --input-dir (default: defect_out); '
                             'use . for the input directory, or an absolute path')
    parser.add_argument('--chain-length', type=int, default=BEADS_PER_CHAIN)
    parser.add_argument('--center', type=float, nargs=3, default=SPHERE_CENTER)
    parser.add_argument('--workers', type=int, default=int(os.environ.get('DEFECT_WORKERS', WORKERS)))
    parser.add_argument('--timeout', type=float, default=FRAME_TIMEOUT_SECONDS)
    parser.add_argument('--progress-interval', type=float, default=PROGRESS_INTERVAL_SECONDS,
                        help='Progress seconds; 0 prints every frame')
    parser.add_argument('--scratch-dir', default=SCRATCH_DIRECTORY,
                        help='Optional local SSD directory for temporary mesh spools')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--director-source', choices=['chains','columns'], default='chains')
    args = parser.parse_args([] if argv is None and kernel_session() else argv)
    print(f'[sphere-nematic {RUNTIME_REVISION}] {Path(__file__).resolve()}', flush=True)
    input_dir = (Path(__file__).resolve().parent if args.input_dir is None
                 else Path(args.input_dir).expanduser().resolve())
    if (args.workers < 0 or args.timeout <= 0 or not np.isfinite(args.timeout) or args.limit < 0
            or args.progress_interval < 0 or not np.isfinite(args.progress_interval)):
        raise ValueError('workers >= 0 (0=auto), finite timeout > 0, limit >= 0, progress interval >= 0 required')
    if args.chain_length < 2 or not np.isfinite(args.center).all():
        raise ValueError('Invalid chain length or center')
    # scandir reuses directory-entry metadata, avoiding multiple per-frame path
    # resolutions/stat calls on Windows and shared storage. Complex path patterns
    # retain the original glob behavior.
    entries = {}
    paths = []
    if not any(separator in args.pattern for separator in ('/', '\\')):
        pattern = os.path.normcase(args.pattern)
        with os.scandir(input_dir) as scan:
            for entry in scan:
                if (entry.name.startswith('.') and not args.pattern.startswith('.')):
                    continue
                if fnmatch.fnmatchcase(os.path.normcase(entry.name), pattern) and entry.is_file():
                    path = Path(entry.path).resolve() if entry.is_symlink() else Path(entry.path)
                    entries[path] = entry
                    paths.append(path)
    else:
        paths = [Path(p).resolve() for p in glob.glob(str(input_dir/args.pattern)) if Path(p).is_file()]
    def key(path):
        match = re.search(r'(\d+)$', path.stem)
        return (int(match.group(1)) if match else -1, path.name)
    paths.sort(key=key)
    if args.limit:
        paths = paths[:args.limit]
    if not paths:
        raise ValueError('No input frames matched')
    max_frame_bytes = max((entries[p].stat().st_size if p in entries else p.stat().st_size)
                          for p in paths)
    workers = select_workers(args.workers, paths, max_frame_bytes)
    settings = Settings(chain_length=args.chain_length, center=tuple(args.center),
                        director_source=args.director_source)
    output = (input_dir/Path(args.output).expanduser()).resolve()
    output.mkdir(parents=True, exist_ok=True)
    xyz_output = (input_dir/Path(args.xyz_output).expanduser()).resolve()
    xyz_output.mkdir(parents=True, exist_ok=True)
    # Protect both destinations, even when callers choose different DAT directories.
    lock_paths = sorted({p.parent/('.'+p.name+'.sphere.lock')
                         for p in (output, xyz_output)}, key=str)
    acquired_locks = []
    work = None
    xyz_work = None
    scratch_work = None
    scratch_root = None
    started = time.perf_counter()
    try:
        for lock in lock_paths:
            acquired_locks.append(OutputLock(lock).acquire())
        work = Path(tempfile.mkdtemp(prefix='.sphere_work_', dir=str(output.parent))).resolve()
        # Stage on each destination filesystem so os.replace also supports separate drives.
        xyz_work = Path(tempfile.mkdtemp(prefix='.sphere_xyz_work_',
                                        dir=str(xyz_output.parent))).resolve()
        if args.scratch_dir:
            scratch_root = Path(args.scratch_dir).resolve()
            scratch_root.mkdir(parents=True, exist_ok=True)
            scratch_work = Path(tempfile.mkdtemp(prefix='.sphere_spool_', dir=str(scratch_root))).resolve()
        # Validate the exact owned cleanup target before any recursive cleanup.
        if work.parent != output.parent or not work.name.startswith('.sphere_work_'):
            raise RuntimeError('Unexpected temporary workspace path')
        xyz_names = [('defect_' + path.stem if path.stem.startswith('out-')
                      else 'defect_out-' + path.stem) + '.xyz' for path in paths]
        if len(set(xyz_names)) != len(xyz_names):
            raise ValidationError('Duplicate trajectory output names')
        tasks = [{'index': i, 'path': str(path), 'output': str(work/f'frame_{i}.dat'),
                  'xyz_output': str(xyz_work/xyz_names[i]),
                  'settings': asdict(settings)} for i, path in enumerate(paths)]
        print(f'Input={input_dir}\nFrames={len(paths)}; parallel workers={workers}; timeout/frame={args.timeout:g}s\n'
              f'Output={output}\nNo recovery or charge insertion.', flush=True)
        records = supervise(tasks, workers, args.timeout, args.progress_interval,
                            scratch_work)
        records.sort(key=lambda r: r['timestep'])
        if len({r['timestep'] for r in records}) != len(records):
            raise ValidationError('Duplicate timesteps; final files not published')
        charges = sorted({-1} | {int(q) for r in records for q in r['counts']}, key=lambda q:(-abs(q), q<0))
        def label(q):
            return str(q//2) if q%2 == 0 else f'{q:+d}/2'
        with (work/'defect_results.dat').open('w', encoding='utf-8', newline='\n') as f:
            f.write('\t'.join(['timestep']+[label(q) for q in charges]+['net_charge','total_defects'])+'\n')
            for r in records:
                row = [str(r['timestep'])]+[str(r['counts'].get(str(q),0)) for q in charges]
                f.write('\t'.join(row+[f'{r["net"]:.1f}',str(r['total'])])+'\n')
        merge_spools(records, work/'delaunay.dat')
        publish_pair(work, output, xyz_names, xyz_work, xyz_output)
        sparse = sum(r['max_edge'] > .5 for r in records)
        near = sum(r['near_branch'] > 0 for r in records)
        print(f'Completed {len(records)} frames in {time.perf_counter()-started:.2f}s. '
              f'Sparse-sampling frames (>0.5 rad): {sparse}; near-90-degree frames: {near}.\n'
              'These are sampling warnings, not radius errors or physical-accuracy certificates.\n'
              f'{output/"defect_results.dat"}\n{output/"delaunay.dat"}\n'
              f'{len(xyz_names)} particle + defect XYZ frames: {xyz_output}/defect_out-*.xyz', flush=True)
        return 0
    except BaseException:
        print('FAILED: no new complete result pair published; any previous files are from an older run.', flush=True)
        raise
    finally:
        # Work directories are unique to this run. Release output ownership before
        # potentially slow cleanup; no further final-output writes occur below.
        for lock in acquired_locks:
            lock.close()
        if (scratch_work is not None and scratch_work.parent == scratch_root
                and scratch_work.name.startswith('.sphere_spool_')):
            shutil.rmtree(scratch_work, ignore_errors=True)
        if work is not None and work.parent == output.parent and work.name.startswith('.sphere_work_'):
            shutil.rmtree(work, ignore_errors=True)
        if (xyz_work is not None and xyz_work.parent == xyz_output.parent
                and xyz_work.name.startswith('.sphere_xyz_work_')):
            shutil.rmtree(xyz_work, ignore_errors=True)


if __name__ == '__main__':
    if '--worker' in sys.argv[1:]:
        raise SystemExit(worker_loop())
    main()
