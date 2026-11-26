"""Draw the largest-volume YM38 sensitivity profiles from controls.py --json."""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

row = next(entry for entry in json.loads(Path(sys.argv[1]).read_text())['spectral'] if entry['L'] == 16)
fig, ax = plt.subplots(figsize=(8, 4.8), layout='constrained')
fractions = [0., .01, .05, .1, .25]
for key, label, color, mark in [
    ('massless', 'Jedna bezmasna pobuda', '#A63822', 'o'),
    ('dense_dyadic', 'Guste razine između 0 i 1', '#00647A', 's'),
    ('accumulating_tower', 'Razine 1, 1/2, 1/3, …', '#503A90', '^'),
]:
    ax.plot([100*x for x in fractions],
            [row['profiles'][key][str(x)]['D2'] for x in fractions],
            color=color, marker=mark, linewidth=2, markersize=6, label=label)
ax.axhspan(row['ellipsoid_cut'], row['finite_sample_reference_cut'], color='#A7ABAF', alpha=.4,
           label='Raspon dvaju pragova testa')
ax.set(yscale='log', xticks=[0, 1, 5, 10, 25], ylim=(1, 800),
       xlabel='Udio početnog signala dodijeljen odabranim pobudama (%)',
       ylabel='Odstupanje od mjerenja (D²)')
ax.set_title('Koliki dio signala mogu nositi lagane pobude?', loc='left', fontweight='bold')
ax.grid(axis='y', alpha=.18)
ax.spines[['top', 'right']].set_visible(False)
ax.legend(loc='upper left', frameon=False, fontsize=9)
fig.savefig(Path(__file__).with_name('profile.png'), dpi=155, facecolor='white')
