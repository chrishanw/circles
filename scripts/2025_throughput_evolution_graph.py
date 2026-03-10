import matplotlib.pyplot as plt

# Data extracted from the table
versions = ["2025-V1.1", "2025-V1.2", "2025-V1.3"]

# Throughput (events/s) with uncertainties
throughput = [475.2, 511.9, 523.9]
throughput_unc = [1.4, 0.7, 3.7]

# Timing (ms) -- no uncertainties shown in the table
timing_ms = [545.2, 507.4, 497.0]

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
        ax1.text(i+0.4, value + throughput_unc[i] - 3, f"{value:.1f} evts/s", 
             ha='center', va='bottom', fontsize=20)
    elif i == 1:
        ax1.text(i-0.1, value + throughput_unc[i] + 1, f"{value:.1f} evts/s", 
             ha='center', va='bottom', fontsize=20)
    else:
        ax1.text(i-0.3, value + throughput_unc[i] + 1, f"{value:.1f} evts/s", 
             ha='center', va='bottom', fontsize=20)

ax1.set_xlabel("HLT menu version")
ax1.set_ylabel("Throughput (events/s)")
ax1.grid(True, linestyle="--", alpha=0.5)
ax1.set_ylim(470, 535)

# Timing on a secondary y-axis (right axis)
#ax2 = ax1.twinx()
#ax2.plot(versions, timing_ms, "s--", linewidth=2, markersize=6)
#ax2.set_ylabel("Timing (ms)")

plt.title("CMS HLT throughput evolution in 2025")
fig.tight_layout()

# Save plot
plt.savefig("cms_hlt_throughput_2025.png", dpi=200)
plt.show()
