import ContactMe from '@/components/kt/ContactMe';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Contact Support | StudyBuddy KT',
  description: 'Reach out to the StudyBuddy Knowledge Transfer support team for assistance with organizational memory management.',
};

export default function ContactMePage() {
  return <ContactMe />;
}
