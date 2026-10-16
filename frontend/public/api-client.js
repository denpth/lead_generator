const states = new Set(["pending", "dispatched", "failed"]);
const uuid = /^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const timestamp = (value) =>
  typeof value === "string" &&
  value.length > 0 &&
  Number.isFinite(Date.parse(value));
const count = (value) => Number.isInteger(value) && value >= 0;

export function isLead(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    uuid.test(value.id) &&
    states.has(value.status) &&
    timestamp(value.created_at) &&
    timestamp(value.updated_at) &&
    count(value.dispatch_attempts)
  );
}

export function phoneError(value) {
  if (!value) return "";
  if (!/^[0-9+().\-\s]{1,32}$/.test(value)) {
    return "Phone can contain only digits, spaces, +, parentheses, periods, and hyphens (up to 32 characters).";
  }
  if (value.replace(/\D/g, "").length < 7)
    return "Phone must contain at least 7 digits, or leave it blank and provide an email address.";
  return "";
}

export function formatDate(value, full = false) {
  if (!timestamp(value)) return "Not available";
  return new Date(value).toLocaleString(
    undefined,
    full
      ? { dateStyle: "medium", timeStyle: "short" }
      : { month: "short", day: "numeric", year: "numeric" },
  );
}

export async function readApiResponse(
  response,
  { page = false, write = false } = {},
) {
  const unexpected = write
    ? "The server returned an unexpected response, so we could not confirm the save. Refresh the inbox before submitting again; the lead may already be saved."
    : "The server returned an unexpected response. Refresh the page and check that you are using the lead dashboard address.";
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(unexpected);
  }
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(
      Array.isArray(detail)
        ? detail
            .map(
              (error) =>
                `${error.loc?.slice(1).join(" › ") || "Lead"}: ${error.msg}`,
            )
            .join(" · ")
        : typeof detail === "string"
          ? detail
          : "The request could not be completed.",
    );
  }
  const valid = page
    ? body &&
      Array.isArray(body.items) &&
      body.items.every(isLead) &&
      count(body.total) &&
      body.counts &&
      [...states].every((state) => count(body.counts[state]))
    : isLead(body);
  if (!valid) throw new Error(unexpected);
  return body;
}
