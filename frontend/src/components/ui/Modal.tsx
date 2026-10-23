"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";

import { backdropClose, newBackdropPress } from "./backdropClose";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  flush?: boolean;
  size?: "sm" | "md" | "lg" | "xl" | "full";
  closeOnBackdropClick?: boolean;
  closeOnEscape?: boolean;
  className?: string;
  /** For a dialog without a visible title of its own. */
  ariaLabel?: string;
}

/** Everything inside the dialog a Tab can land on, in document order. */
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), '
  + 'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const sizeClass: Record<NonNullable<ModalProps["size"]>, string> = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
  full: "max-w-[1400px]",
};

type Area = { left: number; top: number; width: number; height: number };

/** The layout viewport can be wider than the screen, so the dialog follows the visible area. */
function useVisibleArea(open: boolean): Area | null {
  const [area, setArea] = useState<Area | null>(null);
  useEffect(() => {
    const vv = typeof window === "undefined" ? null : window.visualViewport;
    if (!open || !vv) return;
    const read = () =>
      setArea({ left: vv.offsetLeft, top: vv.offsetTop, width: vv.width, height: vv.height });
    read();
    vv.addEventListener("resize", read);
    vv.addEventListener("scroll", read);
    return () => {
      vv.removeEventListener("resize", read);
      vv.removeEventListener("scroll", read);
    };
  }, [open]);
  return open ? area : null;
}

export default function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  flush = false,
  size = "md",
  closeOnBackdropClick = true,
  closeOnEscape = true,
  className = "",
  ariaLabel,
}: ModalProps) {
  const t = useTranslations("common");
  const dialogRef = useRef<HTMLDivElement>(null);
  const press = useRef(newBackdropPress()).current;
  const area = useVisibleArea(open);
  const titleId = `${useId()}-title`;

  // The dialog takes the focus when it opens and hands it back when it closes,
  // otherwise the keyboard stays on the page behind the overlay.
  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    // The panel itself, so the name of the dialog is read out first and Tab
    // then walks its own content from the top.
    dialogRef.current?.focus();
    return () => before?.focus?.();
  }, [open]);

  // Tab must not walk out of the dialog into the cards under the overlay.
  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key !== "Tab") return;
      const dialog = dialogRef.current;
      if (!dialog) return;
      const items = [...dialog.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (items.length === 0) {
        e.preventDefault();
        dialog.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (!e.shiftKey && (active === last || !dialog.contains(active))) {
        e.preventDefault();
        first.focus();
      } else if (e.shiftKey && (active === first || !dialog.contains(active))) {
        e.preventDefault();
        last.focus();
      }
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  useEffect(() => {
    if (!open || !closeOnEscape) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, closeOnEscape, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed z-50 flex items-center justify-center p-4"
      style={{
        backgroundColor: "rgba(0, 0, 0, 0.5)",
        ...(area
          ? { left: area.left, top: area.top, width: area.width, height: area.height }
          : { inset: 0 }),
      }}
      {...backdropClose(press, onClose, closeOnBackdropClick)}
      role="dialog"
      aria-modal="true"
      // A dialog without a name is announced as "dialog" and nothing else.
      aria-labelledby={title ? titleId : undefined}
      aria-label={title ? undefined : ariaLabel}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className={`w-full ${sizeClass[size]} rounded-xl shadow-lg flex flex-col max-h-full focus:outline-none ${className}`}
        style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div
            className="px-5 py-4 flex items-center justify-between gap-4"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            {/* min-w-0 plus the break: a long file name must not push the close button out of the dialog. */}
            <div id={titleId} className="min-w-0 break-words text-base font-semibold" style={{ color: "var(--foreground)" }}>
              {title}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("close")}
              className="w-7 h-7 flex-shrink-0 inline-flex items-center justify-center rounded-full btn-icon dark:text-white dark:hover:!text-white transition-colors"
              style={{ backgroundColor: "var(--surface-dim)" }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        <div className={`${flush ? "" : "px-5 py-4"} overflow-y-auto flex-1`}>{children}</div>

        {footer && (
          <div
            className="px-5 py-3 flex items-center justify-end gap-2"
            style={{ borderTop: "1px solid var(--border)" }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
