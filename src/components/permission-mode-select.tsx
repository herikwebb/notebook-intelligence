// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  VscCheck,
  VscChecklist,
  VscPassFilled,
  VscShield,
  VscWarning
} from '../icons';
import { TranslationBundle } from '@jupyterlab/translation';
import { getTextDirection, useTrans } from '../i18n';

export const BYPASS_PERMISSIONS_MODE = 'bypassPermissions';

// The menu's modes in order, each with its label. Bypass is listed last and
// offered only when policy allows it.
const MODES: ReadonlyArray<{
  mode: string;
  label: (trans: TranslationBundle) => string;
}> = [
  { mode: 'default', label: trans => trans._p('permission mode', 'Default') },
  {
    mode: 'acceptEdits',
    label: trans => trans._p('permission mode', 'Accept Edits')
  },
  { mode: 'plan', label: trans => trans._p('permission mode', 'Plan') },
  {
    mode: BYPASS_PERMISSIONS_MODE,
    label: trans => trans._p('permission mode', 'Bypass Permissions')
  }
];

function labelFor(trans: TranslationBundle, mode: string): string {
  return (MODES.find(m => m.mode === mode) ?? MODES[0]).label(trans);
}

/**
 * Resolve the selector mode after a server permission-mode notification.
 *
 * A `reset` notification (a fresh SDK session: skills reload, config change,
 * restart) must retire bypass but must NOT clobber an explicit non-bypass
 * selection the user already made, so a mid-session reconnect doesn't snap the
 * selector back to default (issue #377). A non-reset notification is an
 * authoritative server-driven switch (plan approval, the slash aliases) and
 * applies unconditionally.
 */
export function nextPermissionModeOnNotification(
  current: string,
  notification: { mode: string; reset: boolean }
): string {
  if (notification.reset) {
    return current === BYPASS_PERMISSIONS_MODE ? notification.mode : current;
  }
  return notification.mode;
}

// A distinct glyph per mode so the active selection reads at a glance in the
// compact footer (no room for a text label there), addressing #377. Bypass
// keeps the red warning glyph as its persistent, non-color-only indicator.
function iconFor(mode: string): JSX.Element {
  switch (mode) {
    case BYPASS_PERMISSIONS_MODE:
      return <VscWarning aria-hidden="true" />;
    case 'acceptEdits':
      return <VscPassFilled aria-hidden="true" />;
    case 'plan':
      return <VscChecklist aria-hidden="true" />;
    default:
      return <VscShield aria-hidden="true" />;
  }
}

export interface IPermissionModeSelectProps {
  value: string;
  bypassAllowed: boolean;
  onModeChange: (mode: string) => void;
}

/**
 * Permission-mode picker for Claude mode (issue #359).
 *
 * A compact footer icon button that opens a menu of modes rather than a
 * wide dropdown, to keep the narrow input footer uncluttered. Each mode has
 * a distinct glyph (shield / check / checklist / warning) so the active selection
 * reads at a glance, and the menu echoes the same glyphs (#359, #377).
 * Default / Accept Edits / Plan switch immediately. Bypass Permissions is
 * listed only when the admin policy allows it and never switches on the
 * first click: choosing it opens a confirm-to-arm step. While armed, the
 * button shows a red warning glyph as a persistent (non-color-only)
 * indicator.
 */
export function PermissionModeSelect(
  props: IPermissionModeSelectProps
): JSX.Element {
  const trans = useTrans();
  const [open, setOpen] = useState(false);
  const [pendingBypass, setPendingBypass] = useState(false);
  const bypassActive = props.value === BYPASS_PERMISSIONS_MODE;
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Close the menu on an outside click, matching the @-autocomplete and
  // tools popovers.
  useEffect(() => {
    if (!open) {
      return;
    }
    const handleClickOutside = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  // Move focus into the menu when it opens (the current item) so keyboard
  // and screen-reader users land on it.
  useEffect(() => {
    if (open) {
      menuRef.current
        ?.querySelector<HTMLButtonElement>('[aria-checked="true"]')
        ?.focus();
    }
  }, [open]);

  // Focus Cancel when the confirm-to-arm dialog opens.
  useEffect(() => {
    if (pendingBypass) {
      cancelRef.current?.focus();
    }
  }, [pendingBypass]);

  // The confirm popover renders in a body-level portal (below) so it escapes
  // the sidebar's stacking context; without that it gets clipped by the icon
  // rail on the left and covered by the main content panel on the right, both
  // of which out-paint an absolutely-positioned child of the sidebar (#377).
  // Position it just above the button, right-aligned, and clamp it inside the
  // viewport so it can't run off-screen in a narrow docked sidebar.
  const [confirmStyle, setConfirmStyle] = useState<React.CSSProperties>({});
  useLayoutEffect(() => {
    if (!pendingBypass) {
      return;
    }
    const reposition = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }
      const margin = 8;
      const width = Math.min(280, window.innerWidth - 2 * margin);
      const left = Math.max(
        margin,
        Math.min(rect.right - width, window.innerWidth - margin - width)
      );
      setConfirmStyle({
        position: 'fixed',
        left,
        bottom: window.innerHeight - rect.top + 6,
        width
      });
    };
    reposition();
    window.addEventListener('resize', reposition);
    return () => window.removeEventListener('resize', reposition);
  }, [pendingBypass]);

  const closeMenu = (restoreFocus = true) => {
    setOpen(false);
    if (restoreFocus) {
      buttonRef.current?.focus();
    }
  };

  const chooseMode = (mode: string) => {
    if (mode === BYPASS_PERMISSIONS_MODE) {
      setOpen(false);
      setPendingBypass(true);
      return;
    }
    setOpen(false);
    buttonRef.current?.focus();
    props.onModeChange(mode);
  };

  const dismissConfirm = () => {
    setPendingBypass(false);
    buttonRef.current?.focus();
  };

  // Offer bypass when the policy allows it, and also when it is already the
  // active mode (a policy flip mid-session shouldn't drop the armed value
  // from the menu before the sidebar resets it).
  const options =
    props.bypassAllowed || bypassActive
      ? MODES.map(m => m.mode)
      : MODES.map(m => m.mode).filter(mode => mode !== BYPASS_PERMISSIONS_MODE);
  const currentLabel = labelFor(trans, props.value);

  return (
    <div className="permission-mode-container" ref={containerRef}>
      {pendingBypass &&
        createPortal(
          <div
            className="permission-mode-confirm"
            // Portaled outside the sidebar, so it does not inherit its dir.
            dir={getTextDirection()}
            style={confirmStyle}
            ref={confirmRef}
            role="alertdialog"
            aria-modal="true"
            aria-label={trans.__('Confirm Bypass Permissions')}
            aria-describedby="permission-mode-confirm-message"
            onKeyDown={event => {
              if (event.key === 'Escape') {
                event.stopPropagation();
                dismissConfirm();
                return;
              }
              // Trap Tab within the dialog: it's portaled to <body> after the
              // trigger, so without this, Tab would walk into the JupyterLab
              // shell behind this security-gating alertdialog (issue #377).
              if (event.key === 'Tab') {
                const buttons = Array.from(
                  confirmRef.current?.querySelectorAll<HTMLButtonElement>(
                    'button'
                  ) ?? []
                );
                if (buttons.length === 0) {
                  return;
                }
                const first = buttons[0];
                const last = buttons[buttons.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                  event.preventDefault();
                  last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                  event.preventDefault();
                  first.focus();
                }
              }
            }}
          >
            <div
              id="permission-mode-confirm-message"
              className="permission-mode-confirm-message"
            >
              {trans.__(
                'Bypass Permissions runs every tool call without asking for confirmation, with your full user account access. Content the agent reads can steer what it runs. Stays on until you switch modes or start a new session.'
              )}
            </div>
            <div className="permission-mode-confirm-buttons">
              <button
                type="button"
                className="jp-Dialog-button jp-mod-styled jp-mod-reject"
                ref={cancelRef}
                onClick={dismissConfirm}
              >
                {trans.__('Cancel')}
              </button>
              <button
                type="button"
                className="jp-Dialog-button jp-mod-styled jp-mod-warn"
                onClick={() => {
                  setPendingBypass(false);
                  props.onModeChange(BYPASS_PERMISSIONS_MODE);
                  buttonRef.current?.focus();
                }}
              >
                {trans.__('Bypass permissions')}
              </button>
            </div>
          </div>,
          document.body
        )}
      {open && (
        <div
          className="permission-mode-menu"
          role="menu"
          ref={menuRef}
          aria-label={trans.__('Claude permission mode')}
          onKeyDown={event => {
            if (event.key === 'Escape') {
              event.stopPropagation();
              closeMenu();
              return;
            }
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
              // Roving focus between items, the expected role=menu behavior.
              event.preventDefault();
              const items = Array.from(
                menuRef.current?.querySelectorAll<HTMLButtonElement>(
                  '[role="menuitemradio"]'
                ) ?? []
              );
              const current = items.indexOf(
                document.activeElement as HTMLButtonElement
              );
              const delta = event.key === 'ArrowDown' ? 1 : -1;
              const next = (current + delta + items.length) % items.length;
              items[next]?.focus();
            }
          }}
        >
          {options.map(mode => {
            const label = labelFor(trans, mode);
            const selected = props.value === mode;
            return (
              <button
                type="button"
                key={mode}
                role="menuitemradio"
                aria-checked={selected}
                // Roving tabindex: the menu is a single Tab stop (focus opens
                // on the checked item; Arrow keys move between items).
                tabIndex={selected ? 0 : -1}
                className={`permission-mode-menu-item${
                  mode === BYPASS_PERMISSIONS_MODE
                    ? ' permission-mode-menu-item-bypass'
                    : ''
                }`}
                onClick={() => chooseMode(mode)}
              >
                <span className="permission-mode-menu-check">
                  {selected && <VscCheck aria-hidden="true" />}
                </span>
                <span className="permission-mode-menu-icon">
                  {iconFor(mode)}
                </span>
                {label}
              </button>
            );
          })}
        </div>
      )}
      <button
        type="button"
        ref={buttonRef}
        className={`user-input-footer-button permission-mode-button${
          bypassActive ? ' permission-mode-button-bypass' : ''
        }`}
        aria-haspopup="menu"
        aria-expanded={open}
        title={
          bypassActive
            ? trans.__(
                'Bypass Permissions is active: tool calls run without confirmation'
              )
            : trans.__('Permission mode: %1', currentLabel)
        }
        aria-label={
          bypassActive
            ? trans.__('Permission mode: Bypass Permissions is active')
            : trans.__('Permission mode: %1', currentLabel)
        }
        onClick={() => setOpen(o => !o)}
      >
        {iconFor(props.value)}
      </button>
    </div>
  );
}
