/**
 * Compliance Violations Table — Client-Side Sorting
 *
 * Provides in-browser sorting for the violations table without
 * server round-trips. Supports text, severity-rank, and date comparators.
 */
(function () {
  "use strict";

  var SEVERITY_RANK = { critical: 4, high: 3, medium: 2, low: 1 };

  function ComplianceSortManager() {
    this.currentSort = { column: null, direction: "asc" };
    this.init();
  }

  ComplianceSortManager.prototype.init = function () {
    this.setupEventListeners();
  };

  ComplianceSortManager.prototype.setupEventListeners = function () {
    var self = this;
    var headers = document.querySelectorAll("[data-sort-column]");
    headers.forEach(function (header) {
      header.addEventListener("click", function (e) {
        self.handleSort(e);
      });
    });
  };

  ComplianceSortManager.prototype.handleSort = function (event) {
    var header = event.currentTarget;
    var columnIndex = parseInt(header.getAttribute("data-sort-column"), 10);
    var sortType = header.getAttribute("data-sort-type") || "text";

    // Toggle direction
    if (this.currentSort.column === columnIndex) {
      this.currentSort.direction =
        this.currentSort.direction === "asc" ? "desc" : "asc";
    } else {
      this.currentSort.column = columnIndex;
      this.currentSort.direction = "asc";
    }

    this.sortTable(columnIndex, this.currentSort.direction, sortType);
    this.updateHeaderIcons(header);
  };

  ComplianceSortManager.prototype.sortTable = function (
    columnIndex,
    direction,
    sortType
  ) {
    var table = document.querySelector("[data-sortable-table]");
    if (!table) return;

    var tbody = table.querySelector("tbody");
    if (!tbody) return;

    var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));

    rows.sort(function (a, b) {
      var cellA = a.querySelectorAll("td")[columnIndex];
      var cellB = b.querySelectorAll("td")[columnIndex];
      if (!cellA || !cellB) return 0;

      var valA = (cellA.getAttribute("data-sort-value") || cellA.textContent || "").trim().toLowerCase();
      var valB = (cellB.getAttribute("data-sort-value") || cellB.textContent || "").trim().toLowerCase();

      var result = 0;

      if (sortType === "severity") {
        result = (SEVERITY_RANK[valA] || 0) - (SEVERITY_RANK[valB] || 0);
      } else if (sortType === "date") {
        var dateA = Date.parse(valA) || 0;
        var dateB = Date.parse(valB) || 0;
        result = dateA - dateB;
      } else {
        result = valA.localeCompare(valB);
      }

      return direction === "desc" ? -result : result;
    });

    // Re-append sorted rows
    rows.forEach(function (row) {
      tbody.appendChild(row);
    });
  };

  ComplianceSortManager.prototype.updateHeaderIcons = function (activeHeader) {
    // Reset all icons to neutral
    var allHeaders = document.querySelectorAll("[data-sort-column]");
    allHeaders.forEach(function (h) {
      var icon = h.querySelector(".sort-icon");
      if (icon) {
        icon.className = "sort-icon fas fa-sort ml-1 text-xs text-gray-400";
      }
      h.classList.remove("text-gray-900");
      h.classList.add("text-gray-500");
    });

    // Set active header icon
    var activeIcon = activeHeader.querySelector(".sort-icon");
    if (activeIcon) {
      if (this.currentSort.direction === "asc") {
        activeIcon.className = "sort-icon fas fa-sort-up ml-1 text-xs text-gray-900";
      } else {
        activeIcon.className = "sort-icon fas fa-sort-down ml-1 text-xs text-gray-900";
      }
    }
    activeHeader.classList.remove("text-gray-500");
    activeHeader.classList.add("text-gray-900");
  };

  // Initialize on page load and after HTMX content swaps
  function initSortManager() {
    if (document.querySelector("[data-sortable-table]")) {
      new ComplianceSortManager();
    }
  }

  document.addEventListener("DOMContentLoaded", initSortManager);
  document.addEventListener("htmx:afterSettle", initSortManager);
})();
