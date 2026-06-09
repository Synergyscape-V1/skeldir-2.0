import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { SignUpForm } from './SignUpForm';

export function SignUpPage() {
    return (
        <div className="min-h-screen w-full flex flex-col items-center justify-center relative overflow-hidden bg-[#0A0A0A] auth-page-container">
            {/* Skeldir Logo - Top Left Corner */}
            <Link 
                href="/" 
                aria-label="Skeldir by Synergyscape"
                className="auth-page-logo absolute z-50 flex items-center"
                style={{
                    top: 'max(10px, env(safe-area-inset-top, 0px))',
                    left: 'max(10px, env(safe-area-inset-left, 0px))',
                    padding: '0',
                    margin: '0',
                }}
            >
                <Image
                    src="/images/logos/skeldir-x-synergyscape-lockup.png"
                    alt=""
                    aria-hidden="true"
                    width={335}
                    height={273}
                    sizes="(max-width: 767px) 116px, 146px"
                    priority
                    className="h-[76px] w-auto shrink-0 origin-left md:h-[80px] drop-shadow-2xl"
                />
            </Link>

            {/* Background Image */}
            <div 
                className="absolute inset-0 z-0"
                style={{
                    backgroundImage: 'url(/images/5594016.jpg)',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                    backgroundRepeat: 'no-repeat',
                    filter: 'brightness(0.95)',
                }}
            />

            {/* Content Container */}
            <div className="auth-page-content relative z-10 w-full max-w-md px-6 py-12 md:py-16 flex flex-col items-center">
                {/* Form */}
                <SignUpForm />
            </div>

            <style dangerouslySetInnerHTML={{__html: `
                @media (max-width: 767px) {
                    .auth-page-container {
                        overflow-x: hidden !important;
                        padding: 0 !important;
                    }

                    .auth-page-logo {
                        top: max(8px, env(safe-area-inset-top, 0px)) !important;
                        left: max(8px, env(safe-area-inset-left, 0px)) !important;
                        max-width: calc(100vw - 16px) !important;
                    }

                    .auth-page-content {
                        padding: 128px 20px 24px 20px !important;
                        width: 100% !important;
                        max-width: 100% !important;
                        box-sizing: border-box !important;
                    }
                }
            `}} />
        </div>
    );
}
