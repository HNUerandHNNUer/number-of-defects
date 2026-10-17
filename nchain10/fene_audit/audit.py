"""Read-only trajectory audit; outputs are confined to this script's directory."""
from pathlib import Path
import csv
import json
import numpy as np

out = Path(__file__).resolve().parent
source = out.parent / 'F_50_gpu1'
bonds = []
section = None
for line in (source / 'polymer.data').read_text().splitlines():
    fields = line.split()
    if not fields:
        continue
    if fields[0] in ('Atoms', 'Bonds', 'Angles', 'Masses', 'Velocities'):
        section = fields[0]
        continue
    if section == 'Bonds' and len(fields) == 4:
        bonds.append([int(fields[2]) - 1, int(fields[3]) - 1])
bonds = np.asarray(bonds)
threshold = 1.5 * np.sqrt(0.9)
rows = []
for path in sorted(source.glob('out-*.xyz')):
    lines = path.read_text().splitlines()
    if not lines[0].startswith('ITEM:'):
        continue
    atoms = np.asarray([[float(v) for v in line.split()] for line in lines[9:]])
    if len(atoms) != int(lines[3]):
        raise ValueError(f'Incomplete frame: {path}')
    atoms = atoms[np.argsort(atoms[:, 0])]
    if not np.array_equal(atoms[:, 0], np.arange(1, len(atoms) + 1)):
        raise ValueError('Expected consecutive atom IDs')
    xyz = atoms[:, 2:5]
    box = np.asarray([float(line.split()[1]) - float(line.split()[0]) for line in lines[5:8]])
    delta = xyz[bonds[:, 1]] - xyz[bonds[:, 0]]
    delta -= box * np.rint(delta / box)
    lengths = np.linalg.norm(delta, axis=1)
    radii = np.linalg.norm(xyz, axis=1)
    rows.append(dict(step=int(lines[1]), max_bond=float(lengths.max()),
                     bonds_above_warning=int((lengths > threshold).sum()),
                     bonds_ge_R0=int((lengths >= 1.5).sum()),
                     min_radius=float(radii.min()), max_radius=float(radii.max())))
with (out / 'frame_metrics.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
summary = dict(source=str(source), frames=len(rows), last_saved_step=rows[-1]['step'],
               warning_threshold=threshold, bonds_per_frame=len(bonds))
for name, cutoff in [('all', 0), ('after_available_25_percent', rows[-1]['step'] * .25)]:
    subset = [r for r in rows if r['step'] >= cutoff]
    summary[name] = dict(frames=len(subset),
        frames_with_overlong_bonds=sum(r['bonds_above_warning'] > 0 for r in subset),
        bond_frame_observations_above_warning=sum(r['bonds_above_warning'] for r in subset),
        bond_frame_observations_ge_R0=sum(r['bonds_ge_R0'] for r in subset),
        max_bond=max(r['max_bond'] for r in subset))
(out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
