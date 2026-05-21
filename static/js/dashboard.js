const App = {
    socket: null,
    currentModel: "",
    monitors: {},
    charts: {},
    detailsPage: 1,
    detailsSentiment: "",
    detailsPlatform: "",
    currentDetails: [],

    init() {
        this.socket = io();
        this.socket.on("connect", () => console.log("Socket.IO 已连接"));
        this.socket.on("disconnect", () => console.log("Socket.IO 已断开"));
        this.socket.on("monitor_start", (data) => this.onMonitorStart(data));
        this.socket.on("dashboard_update", (data) => this.onDashboardUpdate(data));
        this.socket.on("error", (data) => this.onError(data));
        this.socket.on("progress", (data) => this.onProgress(data));
        this.bindEvents();
    },

    bindEvents() {
        const searchBtn = document.getElementById("searchBtn");
        const searchInput = document.getElementById("searchInput");
        if (searchBtn) searchBtn.addEventListener("click", () => this.startMonitor());
        if (searchInput) searchInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") this.startMonitor();
        });

        document.querySelectorAll(".quick-tag").forEach(tag => {
            tag.addEventListener("click", () => {
                const model = tag.dataset.model;
                if (searchInput) searchInput.value = model;
                this.startMonitor(model);
            });
        });
    },

    startMonitor(carModel) {
        const input = document.getElementById("searchInput");
        const model = carModel || (input ? input.value.trim() : "");
        if (!model) {
            this.showToast("请输入车型名称", "error");
            return;
        }

        this.showLoading(true);
        fetch("/api/monitor", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ car_model: model }),
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                this.showToast(data.error, "error");
                this.showLoading(false);
            } else {
                this.addMonitorTag(model);
                this.showToast(`正在分析 ${model} 的舆情...`, "info");
            }
        })
        .catch(err => {
            this.showToast("请求失败: " + err.message, "error");
            this.showLoading(false);
        });
    },

    addMonitorTag(model) {
        this.monitors[model] = true;
        const container = document.getElementById("monitorTags");
        if (!container) return;

        const existing = container.querySelector(`[data-model="${model}"]`);
        if (existing) {
            this.switchMonitor(model);
            return;
        }

        const tag = document.createElement("div");
        tag.className = "monitor-tag";
        tag.dataset.model = model;
        tag.innerHTML = `
            <span class="monitor-tag-name">${model}</span>
            <button class="monitor-tag-refresh" onclick="event.stopPropagation(); App.startMonitor('${model}')" title="重新分析">&#x21bb;</button>
            <button class="monitor-tag-close" onclick="App.removeMonitor('${model}')">&times;</button>
        `;
        tag.addEventListener("click", (e) => {
            if (!e.target.classList.contains("monitor-tag-close")) {
                this.switchMonitor(model);
            }
        });
        container.appendChild(tag);
        this.switchMonitor(model);
    },

    removeMonitor(model) {
        delete this.monitors[model];
        const container = document.getElementById("monitorTags");
        const tag = container ? container.querySelector(`[data-model="${model}"]`) : null;
        if (tag) tag.remove();

        fetch(`/api/monitor/${encodeURIComponent(model)}`, { method: "DELETE" });

        const remaining = Object.keys(this.monitors);
        if (remaining.length > 0) {
            this.switchMonitor(remaining[remaining.length - 1]);
        } else {
            this.currentModel = "";
            this.clearDashboard();
        }
    },

    switchMonitor(model) {
        this.currentModel = model;
        document.querySelectorAll(".monitor-tag").forEach(t => t.classList.remove("active"));
        const tag = document.querySelector(`.monitor-tag[data-model="${model}"]`);
        if (tag) tag.classList.add("active");

        fetch(`/api/dashboard/${encodeURIComponent(model)}`)
            .then(res => res.json())
            .then(data => {
                if (!data.error) {
                    this.renderAgentResponse(data);
                    this.renderMajorAlerts(data);
                    this.renderDashboard(data);
                }
            })
            .catch(() => {});
    },

    onMonitorStart(data) {
        console.log("监控开始:", data.car_model);
    },

    onDashboardUpdate(data) {
        this.showLoading(false);
        if (data.car_model === this.currentModel) {
            this.renderAgentResponse(data.data);
            this.renderMajorAlerts(data.data);
            this.renderDashboard(data.data);
        }
        this.showToast(`${data.car_model} 舆情分析完成`, "success");
    },

    onError(data) {
        this.showLoading(false);
        this.showToast(data.message || "分析失败", "error");
    },

    onProgress(data) {
        const progressEl = document.getElementById("loadingProgress");
        if (progressEl && data.message) {
            progressEl.textContent = data.message;
        }
    },

    renderAgentResponse(data) {
        const section = document.getElementById("agentResponseSection");
        const content = document.getElementById("agentResponseContent");
        if (!section || !content) return;

        const resp = data.agent_response || {};
        if (!resp.core_conclusion) {
            section.style.display = "none";
            return;
        }

        section.style.display = "block";

        let html = "";
        if (resp.greeting) {
            html += `<div class="agent-greeting">${this.escapeHtml(resp.greeting)}</div>`;
        }
        html += `<div class="agent-conclusion">${this.escapeHtml(resp.core_conclusion)}</div>`;

        if (resp.key_points && resp.key_points.length > 0) {
            html += '<div class="agent-key-points"><ul>';
            resp.key_points.forEach(p => {
                html += `<li>${this.escapeHtml(p)}</li>`;
            });
            html += '</ul></div>';
        }

        if (resp.alert_summary) {
            html += `<div class="agent-alert-summary"><i class="fas fa-exclamation-triangle"></i> ${this.escapeHtml(resp.alert_summary)}</div>`;
        }

        if (resp.quality_note) {
            html += `<div class="agent-quality-note"><i class="fas fa-check-circle"></i> ${this.escapeHtml(resp.quality_note)}</div>`;
        }

        if (resp.suggestion) {
            html += `<div class="agent-suggestion">${this.escapeHtml(resp.suggestion)}</div>`;
        }

        content.innerHTML = html;
    },

    renderMajorAlerts(data) {
        const section = document.getElementById("majorAlertSection");
        const list = document.getElementById("majorAlertList");
        const card = document.getElementById("majorAlertCard");
        if (!section || !list || !card) return;

        const majorOpinions = data.major_opinions || [];
        const alertLevel = data.alert_level || "none";

        if (majorOpinions.length === 0) {
            section.style.display = "none";
            return;
        }

        section.style.display = "block";
        card.className = `major-alert-card alert-${alertLevel}`;

        let html = "";
        majorOpinions.forEach(op => {
            const levelClass = op.alert_level === "critical" ? "alert-item-critical" : "alert-item-warning";
            const levelIcon = op.alert_level === "critical" ? "fa-fire" : "fa-exclamation-circle";
            html += `
                <div class="major-alert-item ${levelClass}">
                    <div class="alert-item-header">
                        <i class="fas ${levelIcon}"></i>
                        <span class="alert-item-title">${this.escapeHtml(op.title || "")}</span>
                        <span class="alert-item-platform">${this.escapeHtml(op.platform || "")}</span>
                    </div>
                    <div class="alert-item-content">${this.escapeHtml(op.content || "")}</div>
                    <div class="alert-item-reason"><i class="fas fa-tag"></i> ${this.escapeHtml(op.alert_reason || "")}</div>
                </div>
            `;
        });
        list.innerHTML = html;
    },

    showDashboard() {
        const section = document.getElementById("dashboardSection");
        if (section) {
            section.style.display = "block";
            section.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        const btn = document.getElementById("btnShowDashboard");
        if (btn) {
            btn.innerHTML = '<i class="fas fa-chart-bar"></i> 看板已展开';
            btn.disabled = true;
            btn.style.opacity = "0.6";
        }
    },

    renderDashboard(data) {
        this.renderStats(data);
        this.renderSentimentChart(data);
        this.renderWordCloud(data);
        this.renderVolumeChart(data);
        this.renderTrendChart(data);
        this.renderInsightReport(data);
        this.renderDetails(data);
    },

    renderStats(data) {
        const dist = data.sentiment_distribution || {};
        document.getElementById("statTotal").textContent = data.total_count || 0;
        document.getElementById("statPositive").textContent = dist.positive || 0;
        document.getElementById("statNegative").textContent = dist.negative || 0;
        document.getElementById("statNeutral").textContent = dist.neutral || 0;
    },

    renderSentimentChart(data) {
        const container = document.getElementById("sentimentChart");
        if (!container) return;
        container.innerHTML = "";

        if (this.charts.sentiment) this.charts.sentiment.dispose();
        const chart = echarts.init(container);
        this.charts.sentiment = chart;

        const dist = data.sentiment_distribution || {};
        const chartData = [
            { value: dist.positive || 0, name: "正面", itemStyle: { color: "#10b981" } },
            { value: dist.negative || 0, name: "负面", itemStyle: { color: "#ef4444" } },
            { value: dist.neutral || 0, name: "中性", itemStyle: { color: "#f59e0b" } },
        ];

        chart.setOption({
            tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
            series: [{
                type: "pie",
                radius: ["45%", "72%"],
                center: ["50%", "50%"],
                data: chartData,
                label: {
                    color: "#9ca3af",
                    fontSize: 12,
                    formatter: "{b}\n{d}%",
                },
                labelLine: { lineStyle: { color: "#4b5563" } },
                emphasis: {
                    itemStyle: { shadowBlur: 20, shadowColor: "rgba(0,0,0,0.5)" },
                },
                animationType: "scale",
                animationEasing: "elasticOut",
            }],
        });
        window.addEventListener("resize", () => chart.resize());
    },

    renderWordCloud(data) {
        const container = document.getElementById("wordCloudChart");
        if (!container) return;
        container.innerHTML = "";

        const keywords = data.hotspot_keywords || [];
        if (keywords.length === 0) return;

        const list = keywords.map(k => [k.word, k.weight || k.count || 1]);
        WordCloud(container, {
            list: list,
            gridSize: 8,
            weightFactor: (size) => Math.max(12, size * 40),
            fontFamily: "Microsoft YaHei, sans-serif",
            color: () => {
                const colors = ["#00d4ff", "#10b981", "#f59e0b", "#60a5fa", "#a78bfa", "#f472b6"];
                return colors[Math.floor(Math.random() * colors.length)];
            },
            rotateRatio: 0.3,
            rotationSteps: 2,
            backgroundColor: "transparent",
        });
    },

    renderVolumeChart(data) {
        const container = document.getElementById("volumeChart");
        if (!container) return;
        container.innerHTML = "";

        if (this.charts.volume) this.charts.volume.dispose();
        const chart = echarts.init(container);
        this.charts.volume = chart;

        const stats = data.volume_stats || [];
        const platforms = stats.map(s => s.platform);
        const posData = stats.map(s => s.positive_count || 0);
        const negData = stats.map(s => s.negative_count || 0);
        const neuData = stats.map(s => s.neutral_count || 0);

        chart.setOption({
            tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
            legend: {
                data: ["正面", "负面", "中性"],
                textStyle: { color: "#9ca3af", fontSize: 11 },
                top: 0,
            },
            grid: { left: 40, right: 20, bottom: 30, top: 35 },
            xAxis: {
                type: "category",
                data: platforms,
                axisLabel: { color: "#6b7280", fontSize: 11 },
                axisLine: { lineStyle: { color: "#1e3a5f" } },
            },
            yAxis: {
                type: "value",
                axisLabel: { color: "#6b7280" },
                splitLine: { lineStyle: { color: "#1e3a5f33" } },
            },
            series: [
                { name: "正面", type: "bar", stack: "total", data: posData, itemStyle: { color: "#10b981" } },
                { name: "负面", type: "bar", stack: "total", data: negData, itemStyle: { color: "#ef4444" } },
                { name: "中性", type: "bar", stack: "total", data: neuData, itemStyle: { color: "#f59e0b" } },
            ],
        });
        window.addEventListener("resize", () => chart.resize());
    },

    renderTrendChart(data) {
        const container = document.getElementById("trendChart");
        if (!container) return;
        container.innerHTML = "";

        if (this.charts.trend) this.charts.trend.dispose();
        const chart = echarts.init(container);
        this.charts.trend = chart;

        const trends = data.time_trends || [];
        const dates = trends.map(t => t.date);
        const totalData = trends.map(t => t.total);
        const posData = trends.map(t => t.positive);
        const negData = trends.map(t => t.negative);

        chart.setOption({
            tooltip: { trigger: "axis" },
            legend: {
                data: ["总声量", "正面", "负面"],
                textStyle: { color: "#9ca3af", fontSize: 11 },
                top: 0,
            },
            grid: { left: 50, right: 20, bottom: 30, top: 35 },
            xAxis: {
                type: "category",
                data: dates,
                axisLabel: { color: "#6b7280", fontSize: 11, rotate: 30 },
                axisLine: { lineStyle: { color: "#1e3a5f" } },
                boundaryGap: false,
            },
            yAxis: {
                type: "value",
                axisLabel: { color: "#6b7280" },
                splitLine: { lineStyle: { color: "#1e3a5f33" } },
            },
            series: [
                { name: "总声量", type: "line", data: totalData, smooth: true, lineStyle: { color: "#00d4ff", width: 2 }, itemStyle: { color: "#00d4ff" }, areaStyle: { color: "rgba(0,212,255,0.1)" } },
                { name: "正面", type: "line", data: posData, smooth: true, lineStyle: { color: "#10b981", width: 1.5 }, itemStyle: { color: "#10b981" } },
                { name: "负面", type: "line", data: negData, smooth: true, lineStyle: { color: "#ef4444", width: 1.5 }, itemStyle: { color: "#ef4444" } },
            ],
        });
        window.addEventListener("resize", () => chart.resize());
    },

    renderInsightReport(data) {
        const container = document.getElementById("insightReport");
        if (!container) return;

        const report = data.insight_report || {};
        if (!report.executive_summary) {
            container.innerHTML = '<div class="insight-empty"><i class="fas fa-robot"></i><p>AI洞察报告生成中...</p></div>';
            return;
        }

        const qualityScore = data.quality_score || 0;
        const qualityPercent = Math.round(qualityScore * 100);
        const qualityColor = qualityPercent >= 70 ? "#10b981" : qualityPercent >= 50 ? "#f59e0b" : "#ef4444";

        let html = `
            <div class="insight-summary">
                <div class="insight-summary-icon"><i class="fas fa-brain"></i></div>
                <div class="insight-summary-text">${this.escapeHtml(report.executive_summary)}</div>
            </div>
            <div class="insight-quality">
                <span class="insight-quality-label">分析质量</span>
                <div class="insight-quality-bar">
                    <div class="insight-quality-fill" style="width:${qualityPercent}%;background:${qualityColor}"></div>
                </div>
                <span class="insight-quality-score" style="color:${qualityColor}">${qualityPercent}%</span>
            </div>
        `;

        if (report.key_findings && report.key_findings.length > 0) {
            html += '<div class="insight-section"><h4><i class="fas fa-lightbulb"></i> 关键发现</h4><ul>';
            report.key_findings.forEach(f => {
                html += `<li>${this.escapeHtml(f)}</li>`;
            });
            html += '</ul></div>';
        }

        if (report.risk_alerts && report.risk_alerts.length > 0) {
            html += '<div class="insight-section insight-risk"><h4><i class="fas fa-exclamation-triangle"></i> 风险预警</h4><ul>';
            report.risk_alerts.forEach(r => {
                html += `<li>${this.escapeHtml(r)}</li>`;
            });
            html += '</ul></div>';
        }

        if (report.recommendations && report.recommendations.length > 0) {
            html += '<div class="insight-section insight-recommend"><h4><i class="fas fa-clipboard-check"></i> 建议</h4><ul>';
            report.recommendations.forEach(r => {
                html += `<li>${this.escapeHtml(r)}</li>`;
            });
            html += '</ul></div>';
        }

        if (report.sentiment_overview) {
            html += `<div class="insight-sentiment-overview"><i class="fas fa-chart-line"></i> ${this.escapeHtml(report.sentiment_overview)}</div>`;
        }

        container.innerHTML = html;
    },

    renderDetails(data) {
        const container = document.getElementById("detailList");
        if (!container) return;

        this.currentDetails = data.details || [];
        this._renderFilteredDetails();
    },

    _renderFilteredDetails() {
        const container = document.getElementById("detailList");
        if (!container) return;

        let details = this.currentDetails;
        if (this.detailsSentiment) {
            details = details.filter(d => d.sentiment_label === this.detailsSentiment);
        }
        if (this.detailsPlatform) {
            details = details.filter(d => d.platform === this.detailsPlatform);
        }

        this._updatePlatformFilter();

        if (details.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-inbox"></i><p>暂无舆情详情</p></div>';
            return;
        }

        let html = "";
        details.slice(0, 50).forEach(item => {
            const sentimentClass = item.sentiment_label || "neutral";
            const sentimentText = {positive: "正面", negative: "负面", neutral: "中性"}[sentimentClass] || "中性";
            html += `
                <div class="detail-item">
                    <div class="detail-sentiment ${sentimentClass}"></div>
                    <div class="detail-content">
                        <div class="detail-title-row">
                            <span class="detail-title">${this.escapeHtml(item.title || "")}</span>
                            <span class="detail-sentiment-tag ${sentimentClass}">${sentimentText}</span>
                            <span class="detail-platform">${this.escapeHtml(item.platform || "")}</span>
                        </div>
                        <div class="detail-text">${this.escapeHtml(item.content || "")}</div>
                        <div class="detail-meta">
                            <span><i class="fas fa-user"></i> ${this.escapeHtml(item.author || "匿名")}</span>
                            <span><i class="fas fa-clock"></i> ${item.publish_time || "未知"}</span>
                            <span><i class="fas fa-thumbs-up"></i> ${item.like_count || 0}</span>
                            <span><i class="fas fa-comment"></i> ${item.comment_count || 0}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    },

    _updatePlatformFilter() {
        const select = document.getElementById("platformFilter");
        if (!select) return;
        const currentVal = select.value;
        const platforms = [...new Set(this.currentDetails.map(d => d.platform).filter(Boolean))];
        select.innerHTML = '<option value="">全部平台</option>';
        platforms.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p;
            opt.textContent = p;
            if (p === currentVal) opt.selected = true;
            select.appendChild(opt);
        });
    },

    clearDashboard() {
        document.getElementById("statTotal").textContent = "0";
        document.getElementById("statPositive").textContent = "0";
        document.getElementById("statNegative").textContent = "0";
        document.getElementById("statNeutral").textContent = "0";

        Object.values(this.charts).forEach(c => { if (c && c.dispose) c.dispose(); });
        this.charts = {};

        const wc = document.getElementById("wordCloudChart");
        if (wc) wc.innerHTML = "";

        const dl = document.getElementById("detailList");
        if (dl) dl.innerHTML = '<div class="empty-state"><i class="fas fa-search"></i><p>请输入车型开始舆情监控</p></div>';
    },

    showLoading(show) {
        const overlay = document.getElementById("loadingOverlay");
        if (overlay) {
            overlay.classList.toggle("active", show);
        }
    },

    showToast(message, type = "info") {
        const container = document.getElementById("toastContainer");
        if (!container) return;

        const icons = { success: "fa-check-circle", error: "fa-exclamation-circle", info: "fa-info-circle" };
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(100%)";
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    },
};

document.addEventListener("DOMContentLoaded", () => App.init());
