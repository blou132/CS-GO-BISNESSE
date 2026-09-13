import { describe, expect, it } from "vitest";
import { parsePaintSeeds } from "./watchlist";

describe("paint seed input", () => {
  it("keeps seed zero and deduplicates integers", () => {
    expect(parsePaintSeeds(" 661, 0, 255, 661 ")).toEqual([0, 255, 661]);
    expect(parsePaintSeeds("")).toEqual([]);
  });

  it("rejects fractions, ranges, blanks and non-decimal notation", () => {
    for (const value of ["1.5", "-1", "1001", "1-20", "1,,2", "0x10", "1e2"]) {
      expect(() => parsePaintSeeds(value)).toThrow();
    }
  });
});
