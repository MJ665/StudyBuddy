import React from 'react';

export default function TermsAndConditions() {
  return (
    <div className="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8 text-gray-800 dark:text-gray-200">
      <h1 className="text-3xl font-bold mb-8">Terms & Conditions</h1>
      
      <div className="space-y-8">
        <section>
          <h2 className="text-xl font-semibold mb-4">1. AI Hallucination & Accuracy Disclaimer (CRITICAL)</h2>
          <p className="leading-relaxed">
            StudyBuddy utilizes Artificial Intelligence (LLMs) for quiz generation, code evaluation, and knowledge explanations. AI can make mistakes. The Platform makes no warranties regarding the 100% accuracy of AI-generated content. Users are advised to verify critical educational materials.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">2. User-Generated Content & Intellectual Property</h2>
          <p className="leading-relaxed">
            By uploading documents to the Knowledge Transfer (KT) module, you grant StudyBuddy a license to process, vector-embed, and store this data to provide AI services back to your Organization. You retain full ownership of your IP. You warrant that you are not uploading classified, HIPAA, or PCI-restricted data.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">3. Acceptable Use Policy (AUP)</h2>
          <p className="leading-relaxed">
            The code evaluation sandbox is strictly for educational purposes. Any attempt to execute malicious code, establish reverse shells, mine cryptocurrency, or perform Denial of Service (DoS) attacks against StudyBuddy infrastructure will result in immediate termination of the Organization's account.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">4. Data Processing & Privacy</h2>
          <p className="leading-relaxed">
            We track telemetry, including performance vectors and learning velocities, to improve user outcomes. We do not sell your personal learning data to third-party data brokers.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-4">5. Service Level Agreement (SLA) & Uptime</h2>
          <p className="leading-relaxed">
            While we strive for 99.9% uptime, StudyBuddy is provided 'as is'. We are not liable for missed educational deadlines or enterprise business losses resulting from platform downtime, AI rate-limiting, or third-party (AWS/OpenAI/Google) outages.
          </p>
        </section>
      </div>
    </div>
  );
}
