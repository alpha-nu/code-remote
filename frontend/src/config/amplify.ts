/**
 * AWS Amplify configuration for Cognito authentication.
 */

import { Amplify } from 'aws-amplify';

const amplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
      userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID || '',
      loginWith: {
        oauth: {
          domain: import.meta.env.VITE_COGNITO_DOMAIN || '',
          scopes: ['openid', 'email', 'profile'],
          redirectSignIn: [import.meta.env.VITE_COGNITO_REDIRECT_SIGNIN || 'http://localhost:5173'],
          redirectSignOut: [import.meta.env.VITE_COGNITO_REDIRECT_SIGNOUT || 'http://localhost:5173'],
          responseType: 'code' as const,
        },
      },
    },
  },
};

/**
 * Configure Amplify with Cognito settings.
 * Call this once at app startup.
 */
export function configureAmplify(): void {
  Amplify.configure(amplifyConfig);
}

export default amplifyConfig;
