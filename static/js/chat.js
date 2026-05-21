var ChatApp = (function () {
    var conversationId = "";
    var isLoading = false;
    var currentReader = null;
    var inputEnabled = true;
    var sidebarVisible = false;

    function toggleSidebar() {
        var sidebar = document.getElementById("sidebar");
        var overlay = document.getElementById("sidebarOverlay");
        sidebarVisible = !sidebarVisible;
        if (sidebarVisible) {
            sidebar.classList.remove("hidden");
            if (window.innerWidth <= 768) {
                overlay.classList.add("active");
            }
        } else {
            sidebar.classList.add("hidden");
            overlay.classList.remove("active");
        }
    }

    function loadConversations() {
        fetch("/api/conversations")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var convs = data.conversations || [];
                var list = document.getElementById("conversationList");
                if (!list) return;
                list.innerHTML = "";
                convs.forEach(function (conv) {
                    var item = document.createElement("div");
                    item.className = "conv-item" + (conv.id === conversationId ? " active" : "");
                    item.innerHTML =
                        '<div class="conv-item-icon"><i class="fas fa-comment"></i></div>' +
                        '<div class="conv-item-info">' +
                        '<div class="conv-item-title">' + escapeHtml(conv.title || "新对话") + '</div>' +
                        '<div class="conv-item-time">' + (conv.created_at || "") + '</div>' +
                        '</div>' +
                        '<button class="conv-item-delete" data-id="' + conv.id + '" title="删除对话"><i class="fas fa-trash"></i></button>';
                    item.addEventListener("click", function (e) {
                        if (e.target.closest(".conv-item-delete")) return;
                        switchConversation(conv.id);
                    });
                    var deleteBtn = item.querySelector(".conv-item-delete");
                    deleteBtn.addEventListener("click", function (e) {
                        e.stopPropagation();
                        deleteConversation(conv.id);
                    });
                    list.appendChild(item);
                });
            })
            .catch(function (e) { console.error("加载会话列表失败:", e); });
    }

    function switchConversation(convId) {
        if (isLoading) return;
        if (currentReader) {
            try { currentReader.cancel(); } catch (e) {}
            currentReader = null;
        }
        conversationId = convId;
        isLoading = false;
        inputEnabled = true;
        updateSendButton(false);
        updateInputState(false);

        var container = document.getElementById("chatMessages");
        container.innerHTML = "";

        loadMessages(convId);
        loadConversations();

        if (window.innerWidth <= 768) {
            toggleSidebar();
        }
    }

    function deleteConversation(convId) {
        if (!confirm("确定要删除这个对话吗？")) return;
        fetch("/api/conversations/" + convId, { method: "DELETE" })
            .then(function () {
                if (convId === conversationId) {
                    newConversation();
                }
                loadConversations();
            })
            .catch(function (e) { console.error("删除对话失败:", e); });
    }

    function newConversation() {
        if (currentReader) {
            try { currentReader.cancel(); } catch (e) {}
            currentReader = null;
        }
        conversationId = "";
        isLoading = false;
        inputEnabled = true;
        updateSendButton(false);
        updateInputState(false);

        var container = document.getElementById("chatMessages");
        container.innerHTML = "";
        var welcome = document.createElement("div");
        welcome.className = "welcome-message";
        welcome.id = "welcomeMessage";
        welcome.innerHTML =
            '<div class="welcome-bg"></div>' +
            '<div class="welcome-content">' +
            '<div class="welcome-icon-wrapper">' +
            '<div class="welcome-icon"><i class="fas fa-robot"></i></div>' +
            '<div class="welcome-icon-ring"></div>' +
            '</div>' +
            '<h2>您好！我是 AutoPulse</h2>' +
            '<p class="welcome-desc">汽车舆情智能监控助手，为您提供全方位的舆情分析与报告服务</p>' +
            '<div class="welcome-features">' +
            '<div class="feature-item"><i class="fas fa-search"></i><span>舆情查询</span></div>' +
            '<div class="feature-item"><i class="fas fa-chart-bar"></i><span>可视化报告</span></div>' +
            '<div class="feature-item"><i class="fas fa-file-alt"></i><span>舆情报告</span></div>' +
            '</div>' +
            '<div class="quick-tags">' +
            '<div class="quick-tag-label">快速体验：</div>' +
            '<span class="quick-tag" onclick="ChatApp.sendQuickTag(\'帮我分析比亚迪秦PLUS的舆情\')"><i class="fas fa-bolt"></i> 比亚迪秦PLUS</span>' +
            '<span class="quick-tag" onclick="ChatApp.sendQuickTag(\'帮我分析特斯拉Model 3的舆情\')"><i class="fas fa-bolt"></i> 特斯拉Model 3</span>' +
            '<span class="quick-tag" onclick="ChatApp.sendQuickTag(\'帮我分析比亚迪汉的舆情\')"><i class="fas fa-bolt"></i> 比亚迪汉</span>' +
            '<span class="quick-tag" onclick="ChatApp.sendQuickTag(\'帮我分析蔚来ES6的舆情\')"><i class="fas fa-bolt"></i> 蔚来ES6</span>' +
            '<span class="quick-tag" onclick="ChatApp.sendQuickTag(\'帮我分析小鹏P7的舆情\')"><i class="fas fa-bolt"></i> 小鹏P7</span>' +
            '<span class="quick-tag" onclick="ChatApp.sendQuickTag(\'帮我分析理想L7的舆情\')"><i class="fas fa-bolt"></i> 理想L7</span>' +
            '<span class="quick-tag" onclick="ChatApp.sendQuickTag(\'帮我分析问界M7的舆情\')"><i class="fas fa-bolt"></i> 问界M7</span>' +
            '</div>' +
            '</div>';
        container.appendChild(welcome);
        showToast("已创建新对话", "success");
        loadConversations();
    }

    function init() {
        var input = document.getElementById("chatInput");
        if (input) {
            input.addEventListener("keydown", function (e) {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
            input.addEventListener("input", function () {
                autoResizeInput();
            });
        }

        var sidebar = document.getElementById("sidebar");
        if (window.innerWidth > 768) {
            sidebarVisible = true;
            sidebar.classList.remove("hidden");
        } else {
            sidebar.classList.add("hidden");
        }

        loadConversation();
        loadConversations();
    }

    function autoResizeInput() {
        var input = document.getElementById("chatInput");
        if (!input) return;
        input.style.height = "auto";
        var newHeight = Math.min(input.scrollHeight, 120);
        input.style.height = newHeight + "px";
    }

    function loadConversation() {
        fetch("/api/conversations")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var convs = data.conversations || [];
                if (convs.length > 0) {
                    conversationId = convs[0].id;
                    loadMessages(conversationId);
                }
            })
            .catch(function (e) { console.error("加载会话失败:", e); });
    }

    function loadMessages(convId) {
        fetch("/api/conversations/" + convId + "/messages")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var msgs = data.messages || [];
                if (msgs.length > 0) {
                    hideWelcome();
                    var lastCarModel = "";
                    msgs.forEach(function (msg) {
                        if (msg.role === "user") {
                            appendUserMessage(msg.content);
                        } else if (msg.role === "assistant") {
                            var meta = {};
                            try { meta = JSON.parse(msg.metadata || "{}"); } catch (e) {}
                            if (msg.message_type === "visual_report") {
                                appendReportMessage(msg.content, "visual_report", meta);
                            } else if (msg.message_type === "opinion_report") {
                                appendReportMessage(msg.content, "opinion_report", meta);
                            } else {
                                var buttons = [];
                                var carModel = meta.car_model || lastCarModel || "";
                                if (carModel && msg.content && msg.content.length > 50) {
                                    buttons = [
                                        { label: "📊 查看可视化报告", action: "visual_report" },
                                        { label: "📄 生成舆情报告", action: "opinion_report" },
                                    ];
                                }
                                appendAssistantMessage(msg.content, buttons, carModel);
                            }
                            if (meta.car_model) {
                                lastCarModel = meta.car_model;
                            }
                        }
                    });
                    scrollToBottom();
                }
            })
            .catch(function (e) { console.error("加载消息失败:", e); });
    }

    function sendMessage() {
        if (isLoading) return;
        var input = document.getElementById("chatInput");
        var text = (input.value || "").trim();
        if (!text) return;

        input.value = "";
        input.style.height = "auto";
        input.focus();
        hideWelcome();
        appendUserMessage(text);
        scrollToBottom();

        isLoading = true;
        inputEnabled = false;
        updateSendButton(true);
        updateInputState(true);

        var assistantEl = createAssistantBubble();
        var contentEl = assistantEl.querySelector(".message-content");
        var hasReceivedContent = false;

        fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, conversation_id: conversationId }),
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("请求失败: " + response.status);
                }
                currentReader = response.body.getReader();
                var decoder = new TextDecoder();
                var buffer = "";

                function read() {
                    currentReader.read().then(function (result) {
                        if (result.done) {
                            if (!hasReceivedContent) {
                                contentEl.innerHTML = '<div class="error-message"><i class="fas fa-exclamation-circle"></i> 未收到有效响应</div>';
                            }
                            finishLoading();
                            return;
                        }

                        buffer += decoder.decode(result.value, { stream: true });
                        var lines = buffer.split("\n");
                        buffer = lines.pop();

                        lines.forEach(function (line) {
                            if (line.startsWith("data: ")) {
                                try {
                                    var event = JSON.parse(line.substring(6));
                                    var gotContent = handleSSEEvent(event, contentEl, assistantEl);
                                    if (gotContent) hasReceivedContent = true;
                                } catch (e) {
                                    console.warn("SSE解析错误:", e);
                                }
                            }
                        });

                        scrollToBottom();
                        read();
                    }).catch(function (e) {
                        console.error("SSE读取错误:", e);
                        if (!hasReceivedContent) {
                            contentEl.innerHTML = '<div class="error-message"><i class="fas fa-exclamation-circle"></i> 连接中断，请重试</div>';
                        }
                        finishLoading();
                    });
                }

                read();
            })
            .catch(function (e) {
                console.error("发送消息失败:", e);
                contentEl.innerHTML = '<div class="error-message"><i class="fas fa-exclamation-circle"></i> 发送失败，请重试</div>';
                finishLoading();
            });
    }

    function finishLoading() {
        isLoading = false;
        inputEnabled = true;
        updateSendButton(false);
        updateInputState(false);
        currentReader = null;
        loadConversations();
    }

    function updateInputState(disabled) {
        var input = document.getElementById("chatInput");
        if (input) {
            input.disabled = disabled;
            if (!disabled) {
                input.focus();
            }
        }
    }

    function handleSSEEvent(event, contentEl, assistantEl) {
        var type = event.type;
        var gotContent = false;

        if (type === "connected") {
            if (event.conversation_id) {
                conversationId = event.conversation_id;
            }
        } else if (type === "progress") {
            contentEl.innerHTML =
                '<div class="progress-indicator">' +
                '<i class="fas fa-spinner fa-spin"></i> ' +
                escapeHtml(event.content || "处理中...") +
                '<span class="progress-dots"><span></span><span></span><span></span></span>' +
                '</div>';
        } else if (type === "text") {
            gotContent = true;
            if (event.conversation_id) {
                conversationId = event.conversation_id;
            }
            contentEl.innerHTML = formatText(event.content || "");
            var buttons = event.buttons || [];
            if (buttons.length > 0) {
                appendActionButtons(contentEl, buttons, event.car_model || "");
            }
        } else if (type === "visual_report") {
            gotContent = true;
            if (event.conversation_id) {
                conversationId = event.conversation_id;
            }
            var reportUrl = event.report_url || "";
            contentEl.innerHTML = formatText(event.content || "");
            appendReportOpenButton(contentEl, reportUrl, "visual_report");
            showToast("可视化报告已生成，点击按钮查看", "success");
        } else if (type === "opinion_report") {
            gotContent = true;
            if (event.conversation_id) {
                conversationId = event.conversation_id;
            }
            var reportUrl = event.report_url || "";
            contentEl.innerHTML = formatText(event.content || "");
            appendReportOpenButton(contentEl, reportUrl, "opinion_report");
            showToast("舆情报告已生成，点击按钮查看", "success");
        } else if (type === "error") {
            gotContent = true;
            contentEl.innerHTML =
                '<div class="error-message"><i class="fas fa-exclamation-circle"></i> ' +
                escapeHtml(event.content || "发生错误") + '</div>';
            showToast(event.content || "发生错误", "error");
        } else if (type === "done") {
            if (!contentEl.innerHTML || contentEl.querySelector(".progress-indicator")) {
                contentEl.innerHTML = '<div class="error-message"><i class="fas fa-exclamation-circle"></i> 响应异常，请重试</div>';
            }
            finishLoading();
        }

        return gotContent;
    }

    function sendQuickTag(text) {
        if (isLoading) return;
        var input = document.getElementById("chatInput");
        if (input) input.value = text;
        sendMessage();
    }

    function sendAction(action, carModel) {
        if (isLoading) return;
        var messages = {
            visual_report: "生成" + carModel + "的可视化报告",
            opinion_report: "生成" + carModel + "的舆情报告",
            drill_down: "深入分析" + carModel + "的舆情",
        };
        var text = messages[action] || action;
        var input = document.getElementById("chatInput");
        if (input) input.value = text;
        sendMessage();
    }

    function hideWelcome() {
        var el = document.getElementById("welcomeMessage");
        if (el) {
            el.style.opacity = "0";
            el.style.transform = "translateY(-20px)";
            el.style.transition = "all 0.3s ease";
            setTimeout(function () {
                if (el.parentNode) el.style.display = "none";
            }, 300);
        }
    }

    function appendUserMessage(text) {
        var container = document.getElementById("chatMessages");
        var div = document.createElement("div");
        div.className = "message-row user-row";
        div.innerHTML =
            '<div class="message-bubble user-bubble"><div class="message-content">' +
            escapeHtml(text) + '</div></div>';
        container.appendChild(div);
    }

    function createAssistantBubble() {
        var container = document.getElementById("chatMessages");
        var div = document.createElement("div");
        div.className = "message-row assistant-row";
        div.innerHTML =
            '<div class="assistant-avatar"><i class="fas fa-robot"></i></div>' +
            '<div class="message-bubble assistant-bubble"><div class="message-content">' +
            '<div class="progress-indicator">' +
            '<i class="fas fa-spinner fa-spin"></i> 思考中' +
            '<span class="progress-dots"><span></span><span></span><span></span></span>' +
            '</div></div></div>';
        container.appendChild(div);
        scrollToBottom();
        return div;
    }

    function appendAssistantMessage(text, buttons, carModel) {
        var container = document.getElementById("chatMessages");
        var div = document.createElement("div");
        div.className = "message-row assistant-row";
        var html =
            '<div class="assistant-avatar"><i class="fas fa-robot"></i></div>' +
            '<div class="message-bubble assistant-bubble"><div class="message-content">' +
            formatText(text);

        if (buttons && buttons.length > 0) {
            html += '<div class="action-buttons">';
            buttons.forEach(function (btn) {
                var safeCarModel = escapeAttr(carModel || "");
                html += '<button class="action-btn" data-action="' +
                    escapeAttr(btn.action) + '" data-carmodel="' +
                    safeCarModel + '">' +
                    escapeHtml(btn.label) + '</button>';
            });
            html += '</div>';
        }

        html += '</div></div>';
        div.innerHTML = html;

        var actionBtns = div.querySelectorAll(".action-btn");
        actionBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                var action = btn.getAttribute("data-action");
                var model = btn.getAttribute("data-carmodel");
                sendAction(action, model);
            });
        });

        container.appendChild(div);
    }

    function appendReportMessage(text, reportType, meta) {
        var container = document.getElementById("chatMessages");
        var div = document.createElement("div");
        div.className = "message-row assistant-row";
        var html =
            '<div class="assistant-avatar"><i class="fas fa-robot"></i></div>' +
            '<div class="message-bubble assistant-bubble"><div class="message-content">' +
            formatText(text);

        var reportUrl = "";
        if (meta.report_path) {
            reportUrl = "/api/report/file/" + encodeURIComponent(meta.report_path);
        } else if (meta.car_model) {
            reportUrl = "/api/report/" +
                (reportType === "visual_report" ? "visual" : "opinion") +
                '/' + encodeURIComponent(meta.car_model);
        }

        if (reportUrl) {
            html += '<div class="report-open-btn-wrapper">';
            var icon = reportType === "visual_report" ? "fa-chart-bar" : "fa-file-alt";
            var label = reportType === "visual_report" ? "在新窗口查看可视化报告" : "在新窗口查看舆情报告";
            html += '<a href="' + escapeAttr(reportUrl) + '" target="_blank" class="report-open-btn">';
            html += '<i class="fas ' + icon + '"></i> <span>' + label + '</span>';
            html += '</a></div>';
        }

        html += '</div></div>';
        div.innerHTML = html;
        container.appendChild(div);
    }

    function appendActionButtons(contentEl, buttons, carModel) {
        var existing = contentEl.querySelector(".action-buttons");
        if (existing) existing.remove();

        var div = document.createElement("div");
        div.className = "action-buttons";
        buttons.forEach(function (btn) {
            var button = document.createElement("button");
            button.className = "action-btn";
            button.textContent = btn.label;
            button.setAttribute("data-action", btn.action);
            button.setAttribute("data-carmodel", carModel || "");
            button.addEventListener("click", function () {
                sendAction(btn.action, carModel || "");
            });
            div.appendChild(button);
        });
        contentEl.appendChild(div);
    }

    function appendReportOpenButton(contentEl, reportUrl, reportType) {
        var existing = contentEl.querySelector(".report-open-btn-wrapper");
        if (existing) existing.remove();

        var div = document.createElement("div");
        div.className = "report-open-btn-wrapper";

        var a = document.createElement("a");
        a.href = reportUrl || "#";
        a.target = "_blank";
        a.className = "report-open-btn";
        var icon = reportType === "visual_report" ? "fa-chart-bar" : "fa-file-alt";
        var label = reportType === "visual_report" ? "在新窗口查看可视化报告" : "在新窗口查看舆情报告";
        a.innerHTML = '<i class="fas ' + icon + '"></i> <span>' + label + '</span>';
        if (reportUrl) {
            a.addEventListener("click", function (e) {
                e.preventDefault();
                window.open(reportUrl, "_blank");
            });
        }
        div.appendChild(a);
        contentEl.appendChild(div);
    }

    function scrollToBottom() {
        var main = document.getElementById("chatMain");
        if (main) {
            requestAnimationFrame(function () {
                main.scrollTop = main.scrollHeight;
            });
        }
    }

    function updateSendButton(loading) {
        var btn = document.getElementById("sendBtn");
        if (btn) {
            btn.disabled = loading;
            btn.innerHTML = loading
                ? '<i class="fas fa-circle-notch fa-spin"></i>'
                : '<i class="fas fa-paper-plane"></i>';
        }
    }

    function formatText(text) {
        if (!text) return "";
        var html = escapeHtml(text);
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/\n/g, "<br>");

        html = html.replace(/^[•\-]\s+(.+)/gm, function (match, content) {
            return "<li>" + content + "</li>";
        });
        html = html.replace(/(<li>[\s\S]*?<\/li>)/g, function (match) {
            if (match.indexOf("<ul>") === -1) {
                return "<ul>" + match + "</ul>";
            }
            return match;
        });

        return html;
    }

    function escapeHtml(text) {
        if (!text) return "";
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function escapeAttr(text) {
        if (!text) return "";
        return text.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function showToast(message, type) {
        var container = document.getElementById("toastContainer");
        if (!container) return;
        var toast = document.createElement("div");
        toast.className = "toast toast-" + (type || "success");
        var icon = type === "error" ? "fa-exclamation-circle" : "fa-check-circle";
        toast.innerHTML = '<i class="fas ' + icon + '"></i> ' + escapeHtml(message);
        container.appendChild(toast);
        setTimeout(function () {
            toast.classList.add("toast-out");
            setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 300);
        }, 2500);
    }

    document.addEventListener("DOMContentLoaded", function () {
        init();
    });

    return {
        sendMessage: sendMessage,
        sendQuickTag: sendQuickTag,
        sendAction: sendAction,
        newConversation: newConversation,
        toggleSidebar: toggleSidebar,
    };
})();
