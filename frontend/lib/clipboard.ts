/**
 * Clipboard writes that work outside a secure context.
 *
 * `navigator.clipboard` only exists on HTTPS or localhost, so the deployed app
 * served over plain HTTP from a public IP has no Clipboard API at all and every
 * copy silently failed. The legacy execCommand path still works there.
 */
export async function writeToClipboard(value: string): Promise<boolean> {
  if (!value) return false;

  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Permission denied or a non-secure context: fall through to the legacy path.
    }
  }

  return legacyWriteToClipboard(value);
}

function legacyWriteToClipboard(value: string): boolean {
  if (typeof document === "undefined") return false;
  let area: HTMLTextAreaElement | null = null;
  try {
    area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    // Keep it off-screen but still selectable: display:none would not select.
    area.style.position = "fixed";
    area.style.top = "-1000px";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, value.length);
    const copied = document.execCommand("copy");
    return copied;
  } catch {
    return false;
  } finally {
    area?.remove();
  }
}
