const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function convertModel(file) {
  const formData = new FormData();
  formData.append("file", file);

  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/convert`, {
      method: "POST",
      body: formData,
    });
  } catch (error) {
    throw new Error(
      `Não foi possível conectar ao backend em ${API_BASE_URL}. Verifique se o servidor FastAPI está rodando.`,
    );
  }

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail || "Não foi possível converter o modelo.";
    throw new Error(detail);
  }

  return payload;
}

export async function generateRig(payload) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}/api/rig`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new Error(
      `Não foi possível conectar ao backend em ${API_BASE_URL}. Verifique se o servidor FastAPI está rodando.`,
    );
  }

  const responsePayload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = responsePayload?.detail || "Não foi possível gerar o rig.";
    throw new Error(detail);
  }

  return responsePayload;
}

export function resolveModelUrl(fileUrl) {
  if (!fileUrl) {
    throw new Error("A API não retornou a URL do modelo convertido.");
  }

  if (fileUrl.startsWith("http://") || fileUrl.startsWith("https://")) {
    return fileUrl;
  }

  return `${API_BASE_URL}${fileUrl}`;
}
