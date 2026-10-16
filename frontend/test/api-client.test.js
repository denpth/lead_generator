import { test } from "node:test";
import assert from "node:assert/strict";
import {
  formatDate,
  isLead,
  phoneError,
  readApiResponse,
} from "../public/api-client.js";

const lead = {
  id: "32964ff4-d952-4b53-9aa1-6a91d9046e0e",
  status: "dispatched",
  dispatch_attempts: 1,
  created_at: "2026-09-28T11:16:49Z",
  updated_at: "2026-09-28T11:16:49Z",
};
test("accepts saved leads without optional name/company details", async () => {
  assert.deepEqual(
    await readApiResponse(Response.json(lead), { write: true }),
    lead,
  );
  assert.equal(isLead(lead), true);
});
test("rejects malformed successful responses instead of rendering imaginary leads", async () => {
  for (const value of [
    {},
    { detail: "Invalid phone" },
    { ...lead, created_at: undefined },
    { ...lead, status: "unknown" },
  ]) {
    await assert.rejects(
      readApiResponse(Response.json(value), { write: true }),
      /could not confirm the save/,
    );
  }
  await assert.rejects(
    readApiResponse(new Response("<html>Remote login</html>"), { write: true }),
    /may already be saved/,
  );
  await assert.rejects(
    readApiResponse(
      Response.json({
        items: [{}],
        total: 1,
        counts: { pending: 0, failed: 0, dispatched: 1 },
      }),
      { page: true },
    ),
    /unexpected response/,
  );
});
test("shows validation errors rather than treating them as leads", async () => {
  await assert.rejects(
    readApiResponse(
      Response.json(
        {
          detail: [
            {
              loc: ["body", "phone"],
              msg: "Phone must contain at least 7 digits",
            },
          ],
        },
        { status: 422 },
      ),
      { write: true },
    ),
    /phone: Phone must contain at least 7 digits/,
  );
});
test("missing or malformed dates never render Invalid Date or the Unix epoch", () => {
  for (const value of [undefined, null, "", "not-a-date"])
    assert.equal(formatDate(value), "Not available");
  assert.notEqual(formatDate(lead.created_at), "Not available");
});
test("phone validation counts digits, not punctuation, and allows blank optional phone", () => {
  assert.equal(phoneError(undefined), "");
  assert.equal(phoneError(""), "");
  assert.equal(phoneError("(555) 123-4567"), "");
  assert.match(phoneError("123"), /at least 7 digits/);
  assert.match(phoneError("(1) -- 2"), /at least 7 digits/);
  assert.match(phoneError("not a phone"), /only digits/);
});
