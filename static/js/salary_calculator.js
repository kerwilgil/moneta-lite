document.addEventListener("DOMContentLoaded", () => {
    const panel = document.getElementById("salaryCalculatorPanel");
    if (!panel) {
        return;
    }

    const lang = (panel.dataset.lang || "es").toLowerCase();
    const labels = {
        addName: lang === "en" ? "Deduction name" : "Nombre deduccion",
        addAmount: lang === "en" ? "Deduction amount" : "Monto deduccion",
        remove: lang === "en" ? "Remove" : "Quitar",
        gross: lang === "en" ? "Gross" : "Bruto",
        deductions: lang === "en" ? "Deductions" : "Deducciones",
        net: lang === "en" ? "Net" : "Neto",
        removeRecord: lang === "en" ? "Delete" : "Eliminar",
        noRecords: lang === "en" ? "No saved records yet." : "Todavía no hay registros guardados.",
        dedList: lang === "en" ? "Deduction detail" : "Detalle de deducciones",
    };

    const grossInput = document.getElementById("salaryGross");
    const deductionsContainer = document.getElementById("salaryDeductions");
    const addButton = document.getElementById("addDeductionRow");
    const saveCardButton = document.getElementById("saveNetIncomeCard");
    const totalNode = document.getElementById("salaryTotalDeductions");
    const netNode = document.getElementById("salaryNet");
    const cardsContainer = document.getElementById("netIncomeCards");
    const storageKey = "moneta-net-income-records";
    const legacyStorageKey = "moneta-net-income-cards";

    if (!grossInput || !deductionsContainer || !addButton || !totalNode || !netNode) {
        return;
    }

    const parseMoney = (value) => {
        const parsed = Number.parseFloat(value || "0");
        return Number.isNaN(parsed) ? 0 : Math.max(parsed, 0);
    };

    const formatMoney = (value) => window.MonetaCurrency ? window.MonetaCurrency.format(value) : `$${value.toFixed(2)}`;

    const appendText = (parent, tagName, text, className = "") => {
        const element = document.createElement(tagName);
        if (className) {
            element.className = className;
        }
        element.textContent = text;
        parent.appendChild(element);
        return element;
    };

    function getRowsData() {
        return Array.from(deductionsContainer.querySelectorAll(".salary-row")).map((row) => {
            const nameInput = row.querySelector(".deduction-name");
            const amountInput = row.querySelector(".deduction-amount");
            return {
                name: (nameInput ? nameInput.value : "").trim() || (lang === "en" ? "Deduction" : "Deduccion"),
                amount: parseMoney(amountInput ? amountInput.value : "0"),
            };
        });
    }

    function recalculate() {
        const gross = parseMoney(grossInput.value);
        let totalDeductions = 0;

        const rows = Array.from(deductionsContainer.querySelectorAll(".salary-row"));
        rows.forEach((row) => {
            const amountInput = row.querySelector(".deduction-amount");
            const percentNode = row.querySelector(".deduction-percent");
            const amount = parseMoney(amountInput ? amountInput.value : "0");
            totalDeductions += amount;
            const percent = gross > 0 ? (amount / gross) * 100 : 0;
            if (percentNode) {
                percentNode.textContent = `${percent.toFixed(2)}%`;
            }
        });

        totalNode.textContent = formatMoney(totalDeductions);
        const net = Math.max(gross - totalDeductions, 0);
        netNode.textContent = formatMoney(net);
    }

    function attachRowEvents(row) {
        const amountInput = row.querySelector(".deduction-amount");
        const removeButton = row.querySelector(".remove-deduction");

        if (amountInput) {
            amountInput.addEventListener("input", recalculate);
            amountInput.addEventListener("change", recalculate);
        }
        if (removeButton) {
            removeButton.addEventListener("click", () => {
                const totalRows = deductionsContainer.querySelectorAll(".salary-row").length;
                if (totalRows <= 1) {
                    return;
                }
                row.remove();
                recalculate();
            });
        }
    }

    function loadCards() {
        if (!cardsContainer) {
            return [];
        }
        try {
            const raw = localStorage.getItem(storageKey) || localStorage.getItem(legacyStorageKey);
            const data = raw ? JSON.parse(raw) : [];
            return Array.isArray(data) ? data : [];
        } catch {
            return [];
        }
    }

    function saveCards(cards) {
        localStorage.setItem(storageKey, JSON.stringify(cards.slice(0, 24)));
    }

    function renderCards() {
        if (!cardsContainer) {
            return;
        }
        const cards = loadCards();
        cardsContainer.innerHTML = "";

        if (!cards.length) {
            const empty = document.createElement("p");
            empty.className = "empty-state";
            empty.textContent = labels.noRecords;
            cardsContainer.appendChild(empty);
            return;
        }

        cards.forEach((card, index) => {
            const article = document.createElement("article");
            article.className = "salary-history-card";

            const head = document.createElement("div");
            head.className = "salary-history-head";
            appendText(head, "strong", new Date(card.createdAt).toLocaleString());
            const remove = appendText(head, "button", labels.removeRecord, "btn btn-outline-danger btn-sm");
            remove.type = "button";
            remove.dataset.removeIndex = String(index);
            article.appendChild(head);

            const metrics = document.createElement("div");
            metrics.className = "salary-history-metrics";
            [
                [labels.gross, Number(card.gross) || 0],
                [labels.deductions, Number(card.totalDeductions) || 0],
                [labels.net, Number(card.net) || 0],
            ].forEach(([label, value]) => {
                const wrapper = document.createElement("span");
                wrapper.append(document.createTextNode(`${label}: `));
                appendText(wrapper, "strong", formatMoney(value));
                metrics.appendChild(wrapper);
            });
            article.appendChild(metrics);

            const list = document.createElement("div");
            list.className = "salary-history-list";
            appendText(list, "p", labels.dedList);
            const ul = document.createElement("ul");
            (card.deductions || []).forEach((item) => {
                const li = document.createElement("li");
                appendText(li, "span", item.name || (lang === "en" ? "Deduction" : "Deduccion"));
                appendText(li, "strong", formatMoney(Number(item.amount) || 0));
                ul.appendChild(li);
            });
            list.appendChild(ul);
            article.appendChild(list);
            cardsContainer.appendChild(article);
        });

        cardsContainer.querySelectorAll("[data-remove-index]").forEach((button) => {
            button.addEventListener("click", () => {
                const index = Number(button.dataset.removeIndex);
                const cards = loadCards();
                cards.splice(index, 1);
                saveCards(cards);
                renderCards();
            });
        });
    }

    function initQuickCalculator() {
        const calculator = document.getElementById("quickCalculator");
        const display = document.getElementById("quickCalcDisplay");
        if (!calculator || !display) {
            return;
        }

        let expression = "";

        const normalize = (value) => {
            if (!value) {
                return "0";
            }
            return value.replace(/\*/g, "x").replace(/\//g, "/");
        };

        const updateDisplay = () => {
            display.textContent = normalize(expression);
        };

        const evaluateExpression = (input) => {
            const tokens = input.match(/\d+(?:\.\d+)?|[+\-*/]/g) || [];
            if (!tokens.length || tokens.join("") !== input.replace(/\s+/g, "")) {
                return null;
            }

            const values = [];
            const operators = [];
            const precedence = { "+": 1, "-": 1, "*": 2, "/": 2 };
            const applyOperator = () => {
                const operator = operators.pop();
                const right = values.pop();
                const left = values.pop();
                if (left === undefined || right === undefined) return false;
                if (operator === "+") values.push(left + right);
                if (operator === "-") values.push(left - right);
                if (operator === "*") values.push(left * right);
                if (operator === "/") values.push(right === 0 ? Number.NaN : left / right);
                return true;
            };

            for (const token of tokens) {
                if (/^\d/.test(token)) {
                    values.push(Number(token));
                    continue;
                }
                while (
                    operators.length
                    && precedence[operators[operators.length - 1]] >= precedence[token]
                    && applyOperator()
                ) {
                    // Consume previous higher-precedence operators first.
                }
                operators.push(token);
            }
            while (operators.length && applyOperator()) {}
            return values.length === 1 && Number.isFinite(values[0]) ? values[0] : null;
        };

        const evaluate = () => {
            if (!expression) {
                return;
            }
            const sanitized = expression.replace(/%/g, "/100");
            if (!/^[0-9+\-*/. ]+$/.test(sanitized)) {
                expression = "";
                updateDisplay();
                return;
            }
            const result = evaluateExpression(sanitized);
            expression = result === null ? "" : String(Number(result.toFixed(8)));
            updateDisplay();
        };

        calculator.querySelectorAll("[data-calc-value]").forEach((button) => {
            button.addEventListener("click", () => {
                expression = `${expression}${button.dataset.calcValue}`;
                updateDisplay();
            });
        });

        calculator.querySelectorAll("[data-calc-action]").forEach((button) => {
            button.addEventListener("click", () => {
                const action = button.dataset.calcAction;
                if (action === "clear") {
                    expression = "";
                    updateDisplay();
                }
                if (action === "back") {
                    expression = expression.slice(0, -1);
                    updateDisplay();
                }
                if (action === "equals") {
                    evaluate();
                }
            });
        });
    }

    addButton.addEventListener("click", () => {
        const row = document.createElement("div");
        row.className = "salary-row";
        const nameInput = document.createElement("input");
        nameInput.type = "text";
        nameInput.className = "form-control deduction-name";
        nameInput.placeholder = labels.addName;
        nameInput.setAttribute("aria-label", labels.addName);
        const amountInput = document.createElement("input");
        amountInput.type = "number";
        amountInput.step = "0.01";
        amountInput.min = "0";
        amountInput.className = "form-control deduction-amount";
        amountInput.value = "0";
        amountInput.setAttribute("aria-label", labels.addAmount);
        const percent = appendText(row, "span", "0.00%", "deduction-percent");
        const remove = appendText(row, "button", labels.remove, "btn btn-outline-danger btn-sm remove-deduction");
        remove.type = "button";
        row.prepend(nameInput, amountInput, percent);
        deductionsContainer.appendChild(row);
        attachRowEvents(row);
        recalculate();
    });

    if (saveCardButton && cardsContainer) {
        saveCardButton.addEventListener("click", () => {
            const gross = parseMoney(grossInput.value);
            const deductions = getRowsData();
            const totalDeductions = deductions.reduce((acc, item) => acc + item.amount, 0);
            const net = Math.max(gross - totalDeductions, 0);
            const cards = loadCards();
            cards.unshift({
                createdAt: new Date().toISOString(),
                gross,
                totalDeductions,
                net,
                deductions,
            });
            saveCards(cards);
            renderCards();
        });
    }

    grossInput.addEventListener("input", recalculate);
    grossInput.addEventListener("change", recalculate);
    deductionsContainer.querySelectorAll(".salary-row").forEach(attachRowEvents);
    recalculate();
    renderCards();
    initQuickCalculator();
});
