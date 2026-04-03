/**
 * Returns a grading company cert-lookup URL given a company name and cert number,
 * or null if the company is unknown or either value is missing.
 */
export function gradingLookupUrl(company: string, certNumber: string): string | null {
  const cert = certNumber.trim();
  if (!cert || !company.trim()) return null;

  const c = company.toLowerCase();

  if (c.includes('psa'))
    return `https://www.psacard.com/cert/${cert}`;

  if (c.includes('beckett') || c.includes('bgs') || c.includes('bvg') || c.includes('bccg'))
    return `https://www.beckett.com/grading/card-lookup?item_id=${cert}`;

  if (c.includes('sgc'))
    return `https://www.sgccard.com/research/lookup/?cert=${cert}`;

  if (c.includes('cgc'))
    return `https://www.cgccards.com/certlookup/${cert}`;

  return null;
}
