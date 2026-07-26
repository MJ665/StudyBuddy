import React from 'react';
import { DocShell } from '@/components/common/DocShell';

export const metadata = {
  title: 'Terms & Conditions — StudyBuddy',
  description: 'The terms governing use of the StudyBuddy assessment & knowledge-transfer platform.',
};

export default function TermsAndConditions() {
  return (
    <DocShell title="Terms & Conditions" updated="Last updated: 2026">
      <section>
        <h2>1. AI Accuracy Disclaimer</h2>
        <p>
          StudyBuddy uses AI (large language models) for question generation, evaluation of coding
          and descriptive answers, and knowledge explanations. AI can make mistakes. The platform
          makes no warranty that AI-generated content is fully accurate, and users should verify
          critical material. AI-graded results may be reviewed by a mentor or administrator.
        </p>
      </section>

      <section>
        <h2>2. Your Content &amp; Intellectual Property</h2>
        <p>
          By uploading documents to the Knowledge Transfer (KT) module, you grant StudyBuddy a
          license to process, embed, and store that content so it can be served back to your
          organization through the platform&apos;s AI features. You retain ownership of your
          content. You are responsible for ensuring you have the right to upload it and that you do
          not upload data you are not permitted to share.
        </p>
      </section>

      <section>
        <h2>3. Acceptable Use</h2>
        <p>
          Coding questions are <strong>evaluated by AI — the platform does not execute your
          code</strong>. You agree not to misuse the service: no attempts to disrupt, overload,
          reverse-engineer, or gain unauthorized access to the platform or other organizations&apos;
          data, and no uploading of unlawful or malicious content. Misuse may result in suspension
          or termination of the account.
        </p>
      </section>

      <section>
        <h2>4. Data &amp; Privacy</h2>
        <p>
          We process usage and performance data to operate and improve the service, as described in
          our <a href="/privacy">Privacy Policy</a>. We do not sell your personal data.
        </p>
      </section>

      <section>
        <h2>5. Availability &amp; Liability</h2>
        <p>
          The service is provided on an &quot;as is&quot; basis. We aim for high availability but do
          not guarantee uninterrupted service, and we are not liable for losses resulting from
          downtime, AI rate-limiting, or outages of third-party providers we rely on (cloud
          hosting, the AI model provider, and email delivery).
        </p>
      </section>

      <section>
        <h2>6. Contact</h2>
        <p>
          Questions about these terms:{' '}
          <a href="mailto:contact.hackathonmj@gmail.com">contact.hackathonmj@gmail.com</a>.
        </p>
      </section>
    </DocShell>
  );
}
