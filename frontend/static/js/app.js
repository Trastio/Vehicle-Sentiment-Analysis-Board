const { createApp } = Vue;

createApp({
    data() {
        return {
            vehicles: [],
            currentVehicleId: "",
            overview: {},
            trendData: [],
            platformDist: [],
            eventDist: [],
            opinionDist: [],
            competitorData: [],
            anomalies: [],
            commentSentimentDiff: [],
            posts: { items: [], total: 0, page: 1, size: 20 },
            reports: [],
            postsFilter: { sentiment: "", platform: "" },
            newVehicle: { name: "", brand: "", search_keywords: "" },
            showAddModal: false,
            loading: false,
            dialogOpen: false,
            dialogAnchorType: "",
            dialogAnchorData: {},
            dialogMessages: [],
            dialogConversationId: null,
            dialogInput: "",
            pipelinePhase: "idle",
            pipelineInfo: {},
            pipelinePollTimer: null,
            // Search combobox
            searchQuery: "",
            searchResults: [],
            searchDebounceTimer: null,
            // Group
            groups: [],
            currentGroupId: "",
            groupOverview: {},
            groupComparison: [],
            groupTrendData: [],
            showAddGroupModal: false,
            newGroup: { name: "", description: "" },
        };
    },
    async mounted() {
        await this.fetchVehicles();
        await this.loadGroups();
        window.addEventListener("resize", () => {
            this.trendChart?.resize();
            this.platformChart?.resize();
            this.eventChart?.resize();
            this.opinionChart?.resize();
            this.competitorChart?.resize();
            this.groupComparisonChart?.resize();
            this.groupTrendChart?.resize();
            this.groupRadarChart?.resize();
        });
    },
    methods: {
        async fetchVehicles() {
            const resp = await fetch("/api/vehicles");
            this.vehicles = await resp.json();
        },
        async addVehicle() {
            const kw = this.newVehicle.search_keywords
                ? this.newVehicle.search_keywords.split(",").map(s => s.trim()).filter(Boolean)
                : undefined;
            await fetch("/api/vehicles", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...this.newVehicle, search_keywords: kw }),
            });
            this.showAddModal = false;
            this.newVehicle = { name: "", brand: "", search_keywords: "" };
            await this.fetchVehicles();
        },
        async onVehicleChange() {
            if (!this.currentVehicleId) return;
            await Promise.all([
                this.loadOverview(),
                this.loadTrend(),
                this.loadPlatformDist(),
                this.loadEventDist(),
                this.loadOpinionTop(),
                this.loadCompetitorComparison(),
                this.loadAnomalies(),
                this.loadCommentSentimentDiff(),
                this.loadPosts(1),
                this.loadReports(),
            ]);
        },
        async loadOverview() {
            const resp = await fetch(`/api/dashboard/overview/${this.currentVehicleId}`);
            this.overview = await resp.json();
        },
        async loadTrend() {
            const end = new Date().toISOString().slice(0, 10);
            const start = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10);
            const resp = await fetch(`/api/dashboard/trend/${this.currentVehicleId}?start=${start}&end=${end}`);
            this.trendData = await resp.json();
            this.renderTrendChart();
        },
        bindChartClick(chart, anchorType) {
            if (!chart) return;
            chart.getZr().on("click", (params) => {
                const pointInPixel = [params.offsetX, params.offsetY];
                if (chart.containPixel("grid", pointInPixel)) {
                    const xIndex = chart.convertFromPixel({ seriesIndex: 0 }, pointInPixel)[0];
                    const option = chart.getOption();
                    if (option.xAxis && option.xAxis[0] && option.xAxis[0].data) {
                        const date = option.xAxis[0].data[Math.round(xIndex)];
                        if (date) openDialog(anchorType, { date: date });
                    }
                }
            });
            chart.on("click", (params) => {
                if (params.name) {
                    openDialog(anchorType, anchorType === "event" ? { event: params.name } : anchorType === "opinion" ? { opinion: params.name } : { [anchorType === "platform" ? "platform" : "date"]: params.name });
                }
            });
        },
        renderTrendChart() {
            const el = document.getElementById("trend-chart");
            if (!el) return;
            if (!this.trendChart) this.trendChart = echarts.init(el);
            const raw = this.trendData.data || this.trendData;
            const dates = raw.map(d => d.date);
            this.trendChart.setOption({
                tooltip: { trigger: "axis" },
                legend: { data: ["讨论声量", "媒体声量", "互动烈度", "注意力指数"] },
                xAxis: { type: "category", data: dates },
                yAxis: [
                    { type: "value", name: "声量/互动" },
                    { type: "value", name: "百度指数", position: "right" },
                ],
                dataZoom: [{ type: "inside" }],
                series: [
                    { name: "讨论声量", type: "line", data: raw.map(d => d.discussion_volume), smooth: true },
                    { name: "媒体声量", type: "line", data: raw.map(d => d.media_volume), smooth: true },
                    { name: "互动烈度", type: "line", data: raw.map(d => d.interaction_intensity), smooth: true },
                    { name: "注意力指数", type: "line", yAxisIndex: 1, data: raw.map(d => d.attention_index), smooth: true, lineStyle: { type: "dashed" } },
                ],
            }, true);
            this.bindChartClick(this.trendChart, "trend");
        },
        async loadPlatformDist() {
            const resp = await fetch(`/api/dashboard/platform-distribution/${this.currentVehicleId}`);
            this.platformDist = await resp.json();
            this.renderPlatformChart();
        },
        renderPlatformChart() {
            const el = document.getElementById("platform-chart");
            if (!el) return;
            if (!this.platformChart) this.platformChart = echarts.init(el);
            this.platformChart.setOption({
                tooltip: { trigger: "item" },
                series: [{
                    type: "pie", radius: ["40%", "70%"],
                    data: this.platformDist.map(d => ({ name: d.platform, value: d.count })),
                }],
            }, true);
            this.bindChartClick(this.platformChart, "platform");
        },
        async loadEventDist() {
            const resp = await fetch(`/api/dashboard/event-distribution/${this.currentVehicleId}`);
            this.eventDist = await resp.json();
            this.renderEventChart();
        },
        renderEventChart() {
            const el = document.getElementById("event-chart");
            if (!el) return;
            if (!this.eventChart) this.eventChart = echarts.init(el);
            const data = this.eventDist.slice(0, 10);
            this.eventChart.setOption({
                tooltip: {},
                xAxis: { type: "category", data: data.map(d => d[0]), axisLabel: { rotate: 30 } },
                yAxis: { type: "value" },
                series: [{ type: "bar", data: data.map(d => d[1]) }],
            }, true);
            this.bindChartClick(this.eventChart, "event");
        },
        async loadOpinionTop() {
            const resp = await fetch(`/api/analysis/top-opinions/${this.currentVehicleId}`);
            this.opinionDist = await resp.json();
            this.renderOpinionChart();
        },
        renderOpinionChart() {
            const el = document.getElementById("opinion-chart");
            if (!el) return;
            if (!this.opinionChart) this.opinionChart = echarts.init(el);
            const data = (this.opinionDist || []).slice(0, 10).reverse();
            this.opinionChart.setOption({
                tooltip: {},
                xAxis: { type: "value" },
                yAxis: { type: "category", data: data.map(d => d[0]) },
                series: [{ type: "bar", data: data.map(d => d[1]), itemStyle: { color: "#5470c6" } }],
            }, true);
            this.bindChartClick(this.opinionChart, "opinion");
        },
        async loadCompetitorComparison() {
            const resp = await fetch(`/api/dashboard/competitor-comparison/${this.currentVehicleId}`);
            this.competitorData = await resp.json();
            if (this.competitorData.length > 1) {
                this.renderCompetitorChart();
            }
        },
        renderCompetitorChart() {
            const el = document.getElementById("competitor-chart");
            if (!el) return;
            if (!this.competitorChart) this.competitorChart = echarts.init(el);
            const names = this.competitorData.map(d => d.name);
            this.competitorChart.setOption({
                tooltip: {},
                legend: { data: ["正面", "负面", "中性"] },
                xAxis: { type: "category", data: names },
                yAxis: { type: "value" },
                series: [
                    { name: "正面", type: "bar", stack: "sentiment", data: this.competitorData.map(d => d.positive), itemStyle: { color: "#67c23a" } },
                    { name: "负面", type: "bar", stack: "sentiment", data: this.competitorData.map(d => d.negative), itemStyle: { color: "#f56c6c" } },
                    { name: "中性", type: "bar", stack: "sentiment", data: this.competitorData.map(d => d.neutral), itemStyle: { color: "#909399" } },
                ],
            }, true);
        },
        async loadAnomalies() {
            const end = new Date().toISOString().slice(0, 10);
            const start = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
            const resp = await fetch(`/api/dashboard/anomaly-timeline/${this.currentVehicleId}?start=${start}&end=${end}`);
            this.anomalies = await resp.json();
        },
        async loadCommentSentimentDiff() {
            const resp = await fetch(`/api/dashboard/comment-sentiment-diff/${this.currentVehicleId}`);
            this.commentSentimentDiff = resp.ok ? await resp.json() : [];
        },
        sentimentLabel(s) {
            return { positive: "正面", negative: "负面", neutral: "中性", mixed: "混合" }[s] || s;
        },
        async loadPosts(page) {
            const params = new URLSearchParams({ page, size: this.posts.size });
            if (this.postsFilter.sentiment) params.set("sentiment", this.postsFilter.sentiment);
            if (this.postsFilter.platform) params.set("platform", this.postsFilter.platform);
            const resp = await fetch(`/api/dashboard/posts/${this.currentVehicleId}?${params}`);
            this.posts = await resp.json();
        },
        async loadReports() {
            const resp = await fetch(`/api/dashboard/reports/${this.currentVehicleId}`);
            this.reports = await resp.json();
        },
        async triggerCollection() {
            this.loading = true;
            this.pipelinePhase = "collecting";
            const resp = await fetch(`/api/vehicles/${this.currentVehicleId}/collect`, { method: "POST" });
            const data = await resp.json();
            if (data.status === "already_running") {
                this.pipelinePhase = data.phase;
            }
            this._startPolling();
        },
        async triggerAnalysis() {
            this.loading = true;
            this.pipelinePhase = "analyzing";
            const resp = await fetch(`/api/analysis/trigger/${this.currentVehicleId}`, { method: "POST" });
            const data = await resp.json();
            if (data.status === "already_running") {
                this.pipelinePhase = data.phase;
            }
            this._startPolling();
        },
        _startPolling() {
            if (this.pipelinePollTimer) clearInterval(this.pipelinePollTimer);
            this.pipelinePollTimer = setInterval(() => this._pollPipeline(), 3000);
            this._pollPipeline();
        },
        async _pollPipeline() {
            try {
                const resp = await fetch(`/api/vehicles/${this.currentVehicleId}/pipeline-status`);
                if (!resp.ok) return;
                const data = await resp.json();
                this.pipelinePhase = data.phase;
                this.pipelineInfo = data;

                if (data.phase === "completed" || data.phase === "error") {
                    clearInterval(this.pipelinePollTimer);
                    this.pipelinePollTimer = null;
                    this.loading = false;
                    if (data.phase === "completed") {
                        await this.onVehicleChange();
                    }
                }
            } catch (e) {
                // keep polling on network error
            }
        },
        closeDialog() {
            closeDialog();
        },
        // --- Search Combobox ---
        onSearchInput() {
            clearTimeout(this.searchDebounceTimer);
            const q = this.searchQuery.trim();
            if (!q) {
                this.searchResults = [];
                return;
            }
            this.searchDebounceTimer = setTimeout(async () => {
                try {
                    const resp = await fetch(`/api/vehicles/search?q=${encodeURIComponent(q)}`);
                    if (resp.ok) {
                        this.searchResults = await resp.json();
                    }
                } catch (e) {}
            }, 300);
        },
        onSearchFocus() {
            if (this.searchQuery.trim() && this.searchResults.length) {
                // results already visible via v-if
            }
        },
        onSearchBlur() {
            // small delay so mousedown on item fires first
            setTimeout(() => { this.searchResults = []; }, 200);
        },
        selectVehicle(v) {
            this.currentVehicleId = v.id;
            this.searchQuery = `${v.name} (${v.brand})`;
            this.searchResults = [];
            this.currentGroupId = "";
            this.groupOverview = {};
            this.onVehicleChange();
        },
        // --- Group ---
        async loadGroups() {
            try {
                const resp = await fetch("/api/groups");
                if (resp.ok) {
                    this.groups = await resp.json();
                }
            } catch (e) {}
        },
        async onGroupChange() {
            const groupId = this.currentGroupId;
            if (!groupId) {
                this.groupOverview = {};
                return;
            }
            this.currentVehicleId = "";
            this.searchQuery = "";
            try {
                const [overviewResp, comparisonResp] = await Promise.all([
                    fetch(`/api/groups/${groupId}/overview`),
                    fetch(`/api/groups/${groupId}/comparison`),
                ]);
                if (!overviewResp.ok) return;
                this.groupOverview = await overviewResp.json();
                this.groupComparison = comparisonResp.ok ? await comparisonResp.json() : [];
                this.$nextTick(() => {
                    this.renderGroupComparisonChart();
                    if (this.groupComparison.length > 1) {
                        this.loadGroupTrend(groupId);
                        this.renderGroupRadarChart();
                    }
                });
            } catch (e) {}
        },
        selectGroupVehicle(vehicleId) {
            this.currentGroupId = "";
            this.groupOverview = {};
            this.currentVehicleId = vehicleId;
            const gv = this.groupOverview.cards?.find(v => v.vehicle_id === vehicleId);
            this.searchQuery = gv ? gv.name : "";
            this.onVehicleChange();
        },
        renderGroupComparisonChart() {
            const el = document.getElementById("group-comparison-chart");
            if (!el) return;
            const vlist = this.groupComparison || [];
            if (vlist.length < 1) return;
            if (!this.groupComparisonChart) this.groupComparisonChart = echarts.init(el);
            this.groupComparisonChart.setOption({
                tooltip: {},
                legend: { data: ["正面", "负面", "中性"] },
                xAxis: { type: "category", data: vlist.map(v => v.name) },
                yAxis: { type: "value" },
                series: [
                    { name: "正面", type: "bar", stack: "sentiment", data: vlist.map(v => v.positive || 0), itemStyle: { color: "#67c23a" } },
                    { name: "负面", type: "bar", stack: "sentiment", data: vlist.map(v => v.negative || 0), itemStyle: { color: "#f56c6c" } },
                    { name: "中性", type: "bar", stack: "sentiment", data: vlist.map(v => v.neutral || 0), itemStyle: { color: "#909399" } },
                ],
            }, true);
        },
        async loadGroupTrend(groupId) {
            const end = new Date().toISOString().slice(0, 10);
            const start = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10);
            const resp = await fetch(`/api/groups/${groupId}/trend?start=${start}&end=${end}`);
            if (!resp.ok) return;
            this.groupTrendData = await resp.json();
            this.renderGroupTrendChart();
        },
        renderGroupTrendChart() {
            const el = document.getElementById("group-trend-chart");
            if (!el) return;
            if (!this.groupTrendData || !this.groupTrendData.length) return;
            if (!this.groupTrendChart) this.groupTrendChart = echarts.init(el);
            const colors = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de"];
            const series = [];
            const legendData = [];
            let allDates = new Set();
            this.groupTrendData.forEach(s => {
                legendData.push(s.name);
                s.data.forEach(d => allDates.add(d.date));
            });
            const dates = [...allDates].sort();
            this.groupTrendData.forEach((s, i) => {
                const dateMap = {};
                s.data.forEach(d => { dateMap[d.date] = d.discussion_volume; });
                series.push({
                    name: s.name, type: "line", smooth: true,
                    data: dates.map(d => dateMap[d] ?? null),
                    itemStyle: { color: colors[i % colors.length] },
                });
            });
            this.groupTrendChart.setOption({
                tooltip: { trigger: "axis" },
                legend: { data: legendData },
                xAxis: { type: "category", data: dates },
                yAxis: { type: "value", name: "讨论声量" },
                dataZoom: [{ type: "inside" }],
                series,
            }, true);
        },
        renderGroupRadarChart() {
            const el = document.getElementById("group-radar-chart");
            if (!el) return;
            const vlist = this.groupComparison || [];
            if (vlist.length < 1) return;
            // Collect all dimensions across vehicles
            const dimSet = new Set();
            vlist.forEach(v => {
                Object.keys(v.dim_sentiment || {}).forEach(d => dimSet.add(d));
            });
            const dims = [...dimSet];
            if (!dims.length) return;
            if (!this.groupRadarChart) this.groupRadarChart = echarts.init(el);
            const colors = ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de"];
            this.groupRadarChart.setOption({
                tooltip: {},
                legend: { data: vlist.map(v => v.name) },
                radar: {
                    indicator: dims.map(d => ({ name: d, max: 1, min: -1 })),
                },
                series: [{
                    type: "radar",
                    data: vlist.map((v, i) => ({
                        name: v.name,
                        value: dims.map(d => v.dim_sentiment?.[d] ?? 0),
                        itemStyle: { color: colors[i % colors.length] },
                    })),
                }],
            }, true);
        },
        async addGroup() {
            const resp = await fetch("/api/groups", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(this.newGroup),
            });
            if (resp.ok) {
                this.showAddGroupModal = false;
                this.newGroup = { name: "", description: "" };
                await this.loadGroups();
            }
        },
        renderGenerativeUI(content) {
            return parseGenerativeUI(content);
        },
        async sendDialogMessage() {
            if (!this.dialogAnchorType && !this.dialogConversationId) return;
            const userMsg = this.dialogInput;
            if (userMsg) {
                this.dialogMessages.push({ id: Date.now(), role: "user", content: userMsg });
            }
            this.dialogInput = "";

            const body = {
                vehicle_id: this.currentVehicleId,
                anchor_type: this.dialogAnchorType,
                anchor_data: this.dialogAnchorData,
                message: userMsg,
            };
            if (this.dialogConversationId) body.conversation_id = this.dialogConversationId;

            const resp = await fetch("/api/dialog/anchor", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let assistantContent = "";
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.type === "text") assistantContent += data.content;
                            if (data.type === "done") this.dialogConversationId = data.conversation_id;
                        } catch (e) {}
                    }
                }
            }

            if (assistantContent) {
                this.dialogMessages.push({ id: Date.now(), role: "assistant", content: assistantContent });
            }

            this.$nextTick(() => {
                const container = this.$refs.dialogMessages;
                if (container) container.scrollTop = container.scrollHeight;
            });
        },
    },
}).mount("#app");
