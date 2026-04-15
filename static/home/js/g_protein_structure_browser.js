/*global yadcf,createYADCFfilters,ClearSelection,superposition,AddToSelection,copyToClipboard,*/
/*eslint complexity: ["error", 20]*/
function gproteinstructurebrowser(effector) {
// $(document).ready(function () {
    // 'use strict';
    var prev_ids = Array()
    var current_align_ids = Array()

    function buildColumnsFromDOM(tableSelector, overridesByIndex) {
        var thCount = $(tableSelector + " thead tr").last().find("th").length;
        var columns = new Array(thCount).fill(null);
        if (overridesByIndex) {
            Object.keys(overridesByIndex).forEach(function (key) {
                columns[parseInt(key, 10)] = overridesByIndex[key];
            });
        }
        return columns;
    }

    function normalizeTableHeaderToBody(tableSelector) {
        var $table = $(tableSelector);
        var bodyCols = $table.find("tbody tr:first-child td").length;
        if (!bodyCols) return null;

        // Ensure the last two header rows (labels + filter row) have same number of THs as TDs
        var $theadRows = $table.find("thead tr");
        $theadRows.each(function () {
            var $tr = $(this);
            // Skip the over-header row (it uses colspans)
            if ($tr.hasClass("over_header_row")) return;

            var $ths = $tr.find("th");
            while ($ths.length > bodyCols) {
                $ths.last().remove();
                $ths = $tr.find("th");
            }
        });

        // Ensure the over-header row colspans sum to bodyCols (adjust the last TH if needed)
        var $over = $table.find("thead tr.over_header_row");
        if ($over.length) {
            var $overThs = $over.find("th");
            var sum = 0;
            $overThs.each(function () {
                var cs = parseInt($(this).attr("colspan") || "1", 10);
                sum += cs;
            });
            if (sum !== bodyCols && $overThs.length) {
                var $last = $overThs.last();
                var lastCs = parseInt($last.attr("colspan") || "1", 10);
                $last.attr("colspan", String(lastCs + (bodyCols - sum)));
            }
        }

        return bodyCols;
    }

    //Uncheck every row when using back button on browser
    $(".alt_selected").prop("checked",false);
    $(".alt").prop("checked",false);
    $(".select-all").prop("checked",false);

    switch (window.location.hash) {
        case "#keepselectionreference":
            ClearSelection("reference");
            break;
        case "#keepselectiontargets":
            break;
        default:
            ClearSelection("targets");
            ClearSelection("reference");
            break;
    }

    $("#loading_div").hide();

    let column_filters = [];
    var oTable2;
    if (effector === "gprot"){
      oTable2 = $("#structures_scrollable").DataTable({
          "scrollY":        "65vh",
          "scrollX":        true,
          "scrollCollapse": true,
          "scroller": true,
          "paging":         true,
          "pageLength":     100, 
          // "bSortCellsTop": true,
          "aaSorting": [],
          "autoWidth": false,
          "order": [[30,"desc"],[1,"asc"]],
          "columnDefs": [
              { "targets": "no-sort", "orderable": false },
              { "targets": -1, "visible": false, "searchable": false } // hidden protein id
              ],
          "columns": buildColumnsFromDOM("#structures_scrollable", {23: {"width": "20%"}}),
          "bInfo" : true,
      });

      // Selector column
      // Arg list: createYADCFfilters(start_column, num_cols, filter_type, select_type*, filter_default_label*, filter_reset_button_text*, filter_match_mode*, column_data_type*, width*)
      column_filters = column_filters.concat(createYADCFfilters(0, 1, "none"));
      // Receptor section
      column_filters = column_filters.concat(createYADCFfilters(1, 1, "multi_select", "select2", "Fam.", false, "exact", null, "50px"));
      column_filters = column_filters.concat(createYADCFfilters(2, 1, "multi_select", "select2", "&alpha", false, "exact", "html", "40px"));
      column_filters = column_filters.concat(createYADCFfilters(3, 1, "multi_select", "select2", "Species", false, null, null, "55px"));
      column_filters = column_filters.concat(createYADCFfilters(4, 1, "multi_select", "select2", "Note", false, null, null, "80px"));
      column_filters = column_filters.concat(createYADCFfilters(5, 1, "range_number", null, ["Min", "Max"], false, null, null, "30px"));
      column_filters = column_filters.concat(createYADCFfilters(6, 1, "multi_select", "select2", "&beta", false, "exact", "html", "40px"));
      column_filters = column_filters.concat(createYADCFfilters(7, 1, "multi_select", "select2", "Species", false, null, null, "55px"));
      column_filters = column_filters.concat(createYADCFfilters(8, 1, "multi_select", "select2", "&gamma", false, "exact", "html", "40px"));
      column_filters = column_filters.concat(createYADCFfilters(9, 1, "multi_select", "select2", "Species", false, null, null, "55px"));
      column_filters = column_filters.concat(createYADCFfilters(10, 1, "multi_select", "select2", "Method", false, null, null, "60px"));
      column_filters = column_filters.concat(createYADCFfilters(11, 2, "multi_select", "select2", "", false, null, "html", "50px"));
      column_filters = column_filters.concat(createYADCFfilters(13, 1, "range_number", null, ["Min", "Max"], false, null, null, "30px"));
      column_filters = column_filters.concat(createYADCFfilters(14, 1, "multi_select", "select2", "UniProt", false, "exact", "html", "60px"));
      column_filters = column_filters.concat(createYADCFfilters(15, 1, "multi_select", "select2", "Gene", false, "exact", "html", "60px"));
      column_filters = column_filters.concat(createYADCFfilters(16, 1, "multi_select", "select2", "IUPHAR", false, "exact", "html", "60px"));
      column_filters = column_filters.concat(createYADCFfilters(17, 1, "multi_select", "select2", "Receptor family", false, "exact", "html", "120px"));
      column_filters = column_filters.concat(createYADCFfilters(18, 1, "multi_select", "select2", "Class", false, "exact", "html", "80px"));
      column_filters = column_filters.concat(createYADCFfilters(19, 1, "multi_select", "select2", "Species", false, "exact", null, "55px"));
      column_filters = column_filters.concat(createYADCFfilters(20, 1, "text", "select2", "Receptor fusion", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(21, 1, "text", "select2", "Antibodies", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(22, 1, "text", "select2", "Other", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(23, 1, "text", "select2", "Ligand name", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(24, 1, "multi_select", "select2", "Ligand type", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(25, 1, "multi_select", "select2", "Modality", false, "exact", null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(26, 1, "multi_select", "select2", "Ligand name", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(27, 1, "multi_select", "select2", "Ligand type", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(28, 1, "multi_select", "select2", "Last author", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(29, 1, "multi_select", "select2", "Reference", false, null, null, "140px"));
      column_filters = column_filters.concat(createYADCFfilters(30, 1, "range_date", null, ["Min", "Max"], false, null, null, "30px"));
    } else {
      // Arrestin browser has historically drifted between header and body column counts.
      // Normalize header to body BEFORE DataTables init to avoid '_DT_CellIndex' crashes.
      var arrestinBodyCols = normalizeTableHeaderToBody("#structures_scrollable");
      oTable2 = $("#structures_scrollable").DataTable({
          "scrollY":        "65vh",
          "scrollX":        true,
          "scrollCollapse": true,
          "scroller": true,
          "paging":         false,
          // "bSortCellsTop": true,
          "aaSorting": [],
          "autoWidth": false,
          // Arrestin browser columns:
          // 0 checkbox, 1 PDB, 2 Method, 3 Resolution, ... , 22 PDB Date, 23 hidden protein id
          "order": [[22,"desc"],[9,"asc"]],
          "columnDefs": [
              { "targets": "no-sort", "orderable": false },
              { "targets": -1, "visible": false, "searchable": false } // hidden protein id
              ],
          // Prefer body-derived column count to avoid header drift breaking initialization
          "columns": arrestinBodyCols ? new Array(arrestinBodyCols).fill(null) : buildColumnsFromDOM("#structures_scrollable"),
          "bInfo" : true,
      });
      // Selector column
      // Arg list: createYADCFfilters(start_column, num_cols, filter_type, select_type*, filter_default_label*, filter_reset_button_text*, filter_match_mode*, column_data_type*, width*)
      column_filters = column_filters.concat(createYADCFfilters(0, 1, "none"));
      // Structure Block
      column_filters = column_filters.concat(createYADCFfilters(1, 1, "multi_select", "select2", "PDB", false, null, 'html'));
      column_filters = column_filters.concat(createYADCFfilters(2, 1, "multi_select", "select2", "Method", false, null, null, "60px"));
      column_filters = column_filters.concat(createYADCFfilters(3, 1, "range_number", null, ["Min", "Max"], false, null, null, "30px"));
      // Receptor Block
      column_filters = column_filters.concat(createYADCFfilters(4, 1, "multi_select", "select2", "UniProt", false, "exact", "html", "60px"));
      column_filters = column_filters.concat(createYADCFfilters(5, 1, "multi_select", "select2", "Gene", false, "exact", "html", "60px"));
      column_filters = column_filters.concat(createYADCFfilters(6, 1, "multi_select", "select2", "IUPHAR", false, "exact", "html", "60px"));
      column_filters = column_filters.concat(createYADCFfilters(7, 1, "multi_select", "select2", "Receptor family", false, "exact", "html", "120px"));
      column_filters = column_filters.concat(createYADCFfilters(8, 1, "multi_select", "select2", "Class", false, "exact", "html", "80px"));
      column_filters = column_filters.concat(createYADCFfilters(9, 1, "multi_select", "select2", "Species", false, "exact", null, "55px"));
      // Arrestin block
      column_filters = column_filters.concat(createYADCFfilters(10, 1, "multi_select", "select2", "Fam.", false, "exact", null, "50px"));
      column_filters = column_filters.concat(createYADCFfilters(11, 1, "multi_select", "select2", "Arrestin", false, "exact", "html", "40px"));
      column_filters = column_filters.concat(createYADCFfilters(12, 1, "multi_select", "select2", "Species", false, null, null, "55px"));
      column_filters = column_filters.concat(createYADCFfilters(13, 1, "multi_select", "select2", "Note", false, null, null, "80px"));
      column_filters = column_filters.concat(createYADCFfilters(14, 1, "range_number", null, ["Min", "Max"], false, null, null, "30px"));
      // Other proteins block
      column_filters = column_filters.concat(createYADCFfilters(15, 1, "text", "select2", "Receptor fusion", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(16, 1, "text", "select2", "Antibodies", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(17, 1, "text", "select2", "Other", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(18, 1, "text", "select2", "Ligand name", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(19, 1, "multi_select", "select2", "Ligand type", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(20, 1, "multi_select", "select2", "Modality", false, "exact", null, "100px"));
      // column_filters = column_filters.concat(createYADCFfilters(21, 1, "multi_select", "select2", "Ligand name", false, null, null, "100px"));
      // column_filters = column_filters.concat(createYADCFfilters(22, 1, "multi_select", "select2", "Ligand type", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(21, 1, "multi_select", "select2", "Last author", false, null, null, "100px"));
      column_filters = column_filters.concat(createYADCFfilters(22, 1, "multi_select", "select2", "Reference", false, null, null, "140px"));
      column_filters = column_filters.concat(createYADCFfilters(23, 1, "range_date", null, ["Min", "Max"], false, null, null, "30px"));
  }
    yadcf.init(oTable2, column_filters, {
      cumulative_filtering: false
    });

    //yadcf.exResetAllFilters(oTable2);
    oTable2.columns.adjust();
    // $(function(){
    //     $(".wrapper").scroll(function(){
    //         $(".dataTables_scrollBody").eq(0).scrollLeft($(".wrapper").scrollLeft());
    //     });
    //     $(".dataTables_scrollBody").eq(0).scroll(function(){
    //         $(".wrapper").scrollLeft($(".dataTables_scrollBody").eq(0).scrollLeft());
    //     });
    // });

    $("#structures_scrollable > tbody > tr").click(function(event) {
        if (event.target.type !== "checkbox") {
            $(":checkbox", this).trigger("click");
            $(this).eq(0).toggleClass("alt_selected");
            $(this).find("td").toggleClass("highlight");
        }
        $(this).eq(0).toggleClass("alt_selected");
        $(this).find("td").toggleClass("highlight");
    });

    $(".select-all").click(function() {
        $(":checkbox", this).trigger("click");
        if ($(this).prop("checked")===true) {
            $(".alt").prop("checked", true);
            $(".alt").parent().parent().addClass("alt_selected");
            $(".alt").parent().parent().find("td").addClass("highlight");
        }
        if ($(this).prop("checked")===false) {
            $(".alt").prop("checked", false);
            $(".alt").parent().parent().removeClass("alt_selected");
            $(".alt").parent().parent().find("td").removeClass("highlight");
        }
    });

    // $(".wrapper").find("div").width($(".yadcf-datatables-table--structures_scrollable").width());

    $(".hide_columns").click(function(evt) {
    var columns = $(this).attr("columns").split(",");
    columns.forEach(function(column) {
        var column = oTable2.column( column );
        try {
            column.visible( false, false );
        }
        catch(err) {
            column.visible( false, false );
        }
        });
        oTable2.draw();
    } );

    toggle_enabled = true;
    $("#toggle_fixed_btn").click(function() {
        if (toggle_enabled) {
            toggle_enabled = false;
            $("#overlay").hide();
            $("#toggle_fixed_btn").attr("value","Enable fixed columns");
            $("#toggle_fixed_btn").addClass("clicked_button");
        } else {
            toggle_enabled = true;
            $(".dataTables_scrollBody").scroll();
            $("#toggle_fixed_btn").attr("value","Disable fixed columns");
            $("#toggle_fixed_btn").removeClass("clicked_button");
        }
    });

    $("#toggle_columns_btn").click(function() {
        var totalCols = oTable2.columns().count();
        var hiddenIdIdx = totalCols - 1;
        var columns = Array.from(new Array(totalCols), (x,i) => i);
        columns.forEach(function(columnIdx) {
            if (columnIdx === hiddenIdIdx) return;
            var column = oTable2.column(columnIdx);
            try {
                column.visible( true, false );
            }
            catch(err) {
                column.visible( true, false );
            }
        });
        oTable2.draw();
    });

    $("#representative_btn").click(function () {
        $(this).toggleClass("toggled");
        if ($(this).hasClass("toggled")) {
            $("#representative_btn").addClass("clicked_button");
            $("#representative_btn").attr("value","All structures");
        }
        else {
            $("#representative_btn").removeClass("clicked_button");
            $("#representative_btn").attr("value","Representative structures (state & receptor)");
        }
        oTable2.draw();
    });

    $.fn.dataTable.ext.search.push(
        function (settings, data, dataIndex) {
            if ($("#representative_btn").hasClass("toggled")) {
                if ($(oTable2.row(dataIndex).node()).hasClass("repr-st") && $(oTable2.row(dataIndex).node()).hasClass("repr-st")) {
                    return true;
                }
                return false;
            }
            else {
                return true;
            }
    });

    $("#align_btn_g_prot").click(function () {
        var checked_data = oTable2.rows(".alt_selected").data();
        ClearSelection("targets");

        for (i = 0; i < checked_data.length; i++) {
            // protein id is stored in the final (hidden) column for both browsers
            AddToSelection("targets", "protein", checked_data[i][checked_data[i].length - 1]);
        }
        if (effector=='gprot'){
          window.location.href = "/alignment/segmentselectiongprot";
        }
        else {
          window.location.href = "/alignment/segmentselectionarrestin";
        }
    });

    $("#superpose_btn").click(function() {
        // superposition(oTable2, [1,2,11,14,15,16,17,18,29], "g_protein_structure_browser", "gprot", 11);
        superposition(oTable2, [1,2,11,14,15,16,17,18,29], "g_protein_structure_browser", "gprot", 11);
    });

    $('#superpose_template_btn').click(function () {
        direct_superposition(oTable2, "gprot", 11, "signprot");
    });

    $("#download_btn").click(function () {
        ClearSelection("targets");
        var checked_data = oTable2.rows(".alt_selected").data();
        console.log("CHECKED DATA:", checked_data[0][1])
        for (i = 0; i < checked_data.length; i++) {
            var div = document.createElement("div");
            div.innerHTML = checked_data[i][2];

            if (typeof div.innerText !== "undefined") {
                AddToSelection("targets", "structure",  div.innerText.replace(/\s+/g, "") );
            } else {
                AddToSelection("targets", "structure", div.textContent.replace(/\s+/g, ""));
            }
        }
        window.location.href = "/structure/pdb_download";
    });

    /////////////////////////////////////// PDB button

    // Event handler for button click on the 'pdbs_btn' button.
    $("#sign_complex_pdb_btn").click(function () {
        // Retrieve the current URL path to determine the context of the operation.
        let path = window.location.pathname;

        // Variable to hold the index of the 'PDB' column in the data table.
        let pdb_index;

        // Determine the PDB index based on the ending of the URL path.
        // This ensures that the function behaves differently based on the page it is on.
        if (path.endsWith("/g_protein_structure_browser")) {
            pdb_index = 11;  // Set for 'g_protein_structure_browser' context
        } else if (path.endsWith("/arrestin_structure_browser")) {
            pdb_index = 1;   // Set for 'arrestin_structure_browser' context
        }

        // Retrieve the data from rows that are selected by the user.
        let checked_data = oTable2.rows('.alt_selected').data();

        // Array to store PDB IDs extracted from the selected rows.
        let p_ids = [];
        for (let i = 0; i < checked_data.length; i++) {
            // Extract the PDB ID from the specified column index and add to the array.
            p_ids.push($(checked_data[i][pdb_index]).text());
        };

        // Check if any PDB IDs have been selected.
        if (p_ids.length > 0) {
            // Redirect to a new URL with the PDB IDs as query parameters for download.
            window.location.href = "sign_complex_pdb?" + $.param({"p_ids[]": p_ids});
        } else {
            // Alert the user if no PDB IDs are selected for download.
            alert('No PDBs selected for download');
        }
    });

    $(".uniprot-export").data("powertipjq", $([
        "<p>Export UniProt IDs</p>"
        ].join("\n")));
    $(".pdb-export").data("powertipjq", $([
        "<p>Export PDB IDs</p>"
        ].join("\n")));
    $(".glyphicon-export").powerTip({
        placement: "n",
        smartPlacement: true
    });
    $("#uniprot_copy").click(function () {
        copyToClipboard($(".alt_selected > .uniprot > a"), "\n", "UniProt IDs", $(".uniprot-export"));
    });
    $("#pdb_copy").click(function () {
        copyToClipboard($(".alt_selected > .pdb > a"), "\n", "PDB IDs", $(".pdb-export"));
    });

    $("#reset_filters_btn").click(function () {
        window.location.href = "/structure/";
    });

    $(".dataTables_scrollBody").append("<div id=overlay><table id=\"overlay_table\" class=\"row-border text-center compact dataTable no-footer text-nowrap\"><tbody></tbody></table></div>");

    function create_overlay() {
        // This function fires upon filtering, to update what rows to show as an overlay
        $("#overlay_table tbody tr").remove();
        var $target = $("#overlay_table tbody");
        $("#structures_scrollable tbody tr").each(function() {
            var $tds = $(this).children(),
                $row = $("<tr></tr>");
            // $row.append($tds.eq(0).clone()).append($tds.eq(1).clone()).appendTo($target);
            $row.append($tds.eq(1).clone()).append($tds.eq(2).clone()).appendTo($target);
            $row.height($(this).height());
        });
        $("#overlay_table .border-right").removeClass("border-right");
    }

    // Function that detects filtering events
    $("#structures_scrollable").on( "draw.dt", function (e,oSettings) {
        create_overlay();
    });

    create_overlay();
    $("#overlay").hide();

    var left = 0;
    var old_left = 0;
    $(".dataTables_scrollBody").scroll(function(){
        // If user scrolls and it"s >100px from left, then attach fixed columns overlay
        left = $(".dataTables_scrollBody").scrollLeft();
        if (left!=old_left) $("#overlay").hide();
        old_left = left;

        if (left>100 && toggle_enabled) {
            $("#overlay").css({ left: left+"px" });
            if ($("#overlay").is(":hidden")) $("#overlay").show();
        }
    });
    // console.log($("#yadcf-filter--structures_scrollable-from-12").width());
    // $("#yadcf-filter--structures_scrollable-from-12").width(10);
    // console.log($("#yadcf-filter--structures_scrollable-from-12").width());

}

function CheckSelection(selection_type) {
    var result = null;

    $.ajax({
        'url': '/common/checkselection',
        'data': {
            selection_type: selection_type
        },
        'type': 'GET',
        'dataType': 'json',  // Expecting JSON response from the server
        'async': false,
        'success': function(response) {
            result = response.total;
        },
        'error': function(error) {
            console.error("An error occurred:", error);
        }
    });

    return result;
}

function ClearSelection(selection_type) {
    console.log("Selection type:", selection_type)
    $.ajax({
        'url': '/common/clearselection',
        'data': {
            selection_type: selection_type
        },
        'type': 'GET',
        'async': false,
        'success': function (data) {
            console.log('successsssss:', data)
            $("#selection-" + selection_type).html(data);
        }
    });
}

function copyDropdown() {
    document.getElementById("Dropdown").classList.toggle("show");
}

window.onclick = function(event) {
    if (!event.target.matches(".dropbtn")) {
        var dropdowns = document.getElementsByClassName("dropdown-content");
        var i;
        for (i = 0; i < dropdowns.length; i++) {
            var openDropdown = dropdowns[i];
            if (openDropdown.classList.contains("show")) {
                openDropdown.classList.remove("show");
            }
        }
    }
}

function copyToClipboard(array, delimiter, data_name, powertip_object=false) {
    var link = array;
    var out = "";
    link.each(function() {
        var ele = $(this).attr("href").split("/");
        out+=ele[ele.length-1]+delimiter;
    });
    if (out.length===0) {
        window.alert("No entries selected for copying");
        return 0;
    }
    var textArea = document.createElement("textarea");
    textArea.value = out;
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        var successful = document.execCommand("copy");
        var msg = successful ? "Successful" : "Unsuccessful";
        if (powertip_object!==false) {
            $.powerTip.hide();
            powertip_object.data("powertipjq", $([
                "<p>Copied to clipboard!</p>"
              ].join("\n")));
            powertip_object.powerTip("show");
            setTimeout(function() {
            powertip_object.data("powertipjq", $([
                "<p>Export "+data_name+"</p>"
              ].join("\n")));
            },1000);
        }
    } catch (err) {
        window.alert("Oops, unable to copy");
    }
    document.body.removeChild(textArea);
}
