export class RigDiagnosticsPanel {
  constructor(container) {
    this.container = container;
    this.clear();
  }

  clear() {
    this.container.hidden = true;
    this.container.replaceChildren();
  }

  render(report) {
    this.container.hidden = false;
    this.container.replaceChildren();

    const title = document.createElement("h2");
    title.textContent = "Diagnóstico do Rig";

    const summary = document.createElement("div");
    summary.className = "diagnostics-summary";
    summary.append(
      createMetric("Skinning aplicado", report?.skinningApplied ? "sim" : "não"),
      createMetric("Meshes processados", String(report?.meshCount ?? 0)),
      createMetric("Ações", formatList(report?.actions)),
    );

    const meshList = document.createElement("div");
    meshList.className = "diagnostics-mesh-list";

    const vertexGroups = report?.vertexGroups || {};
    const weightedVertexGroups = report?.weightedVertexGroups || {};
    const meshNames = [
      ...new Set([...(report?.meshes || []), ...Object.keys(vertexGroups)]),
    ];

    if (meshNames.length === 0) {
      meshList.append(createEmpty("Nenhum mesh informado no relatório."));
    } else {
      for (const meshName of meshNames) {
        const row = document.createElement("div");
        row.className = "diagnostics-mesh-row";
        row.append(
          createMetric("Malha", meshName),
          createMetric("Grupos de vértices", String(vertexGroups[meshName]?.length || 0)),
          createMetric("Grupos com peso", String(weightedVertexGroups[meshName]?.length || 0)),
        );
        meshList.append(row);
      }
    }

    const warnings = document.createElement("div");
    warnings.className = "diagnostics-warnings";
    const warningTitle = document.createElement("h3");
    warningTitle.textContent = "Avisos";
    warnings.append(warningTitle);

    if (Array.isArray(report?.warnings) && report.warnings.length > 0) {
      const list = document.createElement("ul");
      for (const warning of report.warnings) {
        const item = document.createElement("li");
        item.textContent = warning;
        list.appendChild(item);
      }
      warnings.appendChild(list);
    } else {
      warnings.append(createEmpty("nenhum"));
    }

    this.container.append(title, summary, meshList, warnings);
  }
}

function createMetric(label, value) {
  const item = document.createElement("div");
  item.className = "diagnostics-metric";

  const labelElement = document.createElement("span");
  labelElement.textContent = label;

  const valueElement = document.createElement("strong");
  valueElement.textContent = value || "-";

  item.append(labelElement, valueElement);
  return item;
}

function createEmpty(text) {
  const empty = document.createElement("p");
  empty.className = "diagnostics-empty";
  empty.textContent = text;
  return empty;
}

function formatList(values) {
  return Array.isArray(values) && values.length > 0 ? values.join(", ") : "nenhuma";
}
