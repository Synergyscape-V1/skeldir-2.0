/** Auth entry flow surfaces — visual/navigation contract only */

export type IdentityMode = 'sign-in' | 'sign-up';

export type AuthEntrySurface = 'identity' | 'create-organization' | 'not-a-member';

export interface InviteContext {
  organizationName: string;
}

export type PostIdentityNextStep = 'create_organization' | 'dashboard' | 'not_a_member';
