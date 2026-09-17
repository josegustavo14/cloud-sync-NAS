import { afterEach, describe, expect, it, vi } from "vitest";
import { bytes, progress, request } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("sync presentation", () => {
  it("does not double count deduplicated downloads", () =>
    expect(
      progress({
        found: 10,
        existing: 4,
        downloaded: 5,
        duplicates: 3,
        errors: 1,
      }),
    ).toBe(100));
  it("handles discovery and empty completed jobs", () => {
    expect(progress({ found: 0, status: "running" })).toBe(0);
    expect(progress({ found: 0, status: "completed" })).toBe(100);
  });
  it("formats storage", () => {
    expect(bytes(1024)).toBe("1.0 KB");
    expect(bytes(0)).toBe("0 B");
  });
  it("sends credentials in a header and surfaces authentication errors", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    vi.stubGlobal("fetch", fetch);
    await expect(request("/accounts", "secret")).rejects.toThrow(
      "Token inválido",
    );
    expect(fetch.mock.calls[0][0]).toBe("/api/accounts");
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer secret");
  });
});
