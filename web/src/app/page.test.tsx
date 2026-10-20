import { beforeEach, describe, expect, it, vi } from "vitest";

const redirect = vi.fn();
vi.mock("next/navigation", () => ({ redirect: (path: string) => redirect(path) }));

import HomePage from "./page";

describe("HomePage", () => {
  beforeEach(() => redirect.mockClear());

  it("sends visitors into the app at the rider home", () => {
    HomePage();
    expect(redirect).toHaveBeenCalledWith("/ride");
  });
});
