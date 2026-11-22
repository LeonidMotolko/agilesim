import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useAsync } from "./useAsync";

describe("useAsync", () => {
  it("resolves reload() only after the new data has arrived", async () => {
    let value = 1;
    const load = vi.fn(() => Promise.resolve(value));
    const { result } = renderHook(() => useAsync(load));
    await waitFor(() => expect(result.current.data).toBe(1));

    value = 2;
    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.data).toBe(2);
    expect(load).toHaveBeenCalledTimes(2);
  });
});
