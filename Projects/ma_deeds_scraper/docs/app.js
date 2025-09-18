const CSV_PATH = "records.csv";

function setLastUpdated() {
  fetch(CSV_PATH, { cache: "no-store" })
    .then(r => document.getElementById("lastUpdated").textContent = r.headers.get("last-modified") || "unknown")
    .catch(() => document.getElementById("lastUpdated").textContent = "unknown");
}

function populateCountyFilter(rows) {
  const sel = document.getElementById("countyFilter");
  [...new Set(rows.map(r => r.county).filter(Boolean))].sort().forEach(c => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    sel.appendChild(opt);
  });
}

function renderTable(rows) {
  const tbody = document.querySelector("#recordsTable tbody");
  tbody.innerHTML = "";
  rows.forEach(r => {
    const tr = document.createElement("tr");
    const tdC = document.createElement("td");
    tdC.textContent = r.county || "";
    const tdL = document.createElement("td");
    if (r.pdf_url) {
      const a = document.createElement("a");
      a.href = r.pdf_url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "Open PDF";
      tdL.appendChild(a);
    }
    tr.appendChild(tdC);
    tr.appendChild(tdL);
    tbody.appendChild(tr);
  });

  if ($.fn.dataTable.isDataTable("#recordsTable")) {
    $("#recordsTable").DataTable().destroy();
  }
  $("#recordsTable").DataTable({
    pageLength: 25,
    order: [[0, "asc"]],
    dom: "ftip"
  });
}

function applyFilter(allRows) {
  const c = document.getElementById("countyFilter").value;
  renderTable(c ? allRows.filter(r => r.county === c) : allRows);
}

function start() {
  Papa.parse(CSV_PATH, {
    download: true,
    header: true,
    skipEmptyLines: true,
    complete: res => {
      const rows = res.data.map(r => ({
        county: r.county || r.County || r.COUNTY,
        pdf_url: r.pdf_url || r.PDF || r["PDF Link"]
      }));
      populateCountyFilter(rows);
      renderTable(rows);
      document.getElementById("countyFilter").addEventListener("change", () => applyFilter(rows));
      setLastUpdated();
    }
  });
}

document.addEventListener("DOMContentLoaded", start);
