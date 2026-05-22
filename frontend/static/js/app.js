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
            anomalies: [],
            posts: { items: [], total: 0, page: 1, size: 20 },
            reports: [],
            postsFilter: { sentiment: "", platform: "" },
            newVehicle: { name: "", brand: "", search_keywords: "" },
            showAddModal: false,
            loading: false,
        };
    },
    async mounted() {
        await this.fetchVehicles();
        window.addEventListener("resize", () => {
            this.trendChart?.resize();
            this.platformChart?.resize();
            this.eventChart?.resize();
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
                this.loadAnomalies(),
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
        renderTrendChart() {
            const el = document.getElementById("trend-chart");
            if (!el) return;
            if (!this.trendChart) this.trendChart = echarts.init(el);
            const dates = this.trendData.map(d => d.date);
            this.trendChart.setOption({
                tooltip: { trigger: "axis" },
                legend: { data: ["讨论声量", "媒体声量", "互动烈度"] },
                xAxis: { type: "category", data: dates },
                yAxis: { type: "value" },
                dataZoom: [{ type: "inside" }],
                series: [
                    { name: "讨论声量", type: "line", data: this.trendData.map(d => d.discussion_volume), smooth: true },
                    { name: "媒体声量", type: "line", data: this.trendData.map(d => d.media_volume), smooth: true },
                    { name: "互动烈度", type: "line", data: this.trendData.map(d => d.interaction_intensity), smooth: true },
                ],
            });
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
            });
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
            });
        },
        async loadAnomalies() {
            const end = new Date().toISOString().slice(0, 10);
            const start = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
            const resp = await fetch(`/api/dashboard/anomaly-timeline/${this.currentVehicleId}?start=${start}&end=${end}`);
            this.anomalies = await resp.json();
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
            await fetch(`/api/vehicles/${this.currentVehicleId}/collect`, { method: "POST" });
            this.loading = false;
            await this.onVehicleChange();
        },
        async triggerAnalysis() {
            this.loading = true;
            await fetch(`/api/analysis/trigger/${this.currentVehicleId}`, { method: "POST" });
            this.loading = false;
            await this.onVehicleChange();
        },
    },
}).mount("#app");
