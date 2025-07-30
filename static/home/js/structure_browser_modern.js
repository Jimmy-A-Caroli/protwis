function getSelectedRowData(tableId) {
    const tableSelector = typeof tableId === "string" ? tableId : `#${tableId.id || tableId}`;
    const table = $(tableSelector).DataTable();
    const allData = table.rows().data().toArray();

    return allData.filter(row => globalSelectedIds.has(String(row.id)));
}

function handleAlignmentClick(tableId) {
        const selectedData = getSelectedRowData(tableId);

        ClearSelection("targets");

        if (selectedData.length === 0) {
            showAlert("No entries selected for sequence alignment", "danger");
            return;
        }

        selectedData.forEach(row => {
            const pdb = row.pdb;
            AddToSelection("targets", "structure", pdb);
        });

        window.location.href = "/structure/selection_convert";
}

function handleDownloadClick(tableId) {
    const selectedData = getSelectedRowData(tableId);

    ClearSelection("targets");

    if (selectedData.length === 0) {
        showAlert("No structures selected for download", "danger");
        return;
    } else if (selectedData.length > 100) {
        showAlert("Maximum number of selected entries is 100", "warning");
        return;
    }

    const ids = selectedData.map(row => row.pdb.replace(/\s+/g, ""));
    AddToSelection("targets", "structure_many", ids.join(","));

    window.location.href = "/structure/pdb_download";
}

function getSuperposeButtonConfig() {
    const hash = window.location.hash;
    return {
        label: hash === "#keepselectionreference"
            ? "Add reference to superposition"
            : hash === "#keepselectiontargets"
                ? "Add targets to superposition"
                : "Superposition",
        type: hash === "#keepselectionreference"
            ? "reference"
            : hash === "#keepselectiontargets"
                ? "targets"
                : "default",
        class: hash === "#keepselectionreference" || hash === "#keepselectiontargets"
            ? "dt-button active-superpose"
            : "dt-button"
    };
}



function handleSuperpositionClick(tableId, type = "default") {
    const selectedData = getSelectedRowData(tableId);

    if (type === "reference") {
        if (selectedData.length !== 1) {
            showAlert("Please select exactly one entry as reference", "danger");
            return;
        }
        const refPdb = selectedData[0].pdb.replace(/\s+/g, "");
        AddToSelection("reference", "structure", refPdb);
        window.location.href = "/structure/superposition_workflow_index#keepselection";
    } else if (type === "targets") {
        if (selectedData.length === 0) {
            showAlert("No targets selected", "danger");
            return;
        } else if (selectedData.length > 50) {
            showAlert("Maximum number of selected targets is 50", "warning");
            return;
        }

        const ids = selectedData.map(row => row.pdb.replace(/\s+/g, ""));
        AddToSelection("targets", "structure_many", ids.join(","));
        window.location.href = "/structure/superposition_workflow_index#keepselection";
    } else {
        // Default case — open modal
        superpositionModern(tableId, ["pdb", "entry_short", "iuphar_name", "family", "class", "species", "state", "pub_date"], "structure_browser", "gpcr", "pdb");
    }
}

function superpositionModern(tableId, columns, site, source = 'gpcr', structure_column_key = "pdb", hidden_columns = []) {
    
    ClearSelection('targets');
    ClearSelection('reference');
    
    const selectedData = getSelectedRowData(tableId);

    if (selectedData.length === 0) {
        showAlert("No entries selected for superposition", "danger");
        return;
    } else if (selectedData.length > 50) {
        showAlert("Maximum number of selected entries is 50", "warning");
        return;
    }

    const selected_ids = [];
    let selection_type = '';

    if (site === 'structure_browser') {
        selectedData.forEach(row => {
            if (row[structure_column_key]) {
                selected_ids.push(row[structure_column_key].replace(/\s+/g, ''));
            }
        });
        selection_type = 'structure_many';
    }

    // Show modal
    const modal = document.getElementById("superposition-modal");
    const span = document.getElementById("close_superposition_modal");
    modal.style.display = "block";

    span.onclick = () => modal.style.display = "none";
    window.onclick = (e) => {
        if (e.target === modal) {
            modal.style.display = "none";
        }
    };

    // Populate modal table
    const tbody = document.querySelector("#superposition_modal_table tbody");
    tbody.innerHTML = "";

    selectedData.forEach(row => {
        const tr = document.createElement("tr");

        // Add checkbox cell
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        const checkboxTd = document.createElement("td");
        checkboxTd.appendChild(checkbox);
        tr.appendChild(checkboxTd);

        // Add data cells
        columns.forEach(key => {
            const td = document.createElement("td");
            td.innerHTML = row[key] || '';
            if (hidden_columns.includes(key)) td.style.display = "none";
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });

    // Handle row click — pick reference, assign rest to targets
    $("#superposition_modal_table tbody tr").on("click", function () {
        const cells = $(this).children();
        const ref_id = cells.eq(columns.indexOf(structure_column_key) + 1).text().replace(/\s+/g, '');

        AddToSelection('reference', 'structure', ref_id);

        const targets = selected_ids.filter(id => id !== ref_id);
        AddToSelection('targets', selection_type, targets.join(","));

        $(this).children(':first').find("input").prop("checked", true);

        const redirectUrl = (source === 'gpcr')
            ? '/structure/superposition_workflow_index#keepselection'
            : '/structure/superposition_workflow_gprot_index#keepselection';

        window.location.href = redirectUrl;
    });
}
