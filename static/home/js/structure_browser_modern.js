function getSelectedRowData(tableId) {
    const table = $(tableId).DataTable();
    const data = [];
    const selectedCheckboxes = $(`${tableId} .select-row:checked`);

    selectedCheckboxes.each(function () {
        const row = $(this).closest("tr");
        const rowData = table.row(row).data();
        if (rowData) {
            data.push(rowData);
        }
    });

    return data;
}

function initAlignButton(tableId) {
    $("#align_btn").on("click", function () {
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
    });
}

function initDownloadButton(tableId) {
    console.log("Binding download_btn exists?", $("#download_btn").length);
    $("#download_btn").on("click", function () {
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
    });
}
function initSuperpositionButtons(tableId) {
    console.log("Binding superposition buttons...");

    // 1. Default Superposition — opens modal
    $(document).on("click", "#superpose_btn", function () {
        console.log("Clicked: #superpose_btn");
        const table = $(tableId).DataTable();
        superposition(table, [7, 1, 2, 3, 4, 5, 11, 29], "structure_browser", "gpcr", 7);
    });

    // 2. Workflow Superposition — adds ref or targets
    $(document).on("click", "#superpose_template_btn", function () {
        console.log("Clicked: #superpose_template_btn");

        const table = $(tableId).DataTable();
        const selectedData = getSelectedRowData(tableId);
        const type = this.dataset.type || "default";

        ClearSelection("reference");
        ClearSelection("targets");

        if (type === "reference") {
            if (selectedData.length !== 1) {
                showAlert("Please select exactly one entry as reference", "danger");
                return;
            }
            const refPdb = selectedData[0].pdb.replace(/\s+/g, "");
            AddToSelection("reference", "structure", refPdb);
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
        } else {
            showAlert("Unknown action. Try reloading the page.", "warning");
            return;
        }

        // Redirect
        window.location.href = "/structure/superposition_workflow_index#keepselection";
    });
}
