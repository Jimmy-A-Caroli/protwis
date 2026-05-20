class TableManager {
  constructor(
    columnSpecification,
    tableId,
  ) {
    this.columnsSpecifications = columnSpecification;
    this.tableId = tableId;
  }

  initialiseDataTable(dataTableOptions) {
    try {
      this.validateColumnSpecifications();
    } catch (error) {
      alert(
        "Error in column specifications during DataTable initialisation:",
        error.message,
      );
      return;
    }

    //Returns [table, tableHead,  primaryHeaderRow, tableBody] HTML object references after adding them to DOM
    let tableComponents = this.createPrimaryTableStructure();

    this.populateColumnTitleHeaders(tableComponents.primaryHeaderRow);

    if (!dataTableOptions.columns) {
      dataTableOptions.columns = this.columnsSpecifications.map((colSpec) =>
        this.colSpecToDataTableColDef(colSpec),
      );
    } else {
      console.log(
        "DataTable options already contains column definitions, skipping automatic column definition generation from specifications.",
      );
    }

    this.dataTableReference = $(`#${this.tableId}`).DataTable(dataTableOptions);

    tableComponents = this.createSecondaryTableStructure(tableComponents);

    this.populateSuperHeaders(tableComponents.superHeaderRow);

    this.populateFilterHeaders(tableComponents.filterHeaderRow);
  }

  createPrimaryTableStructure() {
    let table = document.getElementById(this.tableId);

    if(!table) {
      throw new Error(`No table element found with id "${this.tableId}". Please ensure an HTML <table> element with this id exists in the DOM before initializing the TableManager.`);
    }

    let tableHead = this._createTableHeaderSection();

    let primaryHeaderRow = document.createElement("tr");
    this.primaryHeaderRowId = this.tableId + "_primaryHeaders";
    primaryHeaderRow.id = this.primaryHeaderRowId;
    tableHead.append(primaryHeaderRow);

    let tableBody = document.createElement("tbody");
    tableBody.id = this.tableId + "_body";
    table.prepend(tableBody);

    table.prepend(tableHead);
    table.append(tableBody);

    return {
      table: table,
      tableHead: tableHead,
      primaryHeaderRow: primaryHeaderRow,
      tableBody: tableBody,
    };
  }

  createSecondaryTableStructure(TableComponents) {
    let superHeaderRow = null;
    if (this._hasSuperHeaders()) {
      this.superHeaderRowId = this.tableId + "_superHeaders";
      superHeaderRow = this._createSuperHeaderRow(this.superHeaderRowId);
      TableComponents.tableHead.prepend(superHeaderRow);
    }

    let filterHeaderRow = null;
    if (this._hasFilters()) {
      this.filterHeaderRowId = this.tableId + "_filterHeaders";
      filterHeaderRow = this._createFilterHeaderRow(this.filterHeaderRowId);
      TableComponents.tableHead.append(filterHeaderRow);
    }

    return {
      ...TableComponents,
      superHeaderRow: superHeaderRow,
      filterHeaderRow: filterHeaderRow,
    };
  }

  //-------------------------/
  //                         /
  //  Table header creation  /
  //                         /
  //-------------------------/

  _createTableHeaderSection() {
    const tableHead = document.createElement("thead");
    this.headerSetId = this.tableId + "_headerSet";
    tableHead.id = this.headerSetId;
    return tableHead;
  }

  //---------------------------/
  //  Super(/grouped) headers  /
  //---------------------------/

  _hasSuperHeaders() {
    return this.columnsSpecifications.every((col) => col.column_group);
  }

  _hasFilters() {
    return this.columnsSpecifications.some((col) => col.column_group);
  }

  //Uses column_group property of column specifications to create and append a super-header row to the table,
  // grouping columns under shared headers as specified. E.g. if columns 0-4 have column_group 'Classification' and columns 5-7 have column_group 'State',
  // creates a super-header row with 'Classification' spanning columns 0-4 and 'State' spanning columns 5-7.
  populateSuperHeaders(superHeaderRow) {
    //Add super-header row if any column groups defined in specifications, otherwise remove super-header row (which would just be empty)
    if (!this._hasSuperHeaders()) {
      console.log(
        "No column groups defined in specifications, skipping super-header creation.",
      );
      return;
    }

    const superHeaderStructure = this._getSuperHeaderStructure(
      this.columnsSpecifications,
    );

    superHeaderStructure.forEach(({ name, colspan }) => {
      let th = document.createElement("th");
      th.textContent = name;
      th.colSpan = colspan;
      superHeaderRow.append(th);
    });
  }

  _createSuperHeaderRow(superHeaderRowId) {
    const superHeaderRow = document.createElement("tr");
    superHeaderRow.id = superHeaderRowId;
    return superHeaderRow;
  }

  //Return an array of { name, colspan } objects in col_idx order, e.g. [{ name: 'Classification', colspan: 5 }, { name: 'State', colspan: 3 }, ...]
  _getSuperHeaderStructure(columnsSpecifications) {
    try {
      this.validateColumnSpecifications(columnsSpecifications);
    } catch (error) {
      console.error(
        "Error in column specification when getting super header structure:",
        error.message,
      );
      return [];
    }

    const groups = [];

    for (const col of columnsSpecifications) {
      const last = groups[groups.length - 1];
      if (last && last.name === col.column_group) {
        last.colspan++;
      } else {
        groups.push({ name: col.column_group, colspan: 1 });
      }
    }

    return groups;
  }

  //-------------------/
  //  Primary headers  /
  //-------------------/

  populateColumnTitleHeaders(primaryHeaderRow) {
    this.columnsSpecifications.forEach((col) => {
      // add header
      const th = document.createElement("th");
      th.textContent = col.title;
      
      if (col.cssClassHeaderCell) {
        th.classList.add(col.cssClassHeaderCell);
      }
      
      primaryHeaderRow.append(th);
    });
  }

  //--------------/
  //  Filter row  /
  //--------------/

  // Filter Header row

  _createFilterHeaderRow(filterHeaderRowId) {
    const filterHeaderRow = document.createElement("tr");
    filterHeaderRow.id = filterHeaderRowId;
    return filterHeaderRow;
  }

  populateFilterHeaders(filterHeaderRow) {
    this.columnsSpecifications.forEach((col) => {
      // add filter interface if allowed
      const filterTh = document.createElement("th");

      if (col.cssClassFilterCell) {
        filterTh.classList.add(col.cssClassFilterCell);
      }

      if (col.allow_filter) {
        const filterInterface = this.filterInterfaceFactory(
          col,
          this.dataTableReference,
        );
        if (filterInterface) {
          //Add filter <input> elements  to filter header cell
          filterInterface.forEach((el) => filterTh.appendChild(el));
        }
      }
      filterHeaderRow.append(filterTh);
    });
  }

  //--------------------------/
  //  Filter user interfaces  /
  //--------------------------/

  filterInterfaceFactory(col, dataTableReference) {
    if (col.data_type === "text" || col.data_type === "weblink") {
      return [this._createTextFilterInterface(col, dataTableReference)];
    } else if (col.data_type === "numeric") {
      return this._createNumericRangeFilterInterface(col, dataTableReference);
    }
    return null;
  }

  _createTextFilterInterface(col, dataTableReference) {
    let filterInput = document.createElement("input");

    let data_field = document.createAttribute("data-field");
    data_field.value = col.json_id;
    filterInput.setAttributeNode(data_field);

    let id = document.createAttribute("id");
    id.value = col.json_id + "_search";
    filterInput.setAttributeNode(id);

    filterInput.classList.add("col-filter");
    filterInput.classList.add("text-filter");

    if (col.cssClassFilterInput) {
      filterInput.classList.add(col.cssClassFilterInput);
    }

    filterInput.addEventListener("blur", function () {
      let currentSearchValue =
        dataTableReference.columns(col.col_idx).search()[0] || "%";

      let newSearchValue = this.value;
      if (dataTableReference.settings()[0].oFeatures.bServerSide == true) {
        newSearchValue = newSearchValue + "%"; // append wildcard for "contains" search
      }

      if (newSearchValue !== currentSearchValue) {
        dataTableReference.columns(col.col_idx).search(newSearchValue).draw();
      }
    });

    return filterInput;
  }

  _createNumericRangeFilterInterface(col, dataTableReference) {
    let filterInputMin = document.createElement("input");
    let filterInputMax = document.createElement("input");

    let min_data_field = document.createAttribute("data-field");
    min_data_field.value = col.json_id;
    filterInputMin.setAttributeNode(min_data_field);

    let maxDataField = document.createAttribute("data-field");
    maxDataField.value = col.json_id;
    filterInputMax.setAttributeNode(maxDataField);

    let idMin = document.createAttribute("id");
    idMin.value = col.json_id + "_search_min";
    filterInputMin.setAttributeNode(idMin);

    let idMax = document.createAttribute("id");
    idMax.value = col.json_id + "_search_max";
    filterInputMax.setAttributeNode(idMax);

    let placeholderMin = document.createAttribute("placeholder");
    placeholderMin.value = "min";
    filterInputMin.setAttributeNode(placeholderMin);

    let placeholderMax = document.createAttribute("placeholder");
    placeholderMax.value = "max";
    filterInputMax.setAttributeNode(placeholderMax);

    filterInputMin.classList.add("col-filter");
    filterInputMin.classList.add("numericrange-filter");
    filterInputMax.classList.add("col-filter");
    filterInputMax.classList.add("numericrange-filter");

    if (col.cssClassFilterInput) {
      filterInputMin.classList.add(col.cssClassFilterInput);
      filterInputMax.classList.add(col.cssClassFilterInput);
    }

    let filterChangeListener = null;
    if (dataTableReference.settings()[0].oFeatures.bServerSide == true) {
      // ---- SERVER SIDE PROCESSING MODE ----
      filterChangeListener = this._createNumericFilterChangeListener(
        filterInputMin,
        filterInputMax,
        col,
        dataTableReference,
      );
    } else {
      // ---- CLIENT SIDE PROCESSING MODE ----
      // add a custom search function to DataTables which will read the current values of the min and max
      // inputs and apply the appropriate filtering logic to the relevant column.
      // This function will be called automatically by DataTables whenever the table is redrawn
      // so we just need to trigger a redraw whenever the filter inputs change to ensure the filtering is applied.
      this._attachFixedSearchToDataTable(col, filterInputMin, filterInputMax, dataTableReference);
      // trigger redraw on filter input change to apply the filtering
      filterChangeListener = function () {
        dataTableReference.draw();
      };
    }

    filterInputMin.addEventListener("blur", filterChangeListener);
    filterInputMax.addEventListener("blur", filterChangeListener);

    return [filterInputMin, filterInputMax];
  }

  _attachFixedSearchToDataTable(col, filterInputMin, filterInputMax, dataTableReference) {
    dataTableReference.search.fixed(
      "range_" + col.json_id,
      function (searchStr, data, index) {
        var min = parseInt(filterInputMin.value, 10);
        var max = parseInt(filterInputMax.value, 10);
        var value = parseFloat(data[col.json_id]) || 0;

        if (
          (isNaN(min) && isNaN(max)) ||
          (isNaN(min) && value <= max) ||
          (min <= value && isNaN(max)) ||
          (min <= value && value <= max)
        ) {
          return true;
        }
        return false;
      },
    );
  }

  _createNumericFilterChangeListener(
    filterInputMin,
    filterInputMax,
    col,
    dataTableReference,
  ) {
    //create event callback function
    return function () {
      // For server-side processing, we will encode the range filter as a single search string in the format "min~max"
      // where min and max are the values from the two inputs, or -Inf/Inf if not set. The server can then parse this string to apply the appropriate filtering.
      let rangeMin = filterInputMin.value || "-Inf";
      let rangeMax = filterInputMax.value || "Inf";

      // DataTables sends the current search value for the column as the first element of the array returned by .search()
      // we can use this to avoid unnecessary reloads if the range hasn't actually changed
      let currentSearchValue =
        dataTableReference.columns(col.col_idx).search()[0] || "-Inf~Inf"; // default to full range if no search value currently set

      let newSearchValue = `${rangeMin}~${rangeMax}`;

      if (newSearchValue !== currentSearchValue) {
        dataTableReference.columns(col.col_idx).search(newSearchValue).draw();
      }
    };
  }

  //------------------------------------/
  //  Column specification validation   /
  //------------------------------------/

  validateColumnSpecifications() {
    if (!this._checkColumnsIdxContinuous(this.columnsSpecifications)) {
      throw new Error(
        "Column specifications must have continuous col_idx values starting from 0 with no gaps",
      );
    }

    if (!this._checkColumnsIdxSorted(this.columnsSpecifications)) {
      throw new Error(
        "Column specifications must be sorted in ascending order of col_idx",
      );
    }

    if (!this._checkConsecutiveColumnGroups(this.columnsSpecifications)) {
      throw new Error(
        "Column specifications must have column groups that form contiguous blocks of columns",
      );
    }
  }

  _checkColumnsIdxContinuous(columnsSpecifications) {
    for (let i = 1; i < columnsSpecifications.length; i++) {
      if (
        columnsSpecifications[i].col_idx -
          columnsSpecifications[i - 1].col_idx !==
        1
      ) {
        return false;
      }
    }
    return true;
  }

  _checkColumnsIdxSorted(columnsSpecifications) {
    for (let i = 1; i < columnsSpecifications.length; i++) {
      if (
        columnsSpecifications[i].col_idx < columnsSpecifications[i - 1].col_idx
      ) {
        return false;
      }
    }
    return true;
  }

  _checkConsecutiveColumnGroups(columnsSpecifications) {
    const sorted = [...columnsSpecifications].sort(
      (a, b) => a.col_idx - b.col_idx,
    );
    const closedGroups = new Set();
    let currentGroup = null;

    for (const col of sorted) {
      if (col.column_group !== currentGroup) {
        // true = end of group
        if (closedGroups.has(col.column_group)) {
          //group previously closed
          throw new Error(
            `column_group "${col.column_group}" is non-contiguous: it appears at col_idx ${col.col_idx} after being interrupted by other groups`,
          );
        }
        if (currentGroup !== null) closedGroups.add(currentGroup);
        currentGroup = col.column_group;
      }
    }
    return true;
  }

  //------------------------------/
  //  Data Table Initialisation   /
  //------------------------------/

  colSpecToDataTableColDef(colSpec) {
    const colDef = { data: colSpec.json_id };
    if (colSpec.data_type === "weblink") {
      colDef.render = this.renderWeblink;
    }
    return colDef;
  }

  //------------------------------/
  //  Custom rendering handlers   /
  //------------------------------/

  renderWeblink(data, type, row, meta) {
    if (type === "display" && data) {
      return `<a href="${data.anchor_href}" target="_blank">${data.anchor_content}</a>`;
    }
    return data;
  }

  //-------------------------/
  //  Configuration request  /
  //-------------------------/

  static async fetchConfiguration(dataTableConfigName, dataTableConfigVariant, columnConfigName, columnConfigVariant,) {
    
     const [cols, datatable] = await Promise.all([
      TableManager._fetchConfigurationAsync(
        "column",
        columnConfigName,
        columnConfigVariant),      
      TableManager._fetchConfigurationAsync(
        "datatable",
        dataTableConfigName,
        dataTableConfigVariant,
      )]);      

      return {
        columnsSpecifications: cols,
        datatableConfiguration: datatable,
      };

  }

  // Fetch table configuration JSON from API endpoint
  // endpoint format: /table_provider/configuration/{configurationType}/{tableName}/{configurationVariant}
  static async _fetchConfigurationAsync(
    configurationType,
    tableName,
    configurationVariant,
  ) {
    if (!configurationType || !tableName || !configurationVariant) {
      throw new Error(
        "configurationType, tableName and configurationVariant are required",
      );
    }

    const url = `/table_provider/configuration/${encodeURIComponent(
      configurationType,
    )}/${encodeURIComponent(tableName)}/${encodeURIComponent(
      configurationVariant,
    )}`;

    try {
      const resp = await fetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(
          `Failed to fetch configuration: ${resp.status} ${resp.statusText} - ${text}`,
        );
      }

      const data = await resp.json();
      return data;
    } catch (err) {
      console.error("Error fetching table configuration:", err);
      throw err;
    }
  }
}
