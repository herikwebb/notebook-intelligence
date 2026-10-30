// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { formatNumber as fmtNumber } from '../../src/i18n';
import { initTranslations } from '../../src/i18n';
import { pseudoBundle } from './pseudo-translator';

afterEach(() => initTranslations(null));

describe('performance panel numbers', () => {
  it('keeps the English output the panel always had', () => {
    expect(fmtNumber(1200, 0)).toBe('1200');
    expect(fmtNumber(1.005, 2)).toBe((1.005).toFixed(2));
    expect(fmtNumber(-0.3, 0)).toBe('0');
  });

  it("uses the language's decimal separator", () => {
    initTranslations({ languageCode: 'de_DE', load: () => pseudoBundle });
    expect(fmtNumber(2.5, 1)).toBe('2,5');
    expect(fmtNumber(1200, 0)).toBe('1200');
  });
});
