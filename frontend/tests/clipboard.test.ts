import { afterEach, expect, it, vi } from "vitest";
import { writeToClipboard } from "@/lib/clipboard";

function setClipboard(value: unknown) {
  Object.defineProperty(navigator, "clipboard", { configurable: true, value });
}

function setExecCommand(value: unknown) {
  Object.defineProperty(document, "execCommand", { configurable: true, value });
}

afterEach(() => {
  setClipboard(undefined);
  setExecCommand(undefined);
  vi.restoreAllMocks();
});

it("uses the Clipboard API when the context is secure", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  setClipboard({ writeText });

  expect(await writeToClipboard("bike lock")).toBe(true);
  expect(writeText).toHaveBeenCalledWith("bike lock");
});

it("falls back to execCommand when the Clipboard API is missing", async () => {
  // A plain-HTTP deployment from a public IP has no navigator.clipboard at all;
  // every copy used to report "复制失败，请手动复制" for that reason alone.
  setClipboard(undefined);
  const execCommand = vi.fn().mockReturnValue(true);
  setExecCommand(execCommand);

  expect(await writeToClipboard("bike lock")).toBe(true);
  expect(execCommand).toHaveBeenCalledWith("copy");
});

it("falls back when the Clipboard API rejects", async () => {
  setClipboard({ writeText: vi.fn().mockRejectedValue(new Error("denied")) });
  const execCommand = vi.fn().mockReturnValue(true);
  setExecCommand(execCommand);

  expect(await writeToClipboard("bike lock")).toBe(true);
  expect(execCommand).toHaveBeenCalledWith("copy");
});

it("reports failure when both paths fail", async () => {
  setClipboard(undefined);
  setExecCommand(vi.fn().mockReturnValue(false));

  expect(await writeToClipboard("bike lock")).toBe(false);
});

it("leaves no scratch element behind", async () => {
  setClipboard(undefined);
  setExecCommand(vi.fn().mockReturnValue(true));

  await writeToClipboard("bike lock");

  expect(document.querySelectorAll("textarea")).toHaveLength(0);
});

it("does nothing for an empty value", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  setClipboard({ writeText });

  expect(await writeToClipboard("")).toBe(false);
  expect(writeText).not.toHaveBeenCalled();
});
