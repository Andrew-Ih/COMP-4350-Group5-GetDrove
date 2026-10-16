import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { setAccessToken } from "@/shared/api";

import { RequireAuth } from "./RequireAuth";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/ride",
}));

afterEach(() => {
  setAccessToken(undefined);
  replace.mockReset();
});

describe("RequireAuth", () => {
  it("sends a logged-out visitor to log in, coming back here afterwards", () => {
    render(<RequireAuth>secret</RequireAuth>);

    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fride");
  });

  it("shows the page to a logged-in student", () => {
    setAccessToken("tok");
    render(<RequireAuth>secret</RequireAuth>);

    expect(screen.getByText("secret")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
