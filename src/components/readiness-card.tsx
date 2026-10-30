// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, { useEffect, useRef, useState } from 'react';
import { requestAPI } from '../handler';
import { VscRefresh, VscWarning } from '../icons';
import { TranslationBundle } from '@jupyterlab/translation';
import { useTrans } from '../i18n';

type Level = 'ok' | 'warn' | 'blocked' | 'skipped';
type Verdict = 'ready' | 'degraded' | 'not_ready';

interface IReadinessCheck {
  id: string;
  group: string;
  level: Level;
  title: string;
  detail: string;
  // Present on every blocked or warning row: the specific next action. The
  // whole point of the feature is that the user is never left with "something
  // went wrong" and no idea what to do about it.
  remedy?: string;
}

interface IReadinessDoc {
  schema_version: number;
  generated_at: string;
  verdict: Verdict;
  headline: string;
  checks: IReadinessCheck[];
}

function groupLabel(trans: TranslationBundle, group: string): string {
  switch (group) {
    case 'mode':
      return trans.__('Chat path');
    case 'provider':
      return trans.__('Model provider');
    case 'claude':
      return trans.__('Claude mode');
    case 'acp':
      return trans.__('ACP agent');
    case 'live':
      return trans.__('Live endpoint check');
    default:
      return group;
  }
}

function verdictLabel(trans: TranslationBundle, verdict: Verdict): string {
  switch (verdict) {
    case 'ready':
      return trans._p('readiness verdict', 'Ready');
    case 'degraded':
      return trans._p('readiness verdict', 'Ready, with warnings');
    case 'not_ready':
      return trans._p('readiness verdict', 'Not ready');
    default: {
      // Every verdict needs a label; one this build does not know is shown
      // as the server sent it rather than as a wrong verdict.
      const unknownVerdict: never = verdict;
      return unknownVerdict;
    }
  }
}

function levelLabel(trans: TranslationBundle, level: Level): string {
  switch (level) {
    case 'ok':
      return trans._p('readiness check level', 'ok');
    case 'warn':
      return trans._p('readiness check level', 'warn');
    case 'blocked':
      return trans._p('readiness check level', 'blocked');
    case 'skipped':
      return trans._p('readiness check level', 'skipped');
    default: {
      // A level this build does not know is shown as the server sent it.
      const unknownLevel: never = level;
      return unknownLevel;
    }
  }
}

// The settings dialog unmounts and remounts this component on every tab
// switch and every reopen, and a readiness run is not free: it walks PATH,
// lists models, and in Claude mode forks `claude --version`. Cache the last
// document briefly so reopening the dialog is instant and does not re-fork.
const CACHE_TTL_MS = 30_000;
let cachedDoc: IReadinessDoc | null = null;
let cachedAt = 0;

export function _resetReadinessCacheForTests(): void {
  cachedDoc = null;
  cachedAt = 0;
}

function readCache(): IReadinessDoc | null {
  if (cachedDoc && Date.now() - cachedAt < CACHE_TTL_MS) {
    return cachedDoc;
  }
  return null;
}

function writeCache(doc: IReadinessDoc | null): void {
  cachedDoc = doc;
  cachedAt = doc ? Date.now() : 0;
}

function errorMessage(error: any): string {
  return error?.message ?? String(error);
}

export function ReadinessCard(_props: any): JSX.Element {
  const trans = useTrans();
  const [doc, setDoc] = useState<IReadinessDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [liveRunning, setLiveRunning] = useState(false);
  const [awaitingConfirm, setAwaitingConfirm] = useState(false);

  // Monotonic request id. Both buttons are disabled while a run is in
  // flight, so the UI cannot start two itself; this guards the case where a
  // future caller (or a re-render) does, and pairs with the unmount guard
  // below, which IS reachable: closing the dialog mid-request would
  // otherwise setState on an unmounted component.
  const requestSeq = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = async (live: boolean) => {
    const seq = ++requestSeq.current;
    if (live) {
      setLiveRunning(true);
    } else {
      setLoading(true);
    }
    setError(null);
    setAwaitingConfirm(false);
    try {
      const data = live
        ? await requestAPI<IReadinessDoc>('readiness', {
            method: 'POST',
            body: JSON.stringify({ live: true })
          })
        : await requestAPI<IReadinessDoc>('readiness');
      if (seq !== requestSeq.current || !mounted.current) {
        return;
      }
      setDoc(data);
      writeCache(data);
    } catch (e: any) {
      if (seq !== requestSeq.current || !mounted.current) {
        return;
      }
      // Drop the previous document too. Leaving it would render a green
      // "Ready" pill and stale rows next to "Readiness check failed", which
      // is the one thing this card must never do: a check that could not run
      // must not read as a pass.
      setDoc(null);
      writeCache(null);
      setError(errorMessage(e));
    } finally {
      if (seq === requestSeq.current && mounted.current) {
        setLoading(false);
        setLiveRunning(false);
      }
    }
  };

  useEffect(() => {
    // Served from a short-lived cache when the dialog is reopened or the
    // user switches tabs and comes back: each run walks PATH and, in Claude
    // mode, forks `claude --version`.
    const cached = readCache();
    if (cached) {
      setDoc(cached);
      setLoading(false);
      return;
    }
    load(false);
    // Only on mount; the buttons drive subsequent runs.
  }, []);

  const groups: string[] = [];
  for (const check of doc?.checks ?? []) {
    if (!groups.includes(check.group)) {
      groups.push(check.group);
    }
  }

  return (
    <div className="nbi-readiness">
      <div className="nbi-readiness-header">
        <div
          className={`nbi-readiness-verdict nbi-readiness-verdict-${doc?.verdict ?? 'unknown'}`}
        >
          {doc
            ? verdictLabel(trans, doc.verdict)
            : loading
              ? trans._p('readiness verdict', 'Checking…')
              : trans._p('readiness verdict', 'Unknown')}
        </div>
        <div className="nbi-readiness-headline">
          {error
            ? trans.__('Readiness check failed: %1', error)
            : (doc?.headline ?? trans.__('Checking configuration…'))}
        </div>
        <div className="nbi-readiness-actions">
          <button
            className="jp-Dialog-button jp-mod-reject jp-mod-styled"
            onClick={() => load(false)}
            disabled={loading || liveRunning}
          >
            <VscRefresh />
            <div className="jp-Dialog-buttonLabel">
              {loading ? trans.__('Checking…') : trans.__('Re-check')}
            </div>
          </button>
          <button
            className="jp-Dialog-button jp-mod-reject jp-mod-styled"
            onClick={() => setAwaitingConfirm(true)}
            disabled={loading || liveRunning}
            title={trans.__(
              'Sends one short request to your configured model to verify streaming and tool support.'
            )}
          >
            <div className="jp-Dialog-buttonLabel">
              {liveRunning
                ? trans.__('Running…')
                : trans.__('Test the endpoint')}
            </div>
          </button>
        </div>
      </div>

      {awaitingConfirm && (
        <div className="nbi-readiness-confirm">
          <VscWarning />
          <span>
            {trans.__(
              'This sends one short request to your configured model. It costs a few tokens and is the only way to confirm the endpoint really streams and really accepts tool calls.'
            )}
          </span>
          <button
            className="jp-Dialog-button jp-mod-accept jp-mod-styled"
            onClick={() => load(true)}
          >
            <div className="jp-Dialog-buttonLabel">{trans.__('Run it')}</div>
          </button>
          <button
            className="jp-Dialog-button jp-mod-reject jp-mod-styled"
            onClick={() => setAwaitingConfirm(false)}
          >
            <div className="jp-Dialog-buttonLabel">{trans.__('Cancel')}</div>
          </button>
        </div>
      )}

      {groups.map(group => (
        <div className="nbi-readiness-group" key={group}>
          <div className="nbi-readiness-group-title">
            {groupLabel(trans, group)}
          </div>
          {(doc?.checks ?? [])
            .filter(c => c.group === group)
            .map(check => (
              <div className="nbi-readiness-row" key={check.id}>
                <div className="nbi-readiness-row-head">
                  <span
                    className={`nbi-readiness-badge nbi-readiness-badge-${check.level}`}
                  >
                    {levelLabel(trans, check.level)}
                  </span>
                  <span className="nbi-readiness-title">{check.title}</span>
                  <span className="nbi-readiness-detail">{check.detail}</span>
                </div>
                {check.remedy && (
                  <div className="nbi-readiness-remedy">{check.remedy}</div>
                )}
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}
