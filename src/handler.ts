// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { URLExt } from '@jupyterlab/coreutils';

import { ServerConnection } from '@jupyterlab/services';

import { getCatalogLocale } from './i18n';

/**
 * The query parameter naming the language the server writes in; matches
 * LOCALE_QUERY_ARG in notebook_intelligence/i18n.py. Not a header: a custom
 * header makes cross-origin requests need a CORS preflight that
 * jupyter_server's default allowed headers refuse.
 */
export const LOCALE_QUERY_ARG = 'nbi_locale';

/** A server URL carrying JupyterLab's language, when it is not English. */
export function withLocale(url: string): string {
  const locale = getCatalogLocale();
  if (!locale) {
    return url;
  }
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}${LOCALE_QUERY_ARG}=${encodeURIComponent(locale)}`;
}

/**
 * Call the API extension
 *
 * @param endPoint API REST end point for the extension
 * @param init Initial values for the request
 * @returns The response body interpreted as JSON
 */
export async function requestAPI<T>(
  endPoint = '',
  init: RequestInit = {}
): Promise<T> {
  // Make request to Jupyter API
  const settings = ServerConnection.makeSettings();
  // The server translates the text it writes for the user (the readiness
  // report, approval buttons) into this language.
  const requestUrl = withLocale(
    URLExt.join(
      settings.baseUrl,
      'notebook-intelligence', // API Namespace
      endPoint
    )
  );

  let response: Response;
  try {
    response = await ServerConnection.makeRequest(requestUrl, init, settings);
  } catch (error) {
    throw new ServerConnection.NetworkError(error as any);
  }

  let data: any = await response.text();

  if (data.length > 0) {
    try {
      data = JSON.parse(data);
    } catch (error) {
      console.log('Not a JSON response body.', response);
    }
  }

  if (!response.ok) {
    throw new ServerConnection.ResponseError(
      response,
      data.message || data.error || data
    );
  }

  return data;
}
