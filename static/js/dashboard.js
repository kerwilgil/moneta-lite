document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.getElementById("dashboard-refresh");
    if (refreshButton) {
        refreshButton.addEventListener("click", () => {
            refreshButton.dataset.loading = "true";
            refreshButton.setAttribute("aria-busy", "true");
            window.location.reload();
        });
    }

    initProgressBars();

    const canvas = document.getElementById("cashFlowChart");
    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    const seriesNode = document.getElementById("cash-flow-series");
    if (!seriesNode) {
        return;
    }

    let series = { labels: [], values: [] };
    try {
        series = JSON.parse(seriesNode.textContent);
    } catch (_error) {
        return;
    }

    const chartFrame = canvas.closest(".chart-frame");
    const chartHeightControl = document.getElementById("chartHeightControl");
    const topGrid = document.getElementById("dashboardTopGrid");
    const walletPanel = topGrid ? topGrid.querySelector(".wallet-panel") : null;
    const chartPanel = topGrid ? topGrid.querySelector(".chart-panel") : null;
    const chartHeightStorageKey = "moneta-cashflow-height";
    let cashFlowChart = null;

    function syncSliderMaxWithWallet() {
        if (!chartHeightControl || !chartFrame || !walletPanel || !chartPanel) {
            return;
        }

        if (window.matchMedia("(max-width: 1100px)").matches) {
            chartHeightControl.max = "560";
            return;
        }

        const minValue = Number(chartHeightControl.min) || 220;
        const currentFrameHeight = chartFrame.getBoundingClientRect().height;
        const currentPanelHeight = chartPanel.getBoundingClientRect().height;
        const panelOverhead = Math.max(0, currentPanelHeight - currentFrameHeight);
        const walletHeight = walletPanel.getBoundingClientRect().height;
        const maxValue = Math.max(minValue, Math.floor(walletHeight - panelOverhead));

        chartHeightControl.max = String(maxValue);
        if (Number(chartHeightControl.value) > maxValue) {
            chartHeightControl.value = String(maxValue);
        }
    }

    function cssVar(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    function buildDataset(values, green, greenSoft) {
        const maxValue = Math.max(...values.map((value) => Math.abs(Number(value) || 0)), 0);
        return values.map((value) => (Math.abs(Number(value) || 0) === maxValue ? green : greenSoft));
    }

    function buildChart() {
        if (cashFlowChart) {
            cashFlowChart.destroy();
        }

        const labels = Array.isArray(series.labels) ? series.labels : [];
        const values = Array.isArray(series.values) ? series.values : [];
        const text = cssVar("--text");
        const muted = cssVar("--muted");
        const line = cssVar("--line");
        const green = cssVar("--green");
        const greenSoft = cssVar("--green-soft");
        const surface = cssVar("--surface");
        const warning = cssVar("--warning");

        // Populate tabular fallback for accessibility/no-JS
        const tableBody = document.getElementById("cashFlowTableBody");
        if (tableBody && window.MonetaCurrency) {
            tableBody.innerHTML = labels.map((label, i) =>
                `<tr><th scope="row">${label}</th><td>${window.MonetaCurrency.format(values[i] || 0)}</td></tr>`
            ).join("");
        }

        cashFlowChart = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Cash Flow",
                        data: values,
                        backgroundColor: buildDataset(values, green, greenSoft),
                        borderColor: values.map((value) => (value < 0 ? warning : green)),
                        borderWidth: 1,
                        borderRadius: 10,
                        borderSkipped: false,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: text,
                        titleColor: surface,
                        bodyColor: surface,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            label: (context) => window.MonetaCurrency ? window.MonetaCurrency.format(context.parsed.y || 0) : `$${Number(context.parsed.y || 0).toFixed(2)}`,
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        border: { display: false },
                        ticks: { color: muted },
                    },
                    y: {
                        grid: { color: line },
                        border: { display: false },
                        ticks: {
                            color: muted,
                            callback: (value) => window.MonetaCurrency ? window.MonetaCurrency.formatPlain(value) : `$${Number(value).toLocaleString()}`,
                        },
                    },
                },
            },
        });
    }

    if (chartHeightControl && chartFrame) {
        const setHeight = () => {
            syncSliderMaxWithWallet();
            const minValue = Number(chartHeightControl.min) || 220;
            const maxValue = Number(chartHeightControl.max) || 560;
            const clampedValue = Math.min(maxValue, Math.max(minValue, Number(chartHeightControl.value) || 420));
            chartHeightControl.value = String(clampedValue);
            localStorage.setItem(chartHeightStorageKey, String(clampedValue));
            const height = `${clampedValue}px`;
            chartFrame.style.height = height;
            chartFrame.style.minHeight = height;
            if (cashFlowChart) {
                window.requestAnimationFrame(() => cashFlowChart.resize());
            }
        };

        const persistedHeight = Number(localStorage.getItem(chartHeightStorageKey));
        if (Number.isFinite(persistedHeight) && persistedHeight > 0) {
            chartHeightControl.value = String(persistedHeight);
        }

        chartHeightControl.addEventListener("input", setHeight);
        setHeight();
    }

    buildChart();
    if (walletPanel) {
        walletPanel.style.height = "";
        walletPanel.style.minHeight = "";
    }
    window.requestAnimationFrame(syncSliderMaxWithWallet);
    window.addEventListener("resize", () => {
        syncSliderMaxWithWallet();
        if (chartHeightControl && chartFrame) {
            const height = `${Number(chartHeightControl.value) || 420}px`;
            chartFrame.style.height = height;
            chartFrame.style.minHeight = height;
            if (cashFlowChart) {
                cashFlowChart.resize();
            }
        }
    });
    window.addEventListener("moneta-theme-change", () => {
        buildChart();
        window.requestAnimationFrame(syncSliderMaxWithWallet);
    });
});

function initProgressBars() {
    document.querySelectorAll(".progress-bar[aria-valuenow]").forEach((bar) => {
        const value = parseFloat(bar.getAttribute("aria-valuenow"));
        if (!Number.isNaN(value)) {
            const clamped = Math.min(100, Math.max(0, value));
            bar.style.width = `${clamped}%`;
        }
    });
}
