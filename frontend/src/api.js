export async function request(path, token, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401)
      throw new Error("Token inválido. Verifique o acesso nas configurações.");
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Não foi possível concluir. Verifique os dados e a conexão.",
    );
  }
  return response.json();
}
export function bytes(value = 0) {
  if (!value) return "0 B";
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 4);
  return `${(value / 1024 ** index).toFixed(index ? 1 : 0)} ${["B", "KB", "MB", "GB", "TB"][index]}`;
}
export const date = (value) =>
  value
    ? new Date(value).toLocaleString("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : "Ainda não";
export function progress(job) {
  return job.found
    ? Math.min(
        100,
        Math.round(
          ((job.existing + job.downloaded + job.errors) / job.found) * 100,
        ),
      )
    : job.status === "completed"
      ? 100
      : 0;
}
