import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TextField } from "./TextField";

describe("TextField", () => {
  it("connects the label to the input", () => {
    render(<TextField label="UofM email" type="email" />);
    expect(screen.getByLabelText("UofM email")).toHaveAttribute("type", "email");
  });

  it("marks the input invalid and reads out the error", () => {
    render(<TextField label="UofM email" error="Use your @myumanitoba.ca email" />);
    const input = screen.getByLabelText("UofM email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Use your @myumanitoba.ca email");
  });

  it("shows and hides a password", async () => {
    render(<TextField label="Password" type="password" />);
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("type", "password");

    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(input).toHaveAttribute("type", "text");

    await userEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(input).toHaveAttribute("type", "password");
  });
});
