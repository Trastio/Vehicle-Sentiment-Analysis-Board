function parseGenerativeUI(text) {
    if (!text) return "";
    const uiTypes = ["text", "chart", "table", "stat_cards", "post_list"];
    let html = text;

    uiTypes.forEach(function(type) {
        const regex = new RegExp("\\[GEN_UI:" + type + "\\]([\\s\\S]*?)\\[/GEN_UI\\]", "g");
        html = html.replace(regex, function(match, content) {
            if (type === "text") {
                return "<div class='gen-ui-text'>" + content + "</div>";
            }
            if (type === "chart") {
                return "<div class=\"gen-ui-chart\" data-chart=\"" + content.replace(/"/g, "&quot;") + "\"></div>";
            }
            if (type === "table") {
                try {
                    const data = JSON.parse(content);
                    var rows = data.rows || [];
                    var headers = data.headers || [];
                    var tableHtml = "<table class='gen-ui-table'><thead><tr>";
                    headers.forEach(function(h) { tableHtml += "<th>" + h + "</th>"; });
                    tableHtml += "</tr></thead><tbody>";
                    rows.forEach(function(row) {
                        tableHtml += "<tr>";
                        row.forEach(function(cell) { tableHtml += "<td>" + cell + "</td>"; });
                        tableHtml += "</tr>";
                    });
                    tableHtml += "</tbody></table>";
                    return tableHtml;
                } catch (e) {
                    return "<div class='gen-ui-error'>Table render error</div>";
                }
            }
            if (type === "stat_cards") {
                try {
                    const cards = JSON.parse(content);
                    var cardsHtml = "<div class='gen-ui-cards'>";
                    cards.forEach(function(c) {
                        cardsHtml += "<div class='gen-ui-card'><div class='gen-ui-card-value'>" + c.value + "</div><div class='gen-ui-card-label'>" + c.label + "</div></div>";
                    });
                    cardsHtml += "</div>";
                    return cardsHtml;
                } catch (e) {
                    return "<div class='gen-ui-error'>Cards render error</div>";
                }
            }
            if (type === "post_list") {
                try {
                    const posts = JSON.parse(content);
                    var listHtml = "<div class='gen-ui-posts'>";
                    posts.forEach(function(p) {
                        listHtml += "<div class='gen-ui-post'><strong>" + (p.title || "") + "</strong><p>" + (p.content || "").substring(0, 100) + "</p></div>";
                    });
                    listHtml += "</div>";
                    return listHtml;
                } catch (e) {
                    return "<div class='gen-ui-error'>Post list render error</div>";
                }
            }
            return match;
        });
    });

    return html;
}

function openDialog(anchorType, anchorData) {
    var app = document.querySelector("#app").__vue_app__;
    if (!app) return;
    var vm = app._instance.proxy;
    vm.dialogOpen = true;
    vm.dialogAnchorType = anchorType;
    vm.dialogAnchorData = anchorData;
    vm.dialogMessages = [];
    vm.dialogConversationId = null;
    vm.dialogInput = "";

    vm.sendDialogMessage();
}

function closeDialog() {
    var app = document.querySelector("#app").__vue_app__;
    if (!app) return;
    var vm = app._instance.proxy;
    vm.dialogOpen = false;
    vm.dialogMessages = [];
    vm.dialogConversationId = null;
}
