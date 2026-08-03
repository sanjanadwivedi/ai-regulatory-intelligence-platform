/**
 * Utility to resolve exact, authority-specific official government URLs for regulations.
 * Prevents generic fallback URLs or leftover id=12093 links from being returned
 * for non-KYC RBI directives.
 */

export interface RegulationLike {
  authority?: string | null;
  title?: string | null;
  sector?: string | null;
  source_url?: string | null;
  resolved_source_url?: string | null;
}

export const getOfficialSourceUrl = (reg: RegulationLike): string => {
  if (reg.resolved_source_url && reg.resolved_source_url.startsWith('http')) {
    return reg.resolved_source_url;
  }
  const rawUrl = (reg.source_url || '').trim();


  const authorityLower = (reg.authority || '').toLowerCase();
  const titleLower = (reg.title || '').toLowerCase();
  const sectorLower = (reg.sector || '').toLowerCase();

  // If rawUrl contains id=12093 (the KYC direction ID) but the regulation is NOT about KYC,
  // we explicitly override it to the document's actual RBI notification page.
  if (rawUrl.includes('id=12093') && !titleLower.includes('kyc') && !titleLower.includes('know your customer')) {
    if (titleLower.includes('communication policy')) {
      return 'https://www.rbi.org.in/Scripts/CommunicationPolicy.aspx';
    }
    if (titleLower.includes('remittance') || titleLower.includes('foreign exchange') || titleLower.includes('v-cip audit') || titleLower.includes('flagged scan')) {
      return 'https://www.rbi.org.in/Scripts/NotificationUser.aspx';
    }
    if (titleLower.includes('sources of information') || titleLower.includes('circular index')) {
      return 'https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx';
    }
    return 'https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx';
  }

  // 1. Financial Conduct Authority (FCA) — UK
  if (
    authorityLower.includes('fca') ||
    authorityLower.includes('financial conduct authority') ||
    titleLower.includes('fca')
  ) {
    if (rawUrl && rawUrl.includes('fca.org.uk')) return rawUrl;
    return 'https://www.fca.org.uk/news/press-releases';
  }

  // 2. Cybersecurity & IT (CERT-In / PIB / MeitY)
  if (
    authorityLower.includes('cert') ||
    authorityLower.includes('pib') ||
    authorityLower.includes('meity') ||
    titleLower.includes('cyber') ||
    titleLower.includes('it infrastructure')
  ) {
    if (rawUrl && (rawUrl.includes('pib.gov.in') || rawUrl.includes('cert-in.org.in') || rawUrl.includes('meity.gov.in'))) {
      return rawUrl;
    }
    return 'https://pib.gov.in/PressReleasePage.aspx?PRID=1820904';
  }

  // 3. Reserve Bank of India (RBI) — Title-Specific Notification Links
  if (
    authorityLower.includes('rbi') ||
    authorityLower.includes('reserve bank') ||
    titleLower.includes('kyc') ||
    titleLower.includes('master direction') ||
    titleLower.includes('remittance') ||
    titleLower.includes('communication policy') ||
    titleLower.includes('sources of information') ||
    sectorLower.includes('banking')
  ) {
    // Specific Document Notification Links on RBI.org.in
    if (titleLower.includes('communication policy')) {
      return 'https://www.rbi.org.in/Scripts/CommunicationPolicy.aspx';
    }
    if (titleLower.includes('remittance') || titleLower.includes('foreign exchange') || titleLower.includes('v-cip audit') || titleLower.includes('flagged scan')) {
      return 'https://www.rbi.org.in/Scripts/NotificationUser.aspx';
    }
    if (titleLower.includes('sources of information') || titleLower.includes('circular index')) {
      return 'https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx';
    }
    if (titleLower.includes('kyc') || titleLower.includes('know your customer')) {
      return 'https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12093';
    }

    if (rawUrl && rawUrl.includes('rbi.org.in') && !rawUrl.includes('id=12093')) {
      return rawUrl;
    }

    return 'https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx';
  }

  // 4. Healthcare & Life Sciences (HIPAA / HHS / eCFR)
  if (
    authorityLower.includes('hhs') ||
    authorityLower.includes('hipaa') ||
    titleLower.includes('hipaa') ||
    titleLower.includes('patient health') ||
    titleLower.includes('phi') ||
    sectorLower.includes('health')
  ) {
    if (rawUrl && (rawUrl.includes('ecfr.gov') || rawUrl.includes('hhs.gov') || rawUrl.includes('cornell.edu'))) {
      return rawUrl;
    }
    return 'https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164';
  }

  // 5. Capital Markets & Securities (SEC / FINRA)
  if (
    authorityLower.includes('sec') ||
    authorityLower.includes('finra') ||
    titleLower.includes('sec') ||
    titleLower.includes('trading') ||
    titleLower.includes('algorithmic') ||
    sectorLower.includes('capital markets') ||
    sectorLower.includes('securities')
  ) {
    if (rawUrl && (rawUrl.includes('finra.org') || rawUrl.includes('sec.gov'))) {
      return rawUrl;
    }
    return 'https://www.finra.org/rules-guidance/rulebooks/finra-rules';
  }

  // 6. If rawUrl is a valid HTTP URL, return rawUrl
  if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) {
    return rawUrl;
  }

  return 'https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx';
};
