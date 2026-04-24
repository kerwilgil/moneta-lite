document.addEventListener("DOMContentLoaded", () => {
    const linesContainer = document.getElementById("journal-lines-container");
    const addButton = document.getElementById("add-journal-line");
    const template = document.getElementById("journal-line-template");
    const totalFormsInput = document.getElementById("id_form-TOTAL_FORMS");
    const submitButton = document.getElementById("journal-submit");
    const balanceError = document.getElementById("journal-balance-error");
    const totalDebit = document.getElementById("total-debit");
    const totalCredit = document.getElementById("total-credit");
    const totalDiff = document.getElementById("total-diff");

    if (!linesContainer || !addButton || !template || !totalFormsInput) {
        return;
    }

    const parseAmount = (rawValue) => {
        const value = Number.parseFloat(rawValue || "0");
        return Number.isNaN(value) ? 0 : value;
    };

    const formatMoney = (value) => `$${value.toFixed(2)}`;

    const lineRows = () => Array.from(linesContainer.querySelectorAll(".line-row"));

    function reindexRows() {
        lineRows().forEach((row, index) => {
            const labelElements = row.querySelectorAll("label");
            const fields = row.querySelectorAll("input, select, textarea");
            fields.forEach((field) => {
                if (field.name) {
                    field.name = field.name.replace(/form-(?:\d+|__prefix__)-/g, `form-${index}-`);
                }
                if (field.id) {
                    const oldId = field.id;
                    field.id = field.id.replace(/id_form-(?:\d+|__prefix__)-/g, `id_form-${index}-`);
                    labelElements.forEach((label) => {
                        if (label.htmlFor === oldId) {
                            label.htmlFor = field.id;
                        }
                    });
                }
            });
        });
        totalFormsInput.value = String(lineRows().length);
    }

    function calculateTotals() {
        let debit = 0;
        let credit = 0;
        let validRows = 0;

        lineRows().forEach((row) => {
            const account = row.querySelector("select[name$='-account']");
            const debitInput = row.querySelector("input[name$='-debit']");
            const creditInput = row.querySelector("input[name$='-credit']");
            const debitValue = parseAmount(debitInput ? debitInput.value : "0");
            const creditValue = parseAmount(creditInput ? creditInput.value : "0");

            debit += debitValue;
            credit += creditValue;
            if (account && account.value && (debitValue > 0 || creditValue > 0)) {
                validRows += 1;
            }
        });

        const diff = Math.abs(debit - credit);
        const balanced = diff < 0.005;
        const valid = balanced && validRows >= 2;

        totalDebit.textContent = formatMoney(debit);
        totalCredit.textContent = formatMoney(credit);
        totalDiff.textContent = formatMoney(diff);
        totalDiff.classList.toggle("invalid", !valid);

        if (submitButton) {
            submitButton.disabled = !valid;
        }
        if (balanceError) {
            balanceError.classList.toggle("d-none", valid);
        }
    }

    function attachLineEvents(row) {
        row.querySelectorAll("input, select").forEach((field) => {
            field.addEventListener("input", calculateTotals);
            field.addEventListener("change", calculateTotals);
        });
        const removeButton = row.querySelector(".line-remove");
        if (removeButton) {
            removeButton.addEventListener("click", () => {
                if (lineRows().length <= 2) {
                    return;
                }
                row.remove();
                reindexRows();
                calculateTotals();
            });
        }
    }

    addButton.addEventListener("click", () => {
        const fragment = template.content.cloneNode(true);
        const row = fragment.querySelector(".line-row");
        linesContainer.appendChild(fragment);
        reindexRows();
        attachLineEvents(row);
        calculateTotals();
    });

    lineRows().forEach(attachLineEvents);
    reindexRows();
    calculateTotals();
});
