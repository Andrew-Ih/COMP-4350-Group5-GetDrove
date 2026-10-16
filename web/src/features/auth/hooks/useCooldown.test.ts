import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { formatCountdown, useCooldown } from "./useCooldown";

describe("formatCountdown", () => {
  it.each([
    [60, "1:00"],
    [45, "0:45"],
    [5, "0:05"],
    [0, "0:00"],
    [-3, "0:00"],
  ])("shows %i seconds as %s", (seconds, text) => expect(formatCountdown(seconds)).toBe(text));
});

describe("useCooldown", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("is ready until started, then counts down to ready again", () => {
    const { result } = renderHook(() => useCooldown(60));
    expect(result.current.remaining).toBe(0);

    act(() => result.current.start());
    expect(result.current.remaining).toBe(60);

    act(() => vi.advanceTimersByTime(15_000));
    expect(result.current.remaining).toBe(45);

    act(() => vi.advanceTimersByTime(45_000));
    expect(result.current.remaining).toBe(0);
  });
});
