import React from 'react';

export const metadata = {
  title: 'Privacy Policy — StudyBuddy',
  description: 'How StudyBuddy collects, uses, and protects your data, and how to delete your account.',
};

export default function PrivacyPolicy() {
  return (
    <div className="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8 text-gray-800 dark:text-gray-200">
      <h1 className="text-3xl font-bold mb-2">Privacy Policy</h1>
      <p className="text-sm text-gray-500 mb-8">Last updated: 2026</p>

      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold mb-4">1. Data We Collect</h2>
          <p className="leading-relaxed">
            StudyBuddy collects the information you provide to use the platform: your name and work
            email (for authentication), your organization/role, and the content you generate —
            assessment attempts and scores, discussion posts, and any documents you upload to the
            Knowledge Transfer (KT) module. We also collect basic usage and device information
            (including a push-notification token if you use the mobile app) to operate the service.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">2. How We Use It</h2>
          <p className="leading-relaxed">
            Your data is used to provide the assessment and knowledge-transfer features, generate
            AI feedback and analytics for you and your organization&apos;s administrators, and send
            you relevant notifications. We do not sell your personal data.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">3. Data Sharing & Processors</h2>
          <p className="leading-relaxed">
            Content is visible within your organization according to your role. We use trusted
            processors to operate the service (cloud hosting, an AI model provider for evaluations
            and embeddings, email delivery, and — for the mobile app — a push-notification
            provider). These process data only to deliver the service.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">4. Security</h2>
          <p className="leading-relaxed">
            Data is encrypted in transit (HTTPS). Passwords are hashed. Access to organization data
            is scoped by role and organization membership.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">5. Your Rights &amp; Account Deletion</h2>
          <p className="leading-relaxed">
            You can delete your account and associated personal data at any time from the app:
            open <strong>My Profile → Security → Delete account</strong>. Deleting your account
            deactivates it and removes your personal identifiers (name and email are anonymized and
            your credentials are erased). To request deletion by email instead, contact your
            organization administrator or{' '}
            <a className="text-indigo-500 underline" href="mailto:contact.hackathonmj@gmail.com">
              contact.hackathonmj@gmail.com
            </a>
            . We process deletion requests within 30 days.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">6. Contact</h2>
          <p className="leading-relaxed">
            Questions about this policy can be sent to{' '}
            <a className="text-indigo-500 underline" href="mailto:contact.hackathonmj@gmail.com">
              contact.hackathonmj@gmail.com
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
