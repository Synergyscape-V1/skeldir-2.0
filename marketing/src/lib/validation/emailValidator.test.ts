import { validateBusinessEmail } from './emailValidator';

describe('Business Email Validation', () => {
    const testCases = [
        { email: 'test@gmail.com', expected: false, id: 'VAL-001' },
        { email: 'admin@company.com', expected: true, id: 'VAL-002' },
        { email: 'user+tag@yahoo.com', expected: false, id: 'VAL-003' },
        { email: 'cfo@startup.io', expected: true, id: 'VAL-004' },
        { email: 'invalid-email', expected: false, id: 'VAL-005' },
        { email: 'user@outlook.com', expected: false, id: 'VAL-006' },
        { email: 'team@company.gmail.com', expected: false, id: 'VAL-007' },
        { email: 'support@example.org', expected: true, id: 'VAL-008' },
        { email: 'admin@mail.com', expected: false, id: 'VAL-009' },
        { email: ' user@company.com ', expected: true, id: 'VAL-010' },
        { email: 'USER@COMPANY.COM', expected: true, id: 'VAL-011' },
        { email: '@company.com', expected: false, id: 'VAL-012' },
    ];

    testCases.forEach(({ email, expected, id }) => {
        test(`${id}: ${email} should be ${expected ? 'valid' : 'invalid'}`, () => {
            const result = validateBusinessEmail(email);
            if (result.isValid !== expected) {
                console.log(`Failed ${id}: Expected ${expected}, got ${result.isValid}. Error: ${result.error}`);
            }
            expect(result.isValid).toBe(expected);
        });
    });
});
