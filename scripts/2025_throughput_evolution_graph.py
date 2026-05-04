import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import mplhep as hep
hep.style.use("CMS")

from matplotlib.colors import to_rgb, to_hex
from matplotlib.patches import Patch

# Data extracted from the table
versions = ["2025-V1.0", "2025-V1.1", "2025-V1.2", "2025-V1.3"]

# Throughput (events/s) with uncertainties
throughput = [470.3, 473.0, 513.7, 525.4]
throughput_unc = [1.2, 0.9, 0.7, 0.7]

# Timing (ms) -- no uncertainties shown in the table
timing_ms = [552.5, 548.4, 505.8, 495.6]

# Create a plot with two y-axes
fig, ax1 = plt.subplots(figsize=(8.5, 4.8))

# Throughput with error bars (left axis)
ax1.errorbar(
    versions,
    throughput,
    yerr=throughput_unc,
    fmt="o-",
    capsize=5,
    linewidth=2,
    markersize=7,
)

# Add numeric values on top of each point
for i, (version, value) in enumerate(zip(versions, throughput)):
    if i == 0:
        ax1.text(i+0.25, value + throughput_unc[i] - 10, f"{value:.1f} [ev/s]",
             ha='center', va='bottom', fontsize=15)
    elif i == 1:
        ax1.text(i+0.15, value + throughput_unc[i] - 10, f"{value:.1f} [ev/s]",
             ha='center', va='bottom', fontsize=15)
    elif i == 2:
        ax1.text(i-0.25, value + throughput_unc[i] + 1, f"{value:.1f} [ev/s]",
             ha='center', va='bottom', fontsize=15)
    else:
        ax1.text(i-0.25, value + throughput_unc[i] + 1, f"{value:.1f} [ev/s]",
             ha='center', va='bottom', fontsize=15)

x4 = [0, 1, 2, 3]
ax1.set_xticks(x4)
ax1.set_xticklabels(versions, rotation=0, ha="center", fontsize=12)
ax1.set_xlabel("HLT menu version", fontsize=15)
ax1.set_ylabel("Throughput [ev/s]", fontsize=15)
ax1.grid(True, linestyle="--", alpha=0.5)
ax1.set_ylim(450, 550)
y5 = [460, 480, 500, 520, 540]
ax1.set_yticks(y5)
ax1.set_yticklabels(y5, rotation=0, fontsize=12)
hep.cms.label("Preliminary", data=True, com=13.6, ax=ax1, loc=2, fontsize=15)
ax1.minorticks_off()

# Timing on a secondary y-axis (right axis)
#ax2 = ax1.twinx()
#ax2.plot(versions, timing_ms, "s--", linewidth=2, markersize=6)
#ax2.set_ylabel("Timing (ms)")

#plt.title("CMS HLT throughput evolution in 2025")
fig.tight_layout()

# Save plot
plt.savefig("cms_hlt_throughput_2025.png", dpi=200, bbox_inches="tight")
#plt.show()
