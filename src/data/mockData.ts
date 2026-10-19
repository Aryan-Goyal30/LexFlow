import type { CasePriority, CaseStatus, PracticeArea } from '../types';

/**
 * Fictional sample data, set in an Indian legal context (Supreme Court of
 * India, High Courts, District & Sessions Courts). All people, organisations,
 * case numbers and matters below are entirely fictional.
 *
 * This file is the single source of the sample records:
 * - `scripts/export-sample-data.mjs` writes them to
 *   `server/lexflow/seed/sample_data.json`, which `python -m lexflow.seed` loads
 *   into a development database (marked `is_sample`);
 * - front-end tests build their fake API responses from them.
 *
 * The running app never reads anything from here: case data and the signed-in
 * user both come from the API.
 *
 * Contact details are fictional by construction: e-mail addresses use the
 * reserved `.test` and `.example` domains (RFC 2606 / RFC 6761) and phone numbers
 * start with 0 after the country code, which no Indian number does, so no real
 * person can be reached through them.
 */

export interface SampleClient {
  id: string;
  name: string;
  email: string;
  phone: string;
  company?: string;
}

export interface SampleDocument {
  id: string;
  name: string;
  type: string;
  uploadedOn: string;
  /** A label only: sample records have no file, so there is no measured size. */
  size: string;
}

export interface SampleHearing {
  id: string;
  date: string;
  time: string;
  court: string;
  purpose: string;
}

export interface SampleEvent {
  id: string;
  date: string;
  label: string;
  description: string;
}

export interface SampleCase {
  id: string;
  caseNumber: string;
  title: string;
  status: CaseStatus;
  priority: CasePriority;
  practiceArea: PracticeArea;
  clientId: string;
  clientName: string;
  leadAttorney: string;
  courtName?: string;
  opposingParty?: string;
  description: string;
  openedOn: string;
  nextHearing?: string;
  documents: SampleDocument[];
  hearings: SampleHearing[];
  timeline: SampleEvent[];
}

export const mockClients: SampleClient[] = [
  {
    id: 'c-001',
    name: 'Aarav Textiles Pvt. Ltd.',
    email: 'legal@aarav-textiles.example',
    phone: '+91 00000 00001',
    company: 'Aarav Textiles Pvt. Ltd., Mumbai',
  },
  {
    id: 'c-002',
    name: 'Suresh Iyer',
    email: 'suresh.iyer@client.example',
    phone: '+91 00000 00002',
  },
  {
    id: 'c-003',
    name: 'Vikram Chauhan',
    email: 'chauhan.vikram@client.example',
    phone: '+91 00000 00003',
  },
  {
    id: 'c-004',
    name: 'Neha Sharma',
    email: 'neha.sharma@client.example',
    phone: '+91 00000 00004',
  },
  {
    id: 'c-005',
    name: 'Sattvik Foods Pvt. Ltd.',
    email: 'ip@sattvik-foods.example',
    phone: '+91 00000 00005',
    company: 'Sattvik Foods Pvt. Ltd., Pune',
  },
  {
    id: 'c-006',
    name: 'Nagrik Adhikar Foundation',
    email: 'contact@nagrik-adhikar.example',
    phone: '+91 00000 00006',
    company: 'Nagrik Adhikar Foundation (Regd.), New Delhi',
  },
];

export interface SampleAdvocate {
  name: string;
  /** Fictional sign-in address on the reserved `.test` domain. */
  email: string;
}

/** Advocates on record for the firm (used as "Lead Advocate" options). */
export const advocates: SampleAdvocate[] = [
  { name: 'Aryan Goyal', email: 'aryan.goyal@lexflow.test' },
  { name: 'Rajat Deshpande', email: 'rajat.deshpande@lexflow.test' },
  { name: 'Farhan Qureshi', email: 'farhan.qureshi@lexflow.test' },
  { name: 'Meera Nair', email: 'meera.nair@lexflow.test' },
  { name: 'Vikram Sethi', email: 'vikram.sethi@lexflow.test' },
];

export const mockCases: SampleCase[] = [
  {
    id: 'case-1001',
    caseNumber: 'LF-2026-0142',
    title: 'Aarav Textiles Pvt. Ltd. v. Meghdoot Logistics Pvt. Ltd.',
    status: 'In Progress',
    priority: 'High',
    practiceArea: 'Corporate / Commercial',
    clientId: 'c-001',
    clientName: 'Aarav Textiles Pvt. Ltd.',
    leadAttorney: 'Rajat Deshpande',
    courtName: 'High Court of Judicature at Bombay, Mumbai',
    opposingParty: 'Meghdoot Logistics Pvt. Ltd.',
    description:
      'Commercial suit for recovery of Rs. 3.85 crore together with damages, arising from repeated delays and short-supply under a three-year warehousing and freight agreement dated 12 March 2025. The Plaintiff also seeks a permanent injunction restraining the Defendant from invoking the auto-renewal clause. Registered as Comm. Suit No. 487 of 2026 before the Commercial Division.',
    openedOn: '2026-02-11',
    nextHearing: '2026-09-22',
    documents: [
      {
        id: 'd-1',
        name: 'Warehousing and Freight Agreement dated 12.03.2025.pdf',
        type: 'Agreement',
        uploadedOn: '2026-02-12',
        size: '512 KB',
      },
      {
        id: 'd-2',
        name: 'Statement of Claim.pdf',
        type: 'Pleading',
        uploadedOn: '2026-02-20',
        size: '288 KB',
      },
      {
        id: 'd-3',
        name: 'Invoices and Delivery Challans (Compilation).pdf',
        type: 'Evidence',
        uploadedOn: '2026-03-03',
        size: '1.4 MB',
      },
      {
        id: 'd-4',
        name: 'Reply to Section 8 Notice invoking Arbitration.pdf',
        type: 'Correspondence',
        uploadedOn: '2026-04-18',
        size: '76 KB',
      },
    ],
    hearings: [
      {
        id: 'h-1',
        date: '2026-09-22',
        time: '10:30',
        court: 'Court Room 52',
        purpose: 'Arguments on interim application for injunction',
      },
    ],
    timeline: [
      {
        id: 't-1',
        date: '2026-02-11',
        label: 'Matter opened',
        description: 'Engagement confirmed; vakalatnama executed by the company.',
      },
      {
        id: 't-2',
        date: '2026-02-19',
        label: 'Suit filed',
        description: 'Commercial suit filed with application under Order XXXIX Rules 1 and 2 CPC.',
      },
      {
        id: 't-3',
        date: '2026-03-10',
        label: 'Suit registered',
        description: 'Registered as Comm. Suit No. 487 of 2026; summons issued to the Defendant.',
      },
      {
        id: 't-4',
        date: '2026-05-06',
        label: 'Written statement filed',
        description: 'Defendant filed its written statement; replication under preparation.',
      },
    ],
  },
  {
    id: 'case-1002',
    caseNumber: 'LF-2025-0331',
    title: 'Suresh Iyer v. Lalitha Iyer and Others',
    status: 'On Hold',
    priority: 'Medium',
    practiceArea: 'Civil',
    clientId: 'c-002',
    clientName: 'Suresh Iyer',
    leadAttorney: 'Meera Nair',
    courtName: 'Court of the District and Sessions Judge, Saket District Courts, New Delhi',
    opposingParty: 'Lalitha Iyer and 3 others (co-defendants)',
    description:
      'Suit for partition and separate possession of a one-fourth share in ancestral immovable property at Chittaranjan Park, New Delhi, along with rendition of accounts of rental income. Proceedings are presently deferred pending the outcome of a court-referred mediation before the Delhi High Court Mediation and Conciliation Centre.',
    openedOn: '2025-11-03',
    nextHearing: '2026-10-14',
    documents: [
      {
        id: 'd-5',
        name: 'Registered Sale Deed dated 1998.pdf',
        type: 'Title Document',
        uploadedOn: '2025-11-05',
        size: '640 KB',
      },
      {
        id: 'd-6',
        name: 'Genealogical Tree and Legal Heirs Chart.pdf',
        type: 'Annexure',
        uploadedOn: '2025-11-12',
        size: '54 KB',
      },
      {
        id: 'd-7',
        name: 'Plaint for Partition.pdf',
        type: 'Pleading',
        uploadedOn: '2025-11-20',
        size: '210 KB',
      },
      {
        id: 'd-8',
        name: 'Draft Family Settlement Deed.docx',
        type: 'Draft',
        uploadedOn: '2026-06-09',
        size: '88 KB',
      },
    ],
    hearings: [
      {
        id: 'h-2',
        date: '2026-10-14',
        time: '11:00',
        court: 'Court Room 308',
        purpose: 'Report of the Mediation Centre and further directions',
      },
    ],
    timeline: [
      {
        id: 't-5',
        date: '2025-11-03',
        label: 'Matter opened',
        description: 'Client intake completed; property and revenue records collected.',
      },
      {
        id: 't-6',
        date: '2025-11-20',
        label: 'Plaint filed',
        description:
          'Suit for partition filed with court fee on the notional value of the share claimed.',
      },
      {
        id: 't-7',
        date: '2026-01-22',
        label: 'Matter referred to mediation',
        description:
          'Parties referred to the Delhi High Court Mediation and Conciliation Centre under Section 89 CPC.',
      },
      {
        id: 't-8',
        date: '2026-03-15',
        label: 'Proceedings placed on hold',
        description: 'Suit adjourned pending conclusion of the mediation.',
      },
    ],
  },
  {
    id: 'case-1003',
    caseNumber: 'LF-2026-0489',
    title: 'Vikram Chauhan v. State (NCT of Delhi)',
    status: 'In Progress',
    priority: 'Critical',
    practiceArea: 'Criminal',
    clientId: 'c-003',
    clientName: 'Vikram Chauhan',
    leadAttorney: 'Farhan Qureshi',
    courtName: 'Court of Sessions, Tis Hazari Courts, Delhi',
    opposingParty: 'State (NCT of Delhi)',
    description:
      'Application for regular bail on behalf of the applicant, arrested in connection with FIR No. 0214/2025 registered at PS Karol Bagh for offences punishable under Sections 318(4) and 316(2) of the Bharatiya Nyaya Sanhita, 2023. The applicant, in judicial custody since 28 June 2026, denies involvement and relies on parity with co-accused already enlarged on bail.',
    openedOn: '2026-07-19',
    nextHearing: '2026-09-15',
    documents: [
      {
        id: 'd-9',
        name: 'FIR No. 0214-2025 PS Karol Bagh.pdf',
        type: 'Court Record',
        uploadedOn: '2026-07-19',
        size: '120 KB',
      },
      {
        id: 'd-10',
        name: 'Bail Application under Section 483 BNSS (Draft).docx',
        type: 'Pleading',
        uploadedOn: '2026-07-21',
        size: '64 KB',
      },
      {
        id: 'd-11',
        name: 'Custody and Remand Orders.pdf',
        type: 'Court Record',
        uploadedOn: '2026-07-22',
        size: '96 KB',
      },
      {
        id: 'd-12',
        name: 'Chargesheet under Section 193 BNSS.pdf',
        type: 'Court Record',
        uploadedOn: '2026-08-27',
        size: '2.1 MB',
      },
    ],
    hearings: [
      {
        id: 'h-3',
        date: '2026-09-15',
        time: '14:00',
        court: 'Court Room 14',
        purpose: 'Arguments on the bail application',
      },
    ],
    timeline: [
      {
        id: 't-9',
        date: '2026-07-19',
        label: 'Matter opened',
        description: 'Brief received from the family of the accused; custody papers obtained.',
      },
      {
        id: 't-10',
        date: '2026-07-24',
        label: 'Bail application filed',
        description:
          'Regular bail application filed before the Sessions Court and listed for reply.',
      },
      {
        id: 't-11',
        date: '2026-08-11',
        label: 'Reply filed by prosecution',
        description: 'Status report and reply filed by the State opposing the grant of bail.',
      },
      {
        id: 't-12',
        date: '2026-08-27',
        label: 'Chargesheet filed',
        description:
          'Investigation completed; chargesheet filed and cognizance taken by the Court.',
      },
    ],
  },
  {
    id: 'case-1004',
    caseNumber: 'LF-2025-0207',
    title: 'Neha Sharma and Rohan Sharma — Petition under Section 13B, Hindu Marriage Act, 1955',
    status: 'Closed',
    priority: 'Low',
    practiceArea: 'Family',
    clientId: 'c-004',
    clientName: 'Neha Sharma',
    leadAttorney: 'Meera Nair',
    courtName: 'Court of the Principal Judge, Family Court, Bengaluru',
    opposingParty: undefined,
    description:
      'Joint petition for dissolution of marriage by mutual consent under Section 13B of the Hindu Marriage Act, 1955. The parties recorded a comprehensive settlement covering permanent alimony, return of stridhan and custody of the minor child. The first and second motions were completed and a decree of divorce by mutual consent was granted.',
    openedOn: '2025-09-16',
    nextHearing: undefined,
    documents: [
      {
        id: 'd-13',
        name: 'Joint Petition under Section 13B HMA.pdf',
        type: 'Pleading',
        uploadedOn: '2025-09-18',
        size: '180 KB',
      },
      {
        id: 'd-14',
        name: 'Marriage Certificate.pdf',
        type: 'Annexure',
        uploadedOn: '2025-09-18',
        size: '42 KB',
      },
      {
        id: 'd-15',
        name: 'Memorandum of Settlement (Mutual Consent).pdf',
        type: 'Agreement',
        uploadedOn: '2025-10-02',
        size: '156 KB',
      },
      {
        id: 'd-16',
        name: 'First Motion Order.pdf',
        type: 'Court Order',
        uploadedOn: '2025-10-20',
        size: '88 KB',
      },
      {
        id: 'd-17',
        name: 'Decree of Divorce.pdf',
        type: 'Court Order',
        uploadedOn: '2026-04-29',
        size: '132 KB',
      },
    ],
    hearings: [],
    timeline: [
      {
        id: 't-13',
        date: '2025-09-16',
        label: 'Matter opened',
        description:
          'Both parties advised jointly; settlement terms finalised and reduced to writing.',
      },
      {
        id: 't-14',
        date: '2025-10-20',
        label: 'First motion allowed',
        description:
          'Statements of the parties recorded; first motion allowed by the Family Court.',
      },
      {
        id: 't-15',
        date: '2026-04-22',
        label: 'Second motion recorded',
        description:
          'Parties reaffirmed consent after the statutory interregnum; matter reserved for orders.',
      },
      {
        id: 't-16',
        date: '2026-04-29',
        label: 'Decree granted; matter closed',
        description:
          'Decree of divorce by mutual consent granted; certified copy delivered to the client.',
      },
    ],
  },
  {
    id: 'case-1005',
    caseNumber: 'LF-2026-0361',
    title: 'Sattvik Foods Pvt. Ltd. v. Nisarga Retail Pvt. Ltd.',
    status: 'In Progress',
    priority: 'High',
    practiceArea: 'Intellectual Property',
    clientId: 'c-005',
    clientName: 'Sattvik Foods Pvt. Ltd.',
    leadAttorney: 'Aryan Goyal',
    courtName: 'High Court of Delhi at New Delhi',
    opposingParty: 'Nisarga Retail Pvt. Ltd.',
    description:
      'Commercial suit for a permanent injunction restraining infringement of the registered trade mark "SATTVIK" (word and label, Class 30) and passing off, together with delivery-up and rendition of accounts. The Plaintiff alleges adoption of a deceptively similar mark and trade dress for packaged snack foods. An ad-interim injunction has been granted and is in operation.',
    openedOn: '2026-06-27',
    nextHearing: '2026-09-30',
    documents: [
      {
        id: 'd-18',
        name: 'Trade Mark Registration Certificate (Class 30).pdf',
        type: 'Title Document',
        uploadedOn: '2026-06-27',
        size: '220 KB',
      },
      {
        id: 'd-19',
        name: 'Cease and Desist Notice.pdf',
        type: 'Correspondence',
        uploadedOn: '2026-06-30',
        size: '70 KB',
      },
      {
        id: 'd-20',
        name: 'Plaint with Interim Application.pdf',
        type: 'Pleading',
        uploadedOn: '2026-07-04',
        size: '340 KB',
      },
      {
        id: 'd-21',
        name: 'Comparative Packaging and Trade Dress Chart.pdf',
        type: 'Evidence',
        uploadedOn: '2026-07-04',
        size: '3.2 MB',
      },
    ],
    hearings: [
      {
        id: 'h-5',
        date: '2026-09-30',
        time: '12:00',
        court: 'Court Room 26',
        purpose: 'Hearing on confirmation of the ad-interim injunction',
      },
    ],
    timeline: [
      {
        id: 't-17',
        date: '2026-06-27',
        label: 'Matter opened',
        description: 'Instructions received; trade mark portfolio and market samples reviewed.',
      },
      {
        id: 't-18',
        date: '2026-07-04',
        label: 'Suit filed',
        description:
          'Suit filed with application under Order XXXIX CPC seeking ex-parte ad-interim relief.',
      },
      {
        id: 't-19',
        date: '2026-07-08',
        label: 'Ad-interim injunction granted',
        description: 'Court granted an ad-interim injunction and appointed a Local Commissioner.',
      },
      {
        id: 't-20',
        date: '2026-08-19',
        label: 'Local Commissioner report filed',
        description:
          'Report and seized samples placed on record; matter listed for inter-partes hearing.',
      },
    ],
  },
  {
    id: 'case-1006',
    caseNumber: 'LF-2026-0118',
    title: 'Nagrik Adhikar Foundation v. Union of India and Others',
    status: 'Open',
    priority: 'High',
    practiceArea: 'Constitutional / Administrative',
    clientId: 'c-006',
    clientName: 'Nagrik Adhikar Foundation',
    leadAttorney: 'Vikram Sethi',
    courtName: 'Supreme Court of India, New Delhi',
    opposingParty: 'Union of India and Others',
    description:
      'Public interest writ petition under Article 32 of the Constitution challenging an office memorandum dated 4 June 2026 that curtails proactive disclosure of environmental compliance data for infrastructure projects. The Petitioner, a registered civil-society organisation, seeks a declaration that the memorandum is ultra vires the Environment (Protection) Act, 1986 and Article 21, and a direction restoring proactive disclosure.',
    openedOn: '2026-01-15',
    nextHearing: '2026-10-07',
    documents: [
      {
        id: 'd-22',
        name: 'Writ Petition (Civil) under Article 32.pdf',
        type: 'Pleading',
        uploadedOn: '2026-01-16',
        size: '410 KB',
      },
      {
        id: 'd-23',
        name: 'Impugned Office Memorandum dated 04.06.2026.pdf',
        type: 'Annexure',
        uploadedOn: '2026-01-16',
        size: '58 KB',
      },
      {
        id: 'd-24',
        name: 'Synopsis and List of Dates.pdf',
        type: 'Pleading',
        uploadedOn: '2026-01-16',
        size: '96 KB',
      },
      {
        id: 'd-25',
        name: 'Affidavit in Support of Petition.pdf',
        type: 'Affidavit',
        uploadedOn: '2026-01-18',
        size: '120 KB',
      },
      {
        id: 'd-26',
        name: 'Vakalatnama.pdf',
        type: 'Court Record',
        uploadedOn: '2026-01-18',
        size: '30 KB',
      },
    ],
    hearings: [
      {
        id: 'h-6',
        date: '2026-10-07',
        time: '10:30',
        court: 'Court No. 4',
        purpose: 'Preliminary hearing on maintainability and issuance of notice',
      },
    ],
    timeline: [
      {
        id: 't-21',
        date: '2026-01-15',
        label: 'Matter opened',
        description:
          'Instructions received from the Foundation; cause of action and locus standi documented.',
      },
      {
        id: 't-22',
        date: '2026-01-17',
        label: 'Petition filed',
        description:
          'Writ petition filed with the Registry; awaiting scrutiny and first listing before the Court.',
      },
    ],
  },
];
