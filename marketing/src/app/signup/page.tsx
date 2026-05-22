import { SignUpPage } from '@/components/auth/signup/SignUpPage';
import { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Sign Up - Skeldir',
    description: 'Create your Skeldir account and start building.',
    robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
};

export default function Page() {
    return <SignUpPage />;
}
